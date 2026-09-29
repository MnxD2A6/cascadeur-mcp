"""Local maintenance CLI; never loaded by the MCP stdio entrypoint.

Hook provenance: cascadeur_scripts/c01_startup.py and API_PROVENANCE.md.
No scene writes, shell commands, process control, or stale-session cleanup.
"""
import argparse
import ast
import json
import math
import os
import re
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .bridge.client import BridgeClient
from .bridge.protocol import BridgeError, ID, TOKEN, check_path, read_json

HOOK_RELATIVE = Path('resources/scripts/python/events/application_started/c01_startup.py')
MARKER = '# Managed by cascadeur-mcp maintenance v1\n'


class MaintenanceError(RuntimeError):
    """Fixed error codes only: CLI output must never echo credentials."""


def absolute_safe(value):
    path = Path(value)
    if not path.is_absolute() or '..' in path.parts:
        raise MaintenanceError('ABSOLUTE_PATH_REQUIRED')
    try:
        return check_path(path)
    except BridgeError:
        raise MaintenanceError('UNSAFE_PATH') from None


def source_dir(value=None):
    path = absolute_safe(value if value is not None else Path(__file__).absolute().parent.parent)
    for name in ('__init__.py', 'server.py', 'bridge/host.py'):
        if not absolute_safe(path / 'cascadeur_mcp' / name).is_file():
            raise MaintenanceError('INVALID_SOURCE')
    return path


def hook_path(home):
    home = absolute_safe(home)
    target = absolute_safe(home / HOOK_RELATIVE)
    if not absolute_safe(home / 'cascadeur.exe').is_file() or not target.parent.is_dir():
        raise MaintenanceError('INVALID_CASCADEUR_LAYOUT')
    return target


def hook_bytes(source):
    return (MARKER + '''"""Cascadeur application_started -> main-thread scene idle bridge."""
import sys

PROJECT_SOURCE = ''' + ascii(str(source)) + '''


def run():
    if PROJECT_SOURCE not in sys.path:
        sys.path.insert(0, PROJECT_SOURCE)
    from events import scene_idle_manager
    scene_idle_manager.execute_when_idle(_start_when_ready)
    print("C01_STARTUP queued for scene_idle")


def _start_when_ready():
    from cascadeur_mcp.bridge.host import start
    print("C01_STARTUP", start())
''').encode('utf-8')


def read_hook(path):
    with absolute_safe(path).open('rb') as stream:
        data = stream.read(65537)
    if len(data) > 65536:
        raise MaintenanceError('HOOK_TOO_LARGE')
    return data


def change_hook(home, source=None, *, apply=False, remove=False):
    target = hook_path(home)
    source = source_dir(source)
    expected = hook_bytes(source)
    try:
        existing = read_hook(target)
    except FileNotFoundError:
        existing = None
    if existing is not None and existing != expected:
        raise MaintenanceError('HOOK_CONFLICT')
    result = {'ok': True, 'path': str(target), 'source': str(source), 'applied': False}
    if remove:
        status = 'NOT_INSTALLED' if existing is None else 'WOULD_REMOVE'
        if apply and existing is not None:
            # A changed hook is never treated as ours just because of its marker.
            if read_hook(target) != expected:
                raise MaintenanceError('HOOK_CONFLICT')
            target.unlink()
            status = 'REMOVED'
            result['applied'] = True
    else:
        status = 'ALREADY_INSTALLED' if existing is not None else 'WOULD_INSTALL'
        if apply and existing is None:
            # Publish the complete file exclusively; never replace a competing hook.
            fd, temporary = tempfile.mkstemp(prefix='.cascadeur-mcp-', suffix='.tmp', dir=target.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(expected)
                    stream.flush()
                    os.fsync(stream.fileno())
                absolute_safe(target)
                try:
                    os.link(temporary, target)
                except FileExistsError:
                    raise MaintenanceError('HOOK_CONFLICT') from None
            finally:
                Path(temporary).unlink(missing_ok=True)
            status = 'INSTALLED'
            result['applied'] = True
    return dict(result, status=status)


def instance_root(instance):
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}', instance):
        raise MaintenanceError('INVALID_INSTANCE')
    if os.name == 'nt':
        base = os.environ.get('LOCALAPPDATA')
        if not base:
            raise MaintenanceError('LOCALAPPDATA_MISSING')
        base = absolute_safe(base)
    else:
        base = Path.home() / '.cache'
    return absolute_safe(base / 'cascadeur-mcp' / instance)


def check_session(root, *, live=False, timeout=5.0):
    if not math.isfinite(timeout) or not 0 < timeout <= 20:
        raise MaintenanceError('INVALID_TIMEOUT')
    root = absolute_safe(root)
    result = {'ok': False, 'pid_liveness': 'NOT_CHECKED', 'host_package_version': 'NOT_REPORTED'}
    try:
        data = read_json(root / 'session.json')
    except FileNotFoundError:
        return dict(result, status='NO_DESCRIPTOR')
    except PermissionError:
        return dict(result, status='PERMISSION_DENIED')
    except BridgeError:
        return dict(result, status='INVALID_DESCRIPTOR')
    if (type(data.get('protocol')) is not int or data['protocol'] != 1
            or type(data.get('pid')) is not int or data['pid'] <= 0
            or not isinstance(data.get('session'), str) or not ID.fullmatch(data['session'])
            or not isinstance(data.get('token'), str) or not TOKEN.fullmatch(data['token'])):
        return dict(result, status='INVALID_DESCRIPTOR')
    result['pid'] = data['pid']
    from .bridge import compatibility
    result['descriptor_write_compatibility'] = compatibility.status(data.get('write_contract'))
    # Descriptor metadata is not a live response; never echo arbitrary strings.
    label = data.get('bridge_package_version')
    result['descriptor_package_version'] = (label if type(label) is str and
        re.fullmatch(r'[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:(?:a|b|rc)[0-9]{1,4})?', label)
        else 'NOT_REPORTED')
    if not live:
        return dict(result, ok=True, status='DESCRIPTOR_VALID_NOT_CONNECTED')
    result['pid_liveness'] = 'UNKNOWN'
    try:
        client = BridgeClient(root=root, timeout=timeout)
        ping = client.call('ping_cascadeur', {})
        if (ping.get('host') != 'Cascadeur' or ping.get('live_application') is not True
                or type(ping.get('pid')) is not int or ping['pid'] != data['pid']):
            return dict(result, status='HOST_IDENTITY_MISMATCH')
        result['pid_liveness'] = 'RESPONDED'
        scene = client.call('get_scene_info', {})
        if (type(scene.get('pid')) is not int or scene['pid'] != data['pid']
                or type(scene.get('current_frame')) is not int
                or type(scene.get('object_count')) is not int or scene['object_count'] < 0):
            return dict(result, status='INVALID_SCENE_RESPONSE')
        # No scene names, session tokens, raw exceptions or arbitrary host fields.
        return dict(result, ok=True, status='CONNECTED', current_frame=scene['current_frame'],
                    object_count=scene['object_count'])
    except BridgeError as exc:
        code = str(exc).partition(':')[0]
        allowed = {'BRIDGE_TIMEOUT', 'BRIDGE_UNAVAILABLE', 'HOST_ERROR', 'UNSAFE_PATH'}
        return dict(result, status=code if code in allowed else 'BRIDGE_ERROR')
    except PermissionError:
        return dict(result, status='PERMISSION_DENIED')


def package_version(name):
    try:
        return version(name)
    except PackageNotFoundError:
        return 'NOT_INSTALLED'


def inspect_hook(home, source):
    target = hook_path(home)
    try:
        raw = read_hook(target)
    except FileNotFoundError:
        return {'ok': False, 'status': 'NOT_INSTALLED'}
    if raw == hook_bytes(source):
        return {'ok': True, 'status': 'MANAGED_HOOK_MATCH'}
    try:
        tree = ast.parse(raw.decode('utf-8-sig'))
        sources = [node.value.value for node in tree.body
                   if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
                   and any(isinstance(t, ast.Name) and t.id == 'PROJECT_SOURCE' for t in node.targets)]
    except (ValueError, SyntaxError, UnicodeError):
        sources = []
    # Literal inspection only. Matching source does not authenticate arbitrary code.
    return {'ok': False, 'status': 'EXISTING_UNMANAGED_OR_MODIFIED_HOOK',
            'source_literal_matches': sources == [str(source)], 'executed': False}


def doctor(*, source=None, home=None, instance='c01', live=False, timeout=5.0):
    source = source_dir(source)
    sdk = package_version('mcp')
    result = {'ok': True, 'python': '.'.join(map(str, sys.version_info[:3])),
              'client_version': package_version('cascadeur-mcp'), 'mcp_sdk_version': sdk,
              'source': str(source), 'instance': instance, 'cross_machine_validation': 'NOT_VERIFIED',
              'mode': 'READ_ONLY_LIVE' if live else 'STATIC_ONLY'}
    if home is not None:
        result['hook'] = inspect_hook(home, source)
    result['session'] = check_session(instance_root(instance), live=live, timeout=timeout)
    result['ok'] = (sdk != 'NOT_INSTALLED' and sys.version_info >= (3, 10)
                    and result['session']['ok'] and result.get('hook', {'ok': True})['ok'])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('doctor', 'install-host', 'uninstall-host'):
        cmd = sub.add_parser(command)
        cmd.add_argument('--source', help='Absolute source or site-packages directory containing cascadeur_mcp')
        cmd.add_argument('--cascadeur-home', required=command != 'doctor', help='Absolute Cascadeur installation directory')
        if command == 'doctor':
            cmd.add_argument('--instance', default=os.environ.get('CASCADEUR_MCP_INSTANCE', 'c01'))
            cmd.add_argument('--live', action='store_true', help='Send only ping and scene read requests')
            cmd.add_argument('--timeout', type=float, default=5.0)
        else:
            cmd.add_argument('--apply', action='store_true', help='Apply the previewed operation; close Cascadeur first')
    args = parser.parse_args(argv)
    try:
        if args.command == 'doctor':
            result = doctor(source=args.source, home=args.cascadeur_home,
                            instance=args.instance, live=args.live, timeout=args.timeout)
        else:
            result = change_hook(args.cascadeur_home, args.source, apply=args.apply,
                                 remove=args.command == 'uninstall-host')
    except MaintenanceError as exc:
        result = {'ok': False, 'status': str(exc)}
    except PermissionError:
        result = {'ok': False, 'status': 'PERMISSION_DENIED'}
    except OSError:
        result = {'ok': False, 'status': 'FILESYSTEM_ERROR'}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
