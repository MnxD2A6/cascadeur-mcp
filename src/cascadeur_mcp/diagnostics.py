"""Fixed, shareable doctor explanations; never include raw host error text."""

ADVICE = {
    'INVALID_INSTANCE': ('The instance name is invalid.', 'Use an instance name starting with a lowercase letter, followed by lowercase letters, digits, underscores or hyphens (at most 32 characters). Match it on both peers.'),
    'INVALID_SOURCE': ('The selected source does not contain the required bridge package files.', 'Use the directory containing cascadeur_mcp, such as checkout src or this environment\'s site-packages.'),
    'INVALID_CASCADEUR_LAYOUT': ('The selected directory does not match the supported Windows installation layout.', 'Set --cascadeur-home to the directory containing cascadeur.exe and resources/scripts/python/events/application_started.'),
    'ABSOLUTE_PATH_REQUIRED': ('A configured path is relative or contains parent traversal.', 'Supply an absolute local source/installation path without parent traversal.'),
    'INVALID_TIMEOUT': ('The per-request timeout is invalid.', 'Set --timeout to a finite number greater than zero and at most 20 seconds.'),
    'FILESYSTEM_ERROR': ('A required local file operation failed.', 'Check the source, installation and runtime paths and permissions locally; do not delete the runtime to bypass this error.'),
    'LOCALAPPDATA_MISSING': ('Windows local application data could not be located.', 'Run the external Python environment in your normal Windows user session with LOCALAPPDATA available.'),
    'HOOK_TOO_LARGE': ('The existing startup file exceeds the inspection limit.', 'Preserve the file and review it locally before changing the installation.'),
    'CASCADEUR_NOT_RUNNING': ('The selected Cascadeur installation is not running.', 'Start Cascadeur from this installation, open a disposable saved scene, then run doctor --live again.'),
    'BRIDGE_NOT_DISCOVERED': ('Cascadeur is running but no bridge session was discovered for this instance.', 'Wait for startup; check the hook source and matching CASCADEUR_MCP_INSTANCE. Restart Cascadeur normally if its Python modules changed.'),
    'NO_DESCRIPTOR': ('No bridge session was found; host startup has not been verified.', 'Start Cascadeur, open a scene and check the hook and instance name. Include --cascadeur-home to inspect the selected installation.'),
    'HOOK_NOT_INSTALLED': ('The bridge startup hook is missing.', 'Close Cascadeur normally, preview install-host --cascadeur-home <installation>, then apply that preview with --apply.'),
    'HOOK_REVIEW_REQUIRED': ('An existing startup hook differs from the managed template.', 'Preserve the file and review its source locally. A live connection can work with a legacy hook; never force-overwrite it.'),
    'INCOMPATIBLE_HOST': ('The responding host and this client have different write contracts.', 'Update both client and host to matching source, then restart Cascadeur and the MCP client. Do not edit session files to bypass this check.'),
    'HOST_UPGRADE_REQUIRED': ('The responding host has no write contract.', 'Upgrade the host and client together, then restart both processes. Reads alone do not establish write compatibility.'),
    'INVALID_HOST_CONTRACT': ('The responding host supplied an invalid write contract.', 'Check the configured source paths and restart both processes using matching code.'),
    'HOST_IDENTITY_MISMATCH': ('A responding host identity did not match this diagnostic session.', 'Check the installation and instance; rediscover the host after normal restart.'),
    'HOST_SESSION_CHANGED': ('The host session changed during these checks.', 'Allow startup/restart to finish, then deliberately rerun the read-only diagnostic. Do not reuse old scene or snapshot IDs.'),
    'CAPABILITIES_UNAVAILABLE': ('Scene reads succeeded but the loaded host contract could not be checked.', 'Use a host supporting get_bridge_capabilities and restart both processes. Treat write compatibility as unverified.'),
    'EXPORT_UNAVAILABLE': ('The current Cascadeur session reports no FBX export entitlement.', 'Check the official license in Cascadeur and use its supported sync/sign-in or normal restart flow. Other animation tools can still work.'),
    'EXPORT_STATUS_UNAVAILABLE': ('FBX entitlement could not be verified.', 'Open a saved disposable scene and check get_fbx_export_status on a supported host. No export was attempted.'),
    'EMPTY_SCENE': ('The responding scene contains no objects.', 'Open a saved compatible character scene before trying character tools.'),
    'BRIDGE_TIMEOUT': ('The host did not reply within the per-request deadline.', 'Check whether Cascadeur is busy or waiting for a dialog, and verify the configured instance. This read timeout does not establish that the process is dead.'),
    'BRIDGE_UNAVAILABLE': ('A host session became unavailable.', 'Start the matching Cascadeur instance and verify its startup hook.'),
    'INVALID_DESCRIPTOR': ('The session descriptor is malformed or unsupported.', 'Check the installation and restart the host normally; preserve local evidence and never patch credentials or compatibility fields.'),
    'INVALID_SCENE_RESPONSE': ('The scene response failed validation.', 'Check the host source and matching version, then restart and use a saved disposable scene.'),
    'HOST_ERROR': ('The host rejected a scene read.', 'Open a saved scene and inspect the local Cascadeur event log. Do not publish raw logs or scene data.'),
    'BRIDGE_ERROR': ('The read connection failed validation.', 'Check the selected source, host startup and instance; preserve the redacted report.'),
    'PERMISSION_DENIED': ('The operating system denied a required operation.', 'Check permissions on the installation and private runtime directory. Keep runtime access restricted to its owner.'),
    'UNSAFE_PATH': ('A configured path violates the local path safety checks.', 'Use an absolute local path without symlinks, junctions or parent traversal.'),
    'SDK_NOT_INSTALLED': ('The official MCP Python SDK is not installed in this environment.', 'Run this environment\'s Python -m pip install -e . from the checkout, then Python -m pip check.'),
    'PYTHON_UNSUPPORTED': ('This Python version is unsupported.', 'Create the external environment with Python 3.10 or newer; Python 3.12 was locally tested.'),
}


def issue(code, severity='error'):
    message, next_step = ADVICE.get(code, ('A local configuration check failed.', 'Review the setup guide and the selected Python/source paths.'))
    return {'code': code, 'severity': severity, 'message': message, 'next_step': next_step}


def explain(result):
    """Derive causes only from observations; unknown never becomes not-running."""
    issues = list(result.pop('_live_issues', []))
    hook = result.get('hook', {})
    if hook.get('status') == 'NOT_INSTALLED':
        issues.append(issue('HOOK_NOT_INSTALLED'))
    elif hook and not hook.get('ok'):
        issues.append(issue('HOOK_REVIEW_REQUIRED'))
    session = result['session']
    if not session['ok']:
        code = session['status']
        if code == 'NO_DESCRIPTOR':
            code = {'NOT_RUNNING': 'CASCADEUR_NOT_RUNNING', 'RUNNING': 'BRIDGE_NOT_DISCOVERED'}.get(
                result['application']['status'], code)
        issues.append(issue(code))
    if result['mcp_sdk_version'] == 'NOT_INSTALLED':
        issues.append(issue('SDK_NOT_INSTALLED'))
    if result['python_supported'] is False:
        issues.append(issue('PYTHON_UNSUPPORTED'))
    if session.get('status') == 'CONNECTED' and session.get('object_count') == 0:
        issues.append(issue('EMPTY_SCENE', 'warning'))
    result['diagnostics'] = issues
    result['ok'] = result['ok'] and not any(item['severity'] == 'error' for item in issues)
    result['status'] = ('ACTION_REQUIRED' if not result['ok'] else
                        'STATIC_CHECK_ONLY' if result['mode'] == 'STATIC_ONLY' else
                        'CONNECTED_WITH_WARNINGS' if issues else 'CONNECTED')
    return result


def text_report(result):
    lines = [f"Cascadeur MCP doctor: {result.get('status', 'UNKNOWN')}"]
    session = result.get('session', {})
    if session:
        lines += [f"Client: {result.get('client_version', 'NOT_REPORTED')} | Host: {session.get('host_package_version', 'NOT_REPORTED')}",
                  f"Connection: {session['status']} | Write contract: {session.get('live_write_compatibility', 'NOT_EVALUATED')}",
                  f"FBX: {result['export']['status']} | Rig / write readiness: NOT_EVALUATED"]
    for item in result.get('diagnostics', [issue(result.get('status', 'UNKNOWN'))] if not session else []):
        lines.extend([f"[{item['severity']}] {item['code']}: {item['message']}", f"Next: {item['next_step']}"])
    if session:
        lines.append('Read-only diagnostic; no scene edits or FBX export. Other-machine host connection remains unverified.')
    return '\n'.join(lines)
