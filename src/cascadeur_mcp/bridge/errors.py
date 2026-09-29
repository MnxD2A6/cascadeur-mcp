"""Versioned error evidence. Error text is never proof that rollback occurred."""
import re

STATES = {'not_started', 'read_failed', 'outcome_unknown', 'rolled_back', 'recovery_required', 'completed'}
PHASES = {'client_validation', 'client_session', 'client_publish', 'client_response',
          'host_validation', 'host_dispatch', 'host_result', 'client_cleanup'}
ID = re.compile(r'[0-9a-f]{32}\Z')
CODE = re.compile(r'[A-Z][A-Z0-9_]{1,63}\Z')
MESSAGES = {
    'INVALID_PARAMS': 'Arguments failed validation; correct the input.',
    'UNKNOWN_METHOD': 'This operation is not in the loaded bridge allowlist.',
    'BRIDGE_UNAVAILABLE': 'No host session is available; start the matching Cascadeur instance.',
    'WRITE_OUTCOME_UNKNOWN': 'A write may have executed. Read back before retrying.',
    'BRIDGE_TIMEOUT': 'The host did not reply before the deadline.',
    'RECOVERY_REQUIRED': 'Verified recovery is unavailable; stop editing and inspect the preserved scene.',
    'SCENE_MISMATCH': 'The active scene does not match the expected identity.',
    'INVALID_RESPONSE': 'The response failed protocol validation.',
    'INVALID_ERROR_DETAILS': 'Host error metadata was invalid; no recovery guarantee is accepted.',
    'CLEANUP_FAILED': 'Temporary transport file cleanup failed.',
    'PERMISSION_DENIED': 'A required operation was denied by the operating system.',
    'HOST_UPGRADE_REQUIRED': 'The host has no write contract. Update and restart the host and MCP server together.',
    'INVALID_HOST_CONTRACT': 'Host compatibility metadata is invalid. Check the installation and restart both processes.',
    'INCOMPATIBLE_HOST': 'Host and client write contracts differ. Install matching code and restart both processes.',
    'INCOMPATIBLE_CLIENT': 'The client write contract is missing or incompatible. Update and restart the MCP server.',
    'HOST_SESSION_CHANGED': 'The host session changed before publication. Rediscover the active host before writing.',
}


class BridgeError(RuntimeError):
    """Legacy string plus optional typed execution evidence, set by trusted code."""
    def __init__(self, message, *, details=None, execution_state=None,
                 rollback_verified=None, recovery_snapshot_id=None):
        super().__init__(message)
        self.details = details
        self.execution_state = execution_state
        self.rollback_verified = rollback_verified
        self.recovery_snapshot_id = recovery_snapshot_id


def error_code(exc):
    if isinstance(exc, BridgeError):
        candidate = str(exc).partition(':')[0]
        if CODE.fullmatch(candidate):
            return candidate
    if isinstance(exc, PermissionError):
        return 'PERMISSION_DENIED'
    if isinstance(exc, OSError):
        return 'FILESYSTEM_ERROR'
    return 'INTERNAL_ERROR'


def action_for(state, code):
    if state == 'recovery_required':
        return 'stop_writes_and_recover_preserved_scene'
    if state in ('outcome_unknown', 'completed'):
        return 'read_back_before_any_retry'
    if state == 'rolled_back':
        return 'inspect_failure_and_correct_input_before_retry'
    if code == 'BRIDGE_UNAVAILABLE':
        return 'start_matching_host'
    return 'inspect_error_and_correct_preconditions'


def describe_error(exc, *, operation, is_write, phase, request_id=None,
                   session_id=None, completed=False, legacy=False):
    code = error_code(exc)
    rollback = None
    snapshot = None
    evidence = 'phase_boundary'
    state = 'outcome_unknown' if is_write else 'read_failed'
    if phase in ('client_validation', 'client_session', 'host_validation'):
        state = 'not_started'
    # Rejecting a replay says nothing about execution of the original request.
    if code == 'DUPLICATE_REQUEST' and is_write:
        state = 'outcome_unknown'
    if completed:
        state = 'completed'
    explicit = getattr(exc, 'execution_state', None)
    verified = getattr(exc, 'rollback_verified', None)
    if explicit == 'rolled_back' and verified is True:
        state, rollback, evidence = explicit, True, 'explicit_host_state'
    elif explicit == 'recovery_required' and (verified is False or verified is None):
        state, rollback, evidence = explicit, verified, 'explicit_host_state'
    elif explicit == 'not_started':
        state, evidence = explicit, 'explicit_preflight'
    value = getattr(exc, 'recovery_snapshot_id', None)
    if isinstance(value, str) and ID.fullmatch(value):
        snapshot = value
    if legacy:
        state = 'outcome_unknown' if is_write else 'read_failed'
        rollback, snapshot, evidence = None, None, 'legacy_host_no_state_evidence'
    return {'schema_version': 1, 'code': code,
            'message': MESSAGES.get(code, 'Operation failed; inspect the code and local host diagnostics.'),
            'operation': operation, 'phase': phase, 'execution_state': state,
            'rollback_verified': rollback, 'recovery_snapshot_id': snapshot,
            'automatic_retry_allowed': False, 'recommended_action': action_for(state, code),
            'request_id': request_id, 'session_id': session_id,
            'evidence': evidence, 'cleanup_failed': False}


def validate_remote_error(value, *, operation, is_write):
    """Accept a bounded contract; never promote strings or unknown versions."""
    if type(value) is not dict or type(value.get('schema_version')) is not int or value['schema_version'] != 1:
        return None
    if (value.get('operation') != operation or type(value.get('phase')) is not str
            or value['phase'] not in PHASES):
        return None
    code, state = value.get('code'), value.get('execution_state')
    if not isinstance(code, str) or not CODE.fullmatch(code) or type(state) is not str or state not in STATES:
        return None
    rollback = value.get('rollback_verified')
    if rollback is not None and type(rollback) is not bool:
        return None
    if (state == 'rolled_back') != (rollback is True):
        return None
    if state == 'read_failed' and is_write:
        return None
    if code == 'DUPLICATE_REQUEST' and is_write and state != 'outcome_unknown':
        return None
    if value.get('automatic_retry_allowed') is not False:
        return None
    sid = value.get('recovery_snapshot_id')
    if sid is not None and (not isinstance(sid, str) or not ID.fullmatch(sid)):
        return None
    evidence = value.get('evidence')
    if type(evidence) is not str or evidence not in {'phase_boundary', 'explicit_host_state', 'explicit_preflight'}:
        return None
    if state in ('rolled_back', 'recovery_required') and evidence != 'explicit_host_state':
        return None
    phase = value['phase']
    allowed = {
        'host_validation': {('not_started', 'phase_boundary'), ('outcome_unknown', 'phase_boundary')},
        'host_dispatch': {('not_started', 'explicit_preflight'), ('read_failed', 'phase_boundary'),
                          ('outcome_unknown', 'phase_boundary'), ('rolled_back', 'explicit_host_state'),
                          ('recovery_required', 'explicit_host_state')},
        'host_result': {('completed', 'phase_boundary')},
    }
    if (state, evidence) not in allowed.get(phase, set()):
        return None
    if not is_write and state in ('outcome_unknown', 'rolled_back', 'recovery_required'):
        return None
    if rollback is False and state != 'recovery_required':
        return None
    # Rebuild rather than echo untrusted host messages or extra fields.
    result = describe_error(BridgeError(code), operation=operation, is_write=is_write, phase=value['phase'])
    result.update(execution_state=state, rollback_verified=rollback,
                  recovery_snapshot_id=sid, evidence=evidence,
                  recommended_action=action_for(state, code))
    return result
