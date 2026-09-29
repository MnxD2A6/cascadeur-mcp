"""Real transport guards with simulated native dispatch; not native acceptance."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import time
import uuid

import pytest

from cascadeur_mcp.bridge import host, client
from cascadeur_mcp.bridge.capabilities import describe
from cascadeur_mcp.bridge.protocol import BridgeError, read_json, write_json


def roundtrip(bridge, monkeypatch, method='set_current_frame', params=None):
    dispatched = []
    def native_boundary(name, args):
        dispatched.append(name)
        return {'fixture': 'SIMULATED_NATIVE_BOUNDARY', 'method': name}
    monkeypatch.setattr(host, 'dispatch', native_boundary)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(client.BridgeClient(bridge.root, timeout=.4).call, method,
                           params if params is not None else {'scene': 'fixture', 'frame': 0})
        deadline = time.monotonic() + 2
        while not task.done() and time.monotonic() < deadline:
            bridge.tick()
            time.sleep(.005)
        return task, dispatched


@pytest.mark.parametrize('contract,code', [
    (None, 'HOST_UPGRADE_REQUIRED'),
    ({}, 'INVALID_HOST_CONTRACT'),
    ({'protocol_version': True, 'revision': 1, 'schema_sha256': 'a'*64}, 'INVALID_HOST_CONTRACT'),
    ({'protocol_version': 2, 'revision': 1, 'schema_sha256': 'a'*64}, 'INCOMPATIBLE_HOST'),
    ({'protocol_version': 1, 'revision': 999, 'schema_sha256': 'a'*64}, 'INCOMPATIBLE_HOST'),
    ({'protocol_version': 1, 'revision': 1, 'schema_sha256': 'a'*64}, 'INCOMPATIBLE_HOST'),
])
def test_old_or_incompatible_host_never_receives_write(tmp_path, monkeypatch, contract, code):
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    path = tmp_path/'session.json'
    descriptor = read_json(path)
    descriptor.pop('write_contract', None)
    if contract is not None:
        descriptor['write_contract'] = contract
    write_json(path, descriptor)
    task, dispatched = roundtrip(bridge, monkeypatch)
    with pytest.raises(BridgeError) as caught:
        task.result()
    assert caught.value.details['code'] == code
    assert caught.value.details['execution_state'] == 'not_started'
    assert caught.value.details['automatic_retry_allowed'] is False
    assert dispatched == []
    assert bridge.seen == set()


def test_legacy_descriptor_still_allows_read_diagnostics(tmp_path, monkeypatch):
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    path = tmp_path/'session.json'
    descriptor = read_json(path)
    descriptor.pop('write_contract', None)
    write_json(path, descriptor)
    task, dispatched = roundtrip(bridge, monkeypatch, 'ping_cascadeur', {})
    assert task.result()['method'] == 'ping_cascadeur'
    assert dispatched == ['ping_cascadeur']


def test_matching_contract_writes_with_one_request(tmp_path, monkeypatch):
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    task, dispatched = roundtrip(bridge, monkeypatch)
    assert task.result()['method'] == 'set_current_frame'
    assert dispatched == ['set_current_frame']
    assert len(bridge.seen) == 1


@pytest.mark.parametrize('supplied', [None, {'protocol_version': 1, 'revision': 1, 'schema_sha256': 'a'*64}])
def test_new_host_rejects_legacy_or_mismatched_write_before_dispatch(tmp_path, monkeypatch, supplied):
    bridge = host.HostBridge(tmp_path)
    dispatched = []
    monkeypatch.setattr(host, 'dispatch', lambda *args: dispatched.append(args))
    rid = uuid.uuid4().hex
    request = dict(version=1, id=rid, session=bridge.session, token=bridge.token,
                   expires_at=time.time()+5, method='set_current_frame', params={'scene': 'fixture', 'frame': 0})
    if supplied is not None:
        request['write_contract'] = supplied
    write_json(bridge.folder/(rid+'.request.json'), request)
    bridge.tick()
    response = read_json(bridge.folder/(rid+'.response.json'))
    assert response['ok'] is False
    assert response['error_details']['code'] == 'INCOMPATIBLE_CLIENT'
    assert response['error_details']['execution_state'] == 'not_started'
    assert dispatched == []


def test_restart_between_validation_and_publication_does_not_send_write(tmp_path, monkeypatch):
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    original = client.read_json
    reads = []
    def restart_after_read(path):
        value = original(path)
        if path == tmp_path/'session.json':
            reads.append(1)
            if len(reads) == 1:
                changed = deepcopy(value)
                changed['session'] = 'f'*32
                changed['token'] = 'e'*64
                write_json(path, changed)
        return value
    monkeypatch.setattr(client, 'read_json', restart_after_read)
    task, dispatched = roundtrip(bridge, monkeypatch)
    with pytest.raises(BridgeError) as caught:
        task.result()
    assert caught.value.details['code'] == 'HOST_SESSION_CHANGED'
    assert caught.value.details['execution_state'] == 'not_started'
    assert dispatched == []


def test_schema_or_revision_changes_require_new_compatibility_identity():
    from cascadeur_mcp.bridge import compatibility
    current = compatibility.describe()
    assert current['schema_sha256'] != compatibility.schema_fingerprint({'set_current_frame': {'changed': True}})
    changed = dict(current, revision=current['revision']+1)
    assert compatibility.status(changed) == 'INCOMPATIBLE_HOST'


def test_capability_identity_is_isolated_from_caller_mutation(tmp_path):
    first = describe()
    assert 'write_contract' in first
    first['write_contract']['schema_sha256'] = 'a'*64
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    advertised = read_json(tmp_path/'session.json')
    assert advertised['write_contract'] == describe()['write_contract']
    assert advertised['write_contract']['schema_sha256'] != 'a'*64


@pytest.mark.parametrize('kind', ['legacy', 'current', 'corrupt'])
def test_doctor_separates_descriptor_contract_from_live_readiness(tmp_path, kind):
    from cascadeur_mcp import manage
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    path = tmp_path/'session.json'
    data = read_json(path)
    if kind == 'legacy':
        data.pop('write_contract', None)
    elif kind == 'corrupt':
        data['write_contract'] = []
        data['bridge_package_version'] = 'private-path-or-token'
    write_json(path, data)
    result = manage.check_session(tmp_path)
    assert result['descriptor_write_compatibility'] == {
        'legacy': 'HOST_UPGRADE_REQUIRED', 'current': 'COMPATIBLE', 'corrupt': 'INVALID_HOST_CONTRACT'}[kind]
    assert result['pid_liveness'] == 'NOT_CHECKED'
    assert result['status'] == 'DESCRIPTOR_VALID_NOT_CONNECTED'
    assert 'private-path-or-token' not in str(result)


def test_package_label_difference_does_not_override_matching_contract(tmp_path, monkeypatch):
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    path = tmp_path/'session.json'
    data = read_json(path)
    data['bridge_package_version'] = '99.0.0'
    write_json(path, data)
    task, dispatched = roundtrip(bridge, monkeypatch)
    assert task.result()['method'] == 'set_current_frame'
    assert dispatched == ['set_current_frame']


def test_late_restart_never_redirects_request_to_new_session(tmp_path, monkeypatch):
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    original = client.write_json
    successor = host.HostBridge(tmp_path)
    def replace_descriptor_at_publish(path, value):
        if path.name.endswith('.request.json'):
            descriptor = read_json(tmp_path/'session.json')
            descriptor.update(session=successor.session, token=successor.token)
            write_json(tmp_path/'session.json', descriptor)
        return original(path, value)
    monkeypatch.setattr(client, 'write_json', replace_descriptor_at_publish)
    with pytest.raises(BridgeError) as caught:
        client.BridgeClient(tmp_path, timeout=.1).call('set_current_frame', {'scene': 'fixture', 'frame': 0})
    assert caught.value.details['execution_state'] == 'outcome_unknown'
    assert caught.value.details['session_id'] == bridge.session
    assert not list(successor.folder.iterdir())
