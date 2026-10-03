"""User-facing diagnostics. Fake replies cover untrusted host/error boundaries."""
import json

import pytest

from cascadeur_mcp import manage
from cascadeur_mcp.bridge import compatibility
from cascadeur_mcp.bridge.protocol import BridgeError


@pytest.fixture
def host(tmp_path, monkeypatch):
    root = tmp_path / 'instance'
    root.mkdir()
    descriptor = dict(session='a' * 32, token='b' * 64, pid=123, protocol=1,
                      write_contract=compatibility.describe(), bridge_package_version='0.5.0a9')
    (root / 'session.json').write_text(json.dumps(descriptor))
    calls = []
    replies = {
        'ping_cascadeur': dict(host='Cascadeur', live_application=True, pid=123),
        'get_scene_info': dict(pid=123, current_frame=10, object_count=289, scene_name='PRIVATE_SCENE'),
        'get_bridge_capabilities': dict(host=dict(name='Cascadeur', pid=123, bridge_package_version='0.5.0a9'),
            write_contract=compatibility.describe(), operations={'get_fbx_export_status': {'classification': 'read'}}),
        'get_fbx_export_status': dict(export_available=True, export_verified=False, scene_name='PRIVATE_SCENE'),
    }
    class Client:
        def __init__(self, **kwargs):
            pass
        def call(self, method, params):
            calls.append(method)
            value = replies[method]
            if isinstance(value, Exception):
                raise value
            return dict(value, session='a' * 32)
    monkeypatch.setattr(manage, 'BridgeClient', Client)
    monkeypatch.setattr(manage, 'instance_root', lambda instance: root)
    monkeypatch.setattr(manage, 'package_version', lambda name: '1.30.0' if name == 'mcp' else '0.5.0a10')
    return root, calls, replies


def codes(result):
    return {item['code'] for item in result['diagnostics']}


def test_live_doctor_reports_loaded_contract_and_export_without_scene_writes(host):
    _, calls, _ = host
    result = manage.doctor(live=True)
    assert result['ok'] and result['status'] == 'CONNECTED'
    assert result['session']['host_package_version'] == '0.5.0a9'
    assert result['session']['live_write_compatibility'] == 'COMPATIBLE'
    assert result['export']['status'] == 'AVAILABLE_NOT_VALIDATED'
    assert result['write_readiness'] == 'NOT_EVALUATED'
    assert calls == ['ping_cascadeur', 'get_scene_info', 'get_bridge_capabilities', 'get_fbx_export_status']
    assert 'PRIVATE_SCENE' not in json.dumps(result)
    assert 'b' * 64 not in json.dumps(result)


def test_live_contract_mismatch_is_actionable_even_when_reads_succeed(host):
    _, calls, replies = host
    replies['get_bridge_capabilities']['write_contract'] = dict(compatibility.describe(), revision=1)
    result = manage.doctor(live=True)
    assert not result['ok']
    assert result['session']['status'] == 'CONNECTED'
    assert 'INCOMPATIBLE_HOST' in codes(result)
    assert any('restart' in item['next_step'].lower() for item in result['diagnostics'])
    assert result['status'] == 'ACTION_REQUIRED'
    assert set(calls) <= {'ping_cascadeur', 'get_scene_info', 'get_bridge_capabilities', 'get_fbx_export_status'}


def test_export_unavailable_is_warning_not_failed_connection(host):
    _, _, replies = host
    replies['get_fbx_export_status']['export_available'] = False
    result = manage.doctor(live=True)
    assert result['ok']
    assert result['status'] == 'CONNECTED_WITH_WARNINGS'
    assert result['export']['status'] == 'EXPORT_UNAVAILABLE'
    warning = next(item for item in result['diagnostics'] if item['code'] == 'EXPORT_UNAVAILABLE')
    assert warning['severity'] == 'warning' and 'license' in warning['next_step'].lower()


def test_missing_manifest_preserves_read_connection_but_not_write_acceptance(host):
    _, _, replies = host
    replies['get_bridge_capabilities'] = BridgeError('HOST_ERROR: private error')
    result = manage.doctor(live=True)
    assert result['session']['status'] == 'CONNECTED'
    assert result['session']['live_write_compatibility'] == 'NOT_EVALUATED'
    assert 'CAPABILITIES_UNAVAILABLE' in codes(result)
    assert result['status'] == 'CONNECTED_WITH_WARNINGS'
    assert 'private error' not in json.dumps(result)


@pytest.mark.parametrize('field,value', [('pid', 999), ('pid', True), ('name', 'PRIVATE_HOST')])
def test_manifest_identity_mismatch_is_not_write_acceptance(host, field, value):
    _, _, replies = host
    replies['get_bridge_capabilities']['host'][field] = value
    result = manage.doctor(live=True)
    assert not result['ok'] and 'HOST_IDENTITY_MISMATCH' in codes(result)
    assert result['session']['live_write_compatibility'] == 'NOT_EVALUATED'
    assert 'PRIVATE_HOST' not in json.dumps(result)


def test_manifest_version_is_not_arbitrary_host_text(host):
    _, _, replies = host
    replies['get_bridge_capabilities']['host']['bridge_package_version'] = 'secret\nTOKEN'
    result = manage.doctor(live=True)
    assert result['session']['host_package_version'] == 'NOT_REPORTED'
    assert 'secret' not in json.dumps(result)


def test_export_error_is_redacted_and_does_not_fail_read_connection(host):
    _, _, replies = host
    replies['get_fbx_export_status'] = BridgeError('HOST_ERROR: password=SECRET')
    result = manage.doctor(live=True)
    assert result['ok'] and 'EXPORT_STATUS_UNAVAILABLE' in codes(result)
    assert result['export']['status'] == 'NOT_EVALUATED'
    assert 'SECRET' not in json.dumps(result)


@pytest.mark.parametrize('value', [1, 'true', None])
def test_export_entitlement_requires_native_boolean(host, value):
    _, _, replies = host
    replies['get_fbx_export_status']['export_available'] = value
    result = manage.doctor(live=True)
    assert result['export']['status'] == 'NOT_EVALUATED'
    assert 'EXPORT_STATUS_UNAVAILABLE' in codes(result)


def test_static_doctor_never_probes_host_or_license(host):
    _, calls, _ = host
    result = manage.doctor()
    assert calls == []
    assert result['status'] == 'STATIC_CHECK_ONLY'
    assert result['session']['live_write_compatibility'] == 'NOT_EVALUATED'
    assert result['export']['status'] == 'NOT_EVALUATED'


@pytest.mark.parametrize('app_status,code', [('NOT_RUNNING', 'CASCADEUR_NOT_RUNNING'),
                                         ('RUNNING', 'BRIDGE_NOT_DISCOVERED'),
                                         ('UNKNOWN', 'NO_DESCRIPTOR')])
def test_missing_descriptor_diagnosis_does_not_guess_hook_loaded(host, monkeypatch, app_status, code):
    root, calls, _ = host
    (root / 'session.json').unlink()
    monkeypatch.setattr(manage, 'inspect_hook', lambda home, source: {'ok': True, 'status': 'MANAGED_HOOK_MATCH'})
    monkeypatch.setattr(manage, 'inspect_application', lambda home: {'status': app_status}, raising=False)
    result = manage.doctor(home=root, live=True)
    assert not result['ok'] and code in codes(result)
    assert calls == []


def test_hook_missing_has_install_advice(host, monkeypatch):
    root, _, _ = host
    monkeypatch.setattr(manage, 'inspect_hook', lambda home, source: {'ok': False, 'status': 'NOT_INSTALLED'})
    monkeypatch.setattr(manage, 'inspect_application', lambda home: {'status': 'UNKNOWN'}, raising=False)
    result = manage.doctor(home=root, live=True)
    assert not result['ok'] and 'HOOK_NOT_INSTALLED' in codes(result)
    assert any('install-host' in item['next_step'] for item in result['diagnostics'])


def test_text_cli_has_reason_and_next_step(host, capsys):
    root, _, _ = host
    (root / 'session.json').unlink()
    assert manage.main(['doctor', '--live', '--format', 'text']) == 1
    output = capsys.readouterr().out
    assert 'NO_DESCRIPTOR' in output and 'Next:' in output
    assert 'b' * 64 not in output


def test_host_session_change_during_diagnostics_is_rejected(host):
    _, _, replies = host
    class Client:
        def __init__(self, **kwargs):
            pass
        def call(self, method, params):
            return dict(replies[method], session=('c' if method == 'get_bridge_capabilities' else 'a') * 32)
    # A different authenticated session must not be merged into earlier PID checks.
    from unittest.mock import patch
    with patch.object(manage, 'BridgeClient', Client):
        result = manage.doctor(live=True)
    assert not result['ok'] and 'HOST_SESSION_CHANGED' in codes(result)


def test_windows_process_probe_reads_current_executable_without_shell():
    import os
    import sys
    from pathlib import Path
    if os.name != 'nt':
        pytest.skip('Windows process inspection is platform-specific')
    # Probe the actual pytest Python process, no synthetic process list.
    result = manage.inspect_application(Path(sys.executable).parent, executable=Path(sys.executable).name)
    assert result['status'] == 'RUNNING' and result['matching_process_count'] >= 1


def test_windows_process_probe_does_not_match_another_installation(tmp_path):
    import os
    import sys
    from pathlib import Path
    if os.name != 'nt':
        pytest.skip('Windows process inspection is platform-specific')
    result = manage.inspect_application(tmp_path, executable=Path(sys.executable).name)
    assert result['status'] in {'NOT_RUNNING', 'UNKNOWN'}
    assert result['status'] != 'RUNNING'


def test_configuration_error_json_has_fixed_next_step(capsys):
    assert manage.main(['doctor', '--instance', '../unsafe']) == 1
    report = json.loads(capsys.readouterr().out)
    assert report['status'] == 'INVALID_INSTANCE'
    assert report['diagnostics'][0]['code'] == 'INVALID_INSTANCE'
    assert 'instance' in report['diagnostics'][0]['next_step'].lower()


def test_missing_export_operation_does_not_send_probe(host):
    _, calls, replies = host
    replies['get_bridge_capabilities']['operations'] = {}
    report = manage.doctor(live=True)
    assert report['ok'] and report['export']['status'] == 'NOT_EVALUATED'
    assert 'get_fbx_export_status' not in calls
    assert 'EXPORT_STATUS_UNAVAILABLE' in codes(report)
