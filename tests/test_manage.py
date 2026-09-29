"""Local maintenance safety; synthetic layouts are not native host tests."""
import ast
import json
from pathlib import Path

import pytest

from cascadeur_mcp import manage


@pytest.fixture
def layout(tmp_path):
    home = tmp_path / 'Cascadeur'
    (home / 'cascadeur.exe').parent.mkdir()
    (home / 'cascadeur.exe').touch()
    (home / manage.HOOK_RELATIVE).parent.mkdir(parents=True)
    source = tmp_path / 'source with spaces 动作' / 'src'
    for name in ('__init__.py', 'server.py', 'bridge/host.py'):
        file = source / 'cascadeur_mcp' / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()
    return home, source


def test_preview_apply_idempotent_uninstall(layout):
    home, source = layout
    target = home / manage.HOOK_RELATIVE
    assert manage.change_hook(home, source)['status'] == 'WOULD_INSTALL'
    assert not target.exists()
    assert manage.change_hook(home, source, apply=True)['status'] == 'INSTALLED'
    assert manage.change_hook(home, source, apply=True)['status'] == 'ALREADY_INSTALLED'
    tree = ast.parse(target.read_text())
    value = next(node.value.value for node in tree.body if isinstance(node, ast.Assign))
    assert value == str(source)
    assert manage.change_hook(home, source, remove=True)['status'] == 'WOULD_REMOVE'
    assert target.exists()
    assert manage.change_hook(home, source, remove=True, apply=True)['status'] == 'REMOVED'
    assert not target.exists()
    assert manage.change_hook(home, source, remove=True, apply=True)['status'] == 'NOT_INSTALLED'


@pytest.mark.parametrize('remove', [False, True])
def test_never_overwrites_or_removes_different_hook(layout, remove):
    home, source = layout
    target = home / manage.HOOK_RELATIVE
    original = b'# unrelated or user modified hook\n'
    target.write_bytes(original)
    with pytest.raises(manage.MaintenanceError, match='HOOK_CONFLICT'):
        manage.change_hook(home, source, remove=remove, apply=True)
    assert target.read_bytes() == original


def test_changed_source_cannot_uninstall(layout):
    home, source = layout
    manage.change_hook(home, source, apply=True)
    other = source.parent / 'other'
    import shutil
    shutil.copytree(source, other)
    with pytest.raises(manage.MaintenanceError, match='HOOK_CONFLICT'):
        manage.change_hook(home, other, remove=True, apply=True)


def test_concurrent_creation_is_not_overwritten(layout, monkeypatch):
    home, source = layout
    target = home / manage.HOOK_RELATIVE
    def competing_write(*args):
        target.write_bytes(b'other installer won')
        raise FileExistsError()
    monkeypatch.setattr(manage.os, 'link', competing_write)
    with pytest.raises(manage.MaintenanceError, match='HOOK_CONFLICT'):
        manage.change_hook(home, source, apply=True)
    assert target.read_bytes() == b'other installer won'
    assert sorted(p.name for p in target.parent.iterdir()) == [target.name]


def test_generated_hook_uses_verified_template_functions(layout):
    _, source = layout
    template = Path(__file__).resolve().parents[1] / 'cascadeur_scripts/c01_startup.py'
    def functions(text):
        return [ast.dump(n) for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)]
    assert functions(manage.hook_bytes(source)) == functions(template.read_text())


def test_invalid_layout_and_relative_paths(layout):
    home, source = layout
    with pytest.raises(manage.MaintenanceError, match='ABSOLUTE_PATH_REQUIRED'):
        manage.change_hook(Path('relative'), source)
    (home / 'cascadeur.exe').unlink()
    with pytest.raises(manage.MaintenanceError, match='INVALID_CASCADEUR_LAYOUT'):
        manage.change_hook(home, source)


def test_source_symlink_rejected(layout, tmp_path):
    home, source = layout
    link = tmp_path / 'linked'
    try:
        link.symlink_to(source, target_is_directory=True)
    except OSError:
        pytest.skip('Creating symlinks requires platform permission')
    with pytest.raises(manage.MaintenanceError, match='UNSAFE_PATH'):
        manage.change_hook(home, link)


def descriptor(root, **changes):
    root.mkdir(parents=True, exist_ok=True)
    data = dict(session='a' * 32, token='b' * 64, pid=123, protocol=1)
    data.update(changes)
    (root / 'session.json').write_text(json.dumps(data))


def test_doctor_static_never_contacts_host(tmp_path, monkeypatch):
    descriptor(tmp_path)
    monkeypatch.setattr(manage, 'BridgeClient', lambda **kwargs: pytest.fail('unexpected live call'))
    result = manage.check_session(tmp_path)
    assert result['status'] == 'DESCRIPTOR_VALID_NOT_CONNECTED'
    assert result['pid_liveness'] == 'NOT_CHECKED'
    assert 'b' * 64 not in json.dumps(result)


@pytest.mark.parametrize('changes', [{'pid': True}, {'protocol': 2}, {'token': 'secret'}, {'session': 'bad'}])
def test_invalid_descriptor_redacted(tmp_path, changes):
    descriptor(tmp_path, **changes)
    result = manage.check_session(tmp_path)
    assert result['status'] == 'INVALID_DESCRIPTOR'
    assert 'secret' not in json.dumps(result)
    assert 'b' * 64 not in json.dumps(result)


def test_live_fixed_calls_and_no_secret_echo(tmp_path, monkeypatch):
    descriptor(tmp_path)
    calls = []
    class Client:
        def __init__(self, **kwargs):
            pass
        def call(self, method, params):
            calls.append((method, params))
            return (dict(host='Cascadeur', live_application=True, pid=123)
                    if method == 'ping_cascadeur' else
                    dict(current_frame=10, object_count=66, pid=123, scene_name='secret'))
    monkeypatch.setattr(manage, 'BridgeClient', Client)
    result = manage.check_session(tmp_path, live=True)
    assert result['status'] == 'CONNECTED'
    assert calls == [('ping_cascadeur', {}), ('get_scene_info', {})]
    assert 'secret' not in json.dumps(result)
    assert result['host_package_version'] == 'NOT_REPORTED'


@pytest.mark.parametrize('failure', ['BRIDGE_TIMEOUT: secret', 'HOST_ERROR: secret'])
def test_live_failures_redacted(tmp_path, monkeypatch, failure):
    descriptor(tmp_path)
    class Client:
        def __init__(self, **kwargs):
            pass
        def call(self, *args):
            raise manage.BridgeError(failure)
    monkeypatch.setattr(manage, 'BridgeClient', Client)
    result = manage.check_session(tmp_path, live=True)
    assert not result['ok']
    assert 'secret' not in json.dumps(result)
    assert result['pid_liveness'] == 'UNKNOWN'


def test_missing_descriptor_and_invalid_instance(tmp_path):
    assert manage.check_session(tmp_path)['status'] == 'NO_DESCRIPTOR'
    with pytest.raises(manage.MaintenanceError, match='INVALID_INSTANCE'):
        manage.instance_root('../escape')


def test_live_identity_mismatch_stops_before_scene(tmp_path, monkeypatch):
    descriptor(tmp_path)
    class Client:
        def __init__(self, **kwargs):
            pass
        def call(self, method, params):
            assert method == 'ping_cascadeur'
            return dict(host='Cascadeur', live_application=True, pid=999)
    monkeypatch.setattr(manage, 'BridgeClient', Client)
    assert manage.check_session(tmp_path, live=True)['status'] == 'HOST_IDENTITY_MISMATCH'


def test_permission_error_does_not_echo_details(tmp_path, monkeypatch):
    def deny(*args):
        raise PermissionError('private detail')
    monkeypatch.setattr(manage, 'read_json', deny)
    result = manage.check_session(tmp_path)
    assert result['status'] == 'PERMISSION_DENIED'
    assert 'private detail' not in json.dumps(result)


@pytest.mark.parametrize('timeout', [0, 21, float('nan'), float('inf')])
def test_timeout_bounds(tmp_path, timeout):
    with pytest.raises(manage.MaintenanceError, match='INVALID_TIMEOUT'):
        manage.check_session(tmp_path, timeout=timeout)


def test_cli_json_and_exit_code(capsys, layout):
    home, source = layout
    assert manage.main(['install-host', '--cascadeur-home', str(home), '--source', str(source)]) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'WOULD_INSTALL'
    assert manage.main(['install-host', '--cascadeur-home', 'relative']) == 1
    result = json.loads(capsys.readouterr().out)
    assert result == {'ok': False, 'status': 'ABSOLUTE_PATH_REQUIRED'}
