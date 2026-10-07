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


def check_session(root, *, live=False, timeout=5.0, _scope=None):
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
    if _scope is not None:
        _scope['session'] = data['session']
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
        if _scope is not None and ping.get('session') != _scope['session']:
            return dict(result, status='HOST_SESSION_CHANGED')
        if (ping.get('host') != 'Cascadeur' or ping.get('live_application') is not True
                or type(ping.get('pid')) is not int or ping['pid'] != data['pid']):
            return dict(result, status='HOST_IDENTITY_MISMATCH')
        result['pid_liveness'] = 'RESPONDED'
        scene = client.call('get_scene_info', {})
        if _scope is not None and scene.get('session') != _scope['session']:
            return dict(result, status='HOST_SESSION_CHANGED')
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


def inspect_application(home, *, executable='cascadeur.exe'):
    """Read Windows process metadata without a shell, signals or process control.

    Match the exact installation, ignore zero-thread retained process objects,
    and retain UNKNOWN when access restrictions prevent a reliable answer.
    The executable override exists for native OS tests; it is not a CLI input.
    """
    if os.name != 'nt':
        return {'status': 'NOT_SUPPORTED'}
    import ctypes
    from ctypes import wintypes as w
    class Entry(ctypes.Structure):
        _fields_ = [('size', w.DWORD), ('usage', w.DWORD), ('pid', w.DWORD),
                    ('heap', ctypes.c_size_t), ('module', w.DWORD), ('threads', w.DWORD),
                    ('parent', w.DWORD), ('priority', w.LONG), ('flags', w.DWORD),
                    ('exe', w.WCHAR * 260)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [w.DWORD, w.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
    for name in ('Process32FirstW', 'Process32NextW'):
        fn = getattr(kernel, name)
        fn.argtypes = [w.HANDLE, ctypes.POINTER(Entry)]
        fn.restype = w.BOOL
    kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    kernel.OpenProcess.restype = w.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
    kernel.QueryFullProcessImageNameW.restype = w.BOOL
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.CloseHandle.restype = w.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        return {'status': 'UNKNOWN'}
    expected = os.path.normcase(str(Path(home) / executable))
    count, unknown = 0, False
    try:
        entry = Entry()
        entry.size = ctypes.sizeof(entry)
        found = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        if not found:
            return {'status': 'UNKNOWN'}
        while found:
            if entry.exe.casefold() == executable.casefold() and entry.threads > 0:
                handle = kernel.OpenProcess(0x1000, False, entry.pid)
                if not handle:
                    unknown = True
                else:
                    try:
                        buffer = ctypes.create_unicode_buffer(32768)
                        length = w.DWORD(len(buffer))
                        if kernel.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(length)):
                            if os.path.normcase(buffer.value) == expected:
                                count += 1
                        else:
                            unknown = True
                    finally:
                        kernel.CloseHandle(handle)
            found = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        if ctypes.get_last_error() != 18:  # ERROR_NO_MORE_FILES
            unknown = True
    finally:
        kernel.CloseHandle(snapshot)
    return {'status': 'RUNNING' if count else 'UNKNOWN' if unknown else 'NOT_RUNNING',
            'matching_process_count': count}


def live_details(root, session, scope, timeout):
    """Only existing read tools; loaded host metadata and optional entitlement."""
    from .bridge import compatibility
    from .diagnostics import issue
    export = {'status': 'NOT_EVALUATED', 'export_verified': False}
    issues = []
    client = BridgeClient(root=root, timeout=timeout)
    try:
        caps = client.call('get_bridge_capabilities', {})
    except (BridgeError, PermissionError, OSError):
        return export, [issue('CAPABILITIES_UNAVAILABLE', 'warning')]
    if caps.get('session') != scope.get('session'):
        return export, [issue('HOST_SESSION_CHANGED')]
    host = caps.get('host')
    if (type(host) is not dict or host.get('name') != 'Cascadeur'
            or type(host.get('pid')) is not int or host['pid'] != session['pid']):
        return export, [issue('HOST_IDENTITY_MISMATCH')]
    label = host.get('bridge_package_version')
    session['host_package_version'] = label if type(label) is str and re.fullmatch(
        r'[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}(?:(?:a|b|rc)[0-9]{1,4})?', label) else 'NOT_REPORTED'
    match = compatibility.status(caps.get('write_contract'))
    session['live_write_compatibility'] = match
    if match != 'COMPATIBLE':
        issues.append(issue(match))
    operations = caps.get('operations')
    operation = operations.get('get_fbx_export_status') if type(operations) is dict else None
    if type(operation) is not dict or operation.get('classification') != 'read':
        return export, issues + [issue('EXPORT_STATUS_UNAVAILABLE', 'warning')]
    try:
        reply = client.call('get_fbx_export_status', {})
    except (BridgeError, PermissionError, OSError):
        return export, issues + [issue('EXPORT_STATUS_UNAVAILABLE', 'warning')]
    if reply.get('session') != scope.get('session'):
        session['live_write_compatibility'] = 'NOT_EVALUATED'
        return export, issues + [issue('HOST_SESSION_CHANGED')]
    if type(reply.get('export_available')) is not bool:
        return export, issues + [issue('EXPORT_STATUS_UNAVAILABLE', 'warning')]
    export['status'] = 'AVAILABLE_NOT_VALIDATED' if reply['export_available'] else 'EXPORT_UNAVAILABLE'
    if not reply['export_available']:
        issues.append(issue('EXPORT_UNAVAILABLE', 'warning'))
    return export, issues


def doctor(*, source=None, home=None, instance='c01', live=False, timeout=5.0):
    source = source_dir(source)
    sdk = package_version('mcp')
    result = {'ok': True, 'python': '.'.join(map(str, sys.version_info[:3])),
              'client_version': package_version('cascadeur-mcp'), 'mcp_sdk_version': sdk,
              'source': str(source), 'instance': instance, 'cross_machine_validation': 'NOT_VERIFIED',
              'mode': 'READ_ONLY_LIVE' if live else 'STATIC_ONLY',
              'python_supported': sys.version_info >= (3, 10),
              'application': {'status': 'NOT_CHECKED'},
              'export': {'status': 'NOT_EVALUATED', 'export_verified': False},
              'write_readiness': 'NOT_EVALUATED'}
    if home is not None:
        result['hook'] = inspect_hook(home, source)
        if live:
            result['application'] = inspect_application(home)
    root, scope = instance_root(instance), {}
    result['session'] = check_session(root, live=live, timeout=timeout, _scope=scope)
    result['session']['live_write_compatibility'] = 'NOT_EVALUATED'
    if live and result['session']['status'] == 'CONNECTED':
        result['export'], result['_live_issues'] = live_details(root, result['session'], scope, timeout)
    from .bridge.recovery import read as read_recovery
    from .diagnostics import issue
    try:
        fence = read_recovery(root)
        result['recovery'] = {'status':'FENCE_PRESENT_NATIVE_CHECK_REQUIRED' if fence else 'NO_PERSISTENT_FENCE',
                              'native_checkpoint_verified':False}
        if fence:
            result.setdefault('_live_issues', []).append(issue('RECOVERY_FENCE_PRESENT'))
    except Exception:
        result['recovery'] = {'status':'INVALID_RECOVERY_RECORD', 'native_checkpoint_verified':False}
        result.setdefault('_live_issues', []).append(issue('INVALID_RECOVERY_RECORD'))
    result['ok'] = (sdk != 'NOT_INSTALLED' and sys.version_info >= (3, 10)
                    and result['session']['ok'] and result.get('hook', {'ok': True})['ok'])
    from .diagnostics import explain
    return explain(result)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('doctor', 'install-host', 'uninstall-host'):
        cmd = sub.add_parser(command)
        cmd.add_argument('--source', help='Absolute source or site-packages directory containing cascadeur_mcp')
        cmd.add_argument('--cascadeur-home', required=command != 'doctor', help='Absolute Cascadeur installation directory')
        if command == 'doctor':
            cmd.add_argument('--instance', default=os.environ.get('CASCADEUR_MCP_INSTANCE', 'c01'))
            cmd.add_argument('--live', action='store_true', help='Read ping, scene, loaded contract and optional FBX entitlement')
            cmd.add_argument('--timeout', type=float, default=5.0)
            cmd.add_argument('--format', choices=('json', 'text'), default='json', help='JSON report or concise reason and next step')
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
    if args.command == 'doctor' and 'diagnostics' not in result:
        from .diagnostics import issue
        result['diagnostics'] = [issue(result['status'])]
    if getattr(args, 'format', 'json') == 'text':
        from .diagnostics import text_report
        print(text_report(result))
    else:
        print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
