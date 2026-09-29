"""Error-contract regression; simulated transport is not native acceptance."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from pathlib import Path

import pytest

from cascadeur_mcp.bridge import host
from cascadeur_mcp.bridge.client import BridgeClient
from cascadeur_mcp.bridge.protocol import BridgeError, read_json, write_json
from cascadeur_mcp.bridge.errors import describe_error, validate_remote_error


def test_rollback_text_is_not_evidence():
    value = describe_error(BridgeError('CHARACTER_POSE_FAILED: rollback_verified=True'),
                          operation='set_pose_sequence', is_write=True, phase='host_dispatch')
    assert value['execution_state'] == 'outcome_unknown'
    assert value['rollback_verified'] is None


def test_explicit_native_state_evidence():
    for restored, state in [(True, 'rolled_back'), (False, 'recovery_required')]:
        exc = BridgeError('CHARACTER_POSE_FAILED: private', execution_state=state,
                          rollback_verified=restored, recovery_snapshot_id='a'*32)
        value = describe_error(exc, operation='set_pose_sequence', is_write=True, phase='host_dispatch')
        assert value['execution_state'] == state
        assert value['rollback_verified'] is restored
        assert value['recovery_snapshot_id'] == 'a'*32
        assert value['automatic_retry_allowed'] is False


def test_mutation_error_code_alone_is_not_a_preflight():
    error = BridgeError('EXPORT_CONFLICT: output changed during export')
    assert describe_error(error, operation='export_fbx', is_write=True,
                          phase='host_dispatch')['execution_state'] == 'outcome_unknown'


def test_replay_never_claims_original_was_not_executed():
    value = describe_error(BridgeError('DUPLICATE_REQUEST: rejected'),
                          operation='set_pose_sequence', is_write=True, phase='host_validation')
    assert value['execution_state'] == 'outcome_unknown'


def test_remote_rollback_requires_typed_proof():
    value = describe_error(BridgeError('FAILED', execution_state='rolled_back', rollback_verified=True),
                          operation='set_pose_sequence', is_write=True, phase='host_dispatch')
    value['rollback_verified'] = 'True'
    assert validate_remote_error(value, operation='set_pose_sequence', is_write=True) is None


@pytest.mark.parametrize('field', ['phase', 'execution_state', 'evidence', 'code'])
def test_malformed_metadata_is_rejected_without_exception(field):
    value = describe_error(BridgeError('FAILURE'), operation='set_pose_sequence',
                           is_write=True, phase='host_dispatch')
    value[field] = []
    assert validate_remote_error(value, operation='set_pose_sequence', is_write=True) is None


@pytest.mark.parametrize('phase,state,evidence', [
    ('host_result', 'not_started', 'phase_boundary'),
    ('host_validation', 'completed', 'phase_boundary'),
    ('host_dispatch', 'not_started', 'phase_boundary'),
    ('client_validation', 'not_started', 'phase_boundary'),
])
def test_contradictory_remote_evidence_is_rejected(phase, state, evidence):
    value = describe_error(BridgeError('FAILURE'), operation='set_pose_sequence',
                           is_write=True, phase='host_dispatch')
    value.update(phase=phase, execution_state=state, evidence=evidence)
    assert validate_remote_error(value, operation='set_pose_sequence', is_write=True) is None


def test_locked_journal_has_explicit_recovery_state(monkeypatch):
    from cascadeur_mcp.bridge import character
    scene = object()
    monkeypatch.setattr(character, '_journals', {id(scene): {'locked': True}})
    with pytest.raises(BridgeError) as caught:
        character.journal(scene)
    assert caught.value.execution_state == 'recovery_required'


def test_remote_replay_cannot_claim_not_started():
    value = describe_error(BridgeError('DUPLICATE_REQUEST'), operation='set_current_frame',
                           is_write=True, phase='host_validation')
    value['execution_state'] = 'not_started'
    assert validate_remote_error(value, operation='set_current_frame', is_write=True) is None


@pytest.mark.parametrize('after_success', [False, True])
def test_server_fallback_preserves_execution_stage(monkeypatch, after_success):
    from cascadeur_mcp import server
    class Client:
        def call(self, *args):
            if after_success:
                return {'cannot_encode': {object()}}
            raise RuntimeError('unexpected failure after publication')
    monkeypatch.setattr(server, 'BridgeClient', Client)
    result = asyncio.run(server.call_tool('set_current_frame', {'scene': 'fixture', 'frame': 0}))
    assert result.isError
    assert result.structuredContent['error']['execution_state'] == ('completed' if after_success else 'outcome_unknown')


def test_redaction_does_not_echo_exception_values():
    secret = 'private-token-value-do-not-return'
    value = describe_error(ValueError(secret), operation='get_objects', is_write=False, phase='host_dispatch')
    assert secret not in str(value)
    assert value['execution_state'] == 'read_failed'


def test_client_invalid_input_not_submitted(tmp_path):
    with pytest.raises(BridgeError) as caught:
        BridgeClient(tmp_path).call('get_objects', {'limit': True})
    assert caught.value.details['execution_state'] == 'not_started'
    assert caught.value.details['phase'] == 'client_validation'
    assert not list(tmp_path.iterdir())


def test_write_timeout_is_unknown_and_correlated(tmp_path):
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    with pytest.raises(BridgeError) as caught:
        BridgeClient(tmp_path, timeout=.1).call('set_current_frame', {'scene': 'fixture', 'frame': 0})
    details = caught.value.details
    assert details['code'] == 'WRITE_OUTCOME_UNKNOWN'
    assert details['execution_state'] == 'outcome_unknown'
    assert len(details['request_id']) == 32 and details['session_id'] == bridge.session


def test_publication_failure_is_conservative(tmp_path, monkeypatch):
    from cascadeur_mcp.bridge import client
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    def publish_then_fail(path, payload):
        write_json(path, payload)
        raise PermissionError('temporary cleanup failed')
    monkeypatch.setattr(client, 'write_json', publish_then_fail)
    with pytest.raises(BridgeError) as caught:
        BridgeClient(tmp_path).call('set_current_frame', {'scene': 'fixture', 'frame': 0})
    assert caught.value.details['execution_state'] == 'outcome_unknown'


def test_cleanup_failure_preserves_timeout(tmp_path, monkeypatch):
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    original = Path.unlink
    def deny(path, *args, **kwargs):
        if path.name.endswith('.request.json'):
            raise PermissionError('private detail')
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', deny)
    with pytest.raises(BridgeError) as caught:
        BridgeClient(tmp_path, timeout=.1).call('set_current_frame', {'scene': 'fixture', 'frame': 0})
    assert caught.value.details['code'] == 'WRITE_OUTCOME_UNKNOWN'
    assert caught.value.details['cleanup_failed'] is True


def roundtrip(tmp_path, monkeypatch, dispatch):
    bridge = host.HostBridge(tmp_path)
    bridge.publish()
    monkeypatch.setattr(host, 'dispatch', dispatch)
    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(BridgeClient(tmp_path).call, 'set_current_frame', {'scene': 'fixture', 'frame': 0})
        deadline = time.monotonic() + 3
        while not task.done() and time.monotonic() < deadline:
            bridge.tick()
            time.sleep(.01)
        return task.result()


def test_host_structured_metadata_reaches_client(tmp_path, monkeypatch):
    def simulated_dispatch(*args):
        raise BridgeError('TEST_FAILED', execution_state='rolled_back', rollback_verified=True)
    with pytest.raises(BridgeError) as caught:
        roundtrip(tmp_path, monkeypatch, simulated_dispatch)
    assert caught.value.details['execution_state'] == 'rolled_back'
    assert caught.value.details['evidence'] == 'explicit_host_state'


def test_old_host_rollback_text_does_not_upgrade_evidence(tmp_path, monkeypatch):
    original = host.write_json
    def legacy_write(path, value):
        if value.get('ok') is False:
            value = {k:v for k,v in value.items() if k != 'error_details'}
            value['error'] = 'rollback_verified=True; private-token'
        return original(path, value)
    monkeypatch.setattr(host, 'write_json', legacy_write)
    def fail(*args):
        raise BridgeError('FAILED', execution_state='rolled_back', rollback_verified=True)
    with pytest.raises(BridgeError) as caught:
        roundtrip(tmp_path, monkeypatch, fail)
    assert caught.value.details['execution_state'] == 'outcome_unknown'
    assert caught.value.details['rollback_verified'] is None
    assert 'private-token' not in str(caught.value)


def test_result_delivery_failure_preserves_completed_state(tmp_path, monkeypatch):
    original = host.write_json
    def delivery_failure(path, value):
        if value.get('ok') is True:
            raise PermissionError('cannot publish successful response')
        return original(path, value)
    monkeypatch.setattr(host, 'write_json', delivery_failure)
    with pytest.raises(BridgeError) as caught:
        roundtrip(tmp_path, monkeypatch, lambda *args: {'fixture': 'SIMULATED_WRITE_COMPLETE'})
    assert caught.value.details['execution_state'] == 'completed'
    assert caught.value.details['phase'] == 'host_result'


@pytest.mark.parametrize('corrupt', ['correlation', 'result', 'json'])
def test_corrupt_write_response_never_claims_not_started(tmp_path, monkeypatch, corrupt):
    original = host.write_json
    def corrupt_write(path, value):
        if value.get('ok') is True:
            if corrupt == 'correlation':
                value = {**value, 'id': '0'*32}
            elif corrupt == 'result':
                value = {**value, 'result': []}
            else:
                path.write_text('{invalid')
                return
        return original(path, value)
    monkeypatch.setattr(host, 'write_json', corrupt_write)
    with pytest.raises(BridgeError) as caught:
        roundtrip(tmp_path, monkeypatch, lambda *args: {'fixture': 'SIMULATED_WRITE_COMPLETE'})
    assert caught.value.details['execution_state'] == 'outcome_unknown'


@pytest.mark.parametrize('status', [None, 1, 'false'])
def test_invalid_response_status_cannot_claim_rollback(tmp_path, monkeypatch, status):
    original = host.write_json
    def corrupt_status(path, value):
        if value.get('ok') is False:
            value = {**value, 'ok': status}
        return original(path, value)
    monkeypatch.setattr(host, 'write_json', corrupt_status)
    def fail(*args):
        raise BridgeError('FAILED', execution_state='rolled_back', rollback_verified=True)
    with pytest.raises(BridgeError) as caught:
        roundtrip(tmp_path, monkeypatch, fail)
    assert caught.value.details['code'] == 'INVALID_RESPONSE'
    assert caught.value.details['execution_state'] == 'outcome_unknown'


def test_cleanup_error_does_not_erase_trusted_success(tmp_path, monkeypatch):
    unlink = Path.unlink
    def deny_response_cleanup(path, *args, **kwargs):
        if path.name.endswith('.response.json'):
            raise PermissionError('private detail')
        return unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'unlink', deny_response_cleanup)
    result = roundtrip(tmp_path, monkeypatch, lambda *args: {'fixture': 'SIMULATED_WRITE_COMPLETE'})
    assert result['fixture'] == 'SIMULATED_WRITE_COMPLETE'
    assert result['transport_warnings'] == ['CLEANUP_FAILED']


def test_stdio_handler_uses_structured_errors(tmp_path, monkeypatch):
    from cascadeur_mcp import server
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    response = asyncio.run(server.call_tool('get_objects', {'limit': True}))
    assert response.isError
    assert response.structuredContent['error']['execution_state'] == 'not_started'
    assert 'INVALID_PARAMS' in response.content[0].text


@pytest.mark.parametrize('state', ['matches', 'differs', 'capture_fails'])
def test_transaction_failure_verifies_state_or_locks_journal(monkeypatch, state):
    from cascadeur_mcp.bridge import character
    original = {'value': 1}
    journal = {'locked': False}
    def capture(scene):
        if state == 'capture_fails':
            raise RuntimeError('capture failed')
        return original if state == 'matches' else {'value': 2}
    monkeypatch.setattr(character, 'capture', capture)
    error = character._transaction_failure(None, original, journal, RuntimeError('setter failed'),
                                           'a'*32, 'HAND_WRITE_FAILED')
    assert error.rollback_verified is (state == 'matches')
    assert error.execution_state == ('rolled_back' if state == 'matches' else 'recovery_required')
    assert journal['locked'] is (state != 'matches')
