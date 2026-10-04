"""Advisory native reads, without permission tokens or recovery state mutation."""
from . import character, curve_edit, playback, semantics
from .protocol import BridgeError

NEXT = {
    'SCENE_MISMATCH': 'Rediscover the active saved scene and character IDs.',
    'SNAPSHOT_LIMIT': 'Preserve a native checkpoint; normally close/reopen and rediscover. Never delete snapshots to bypass this limit.',
    'TRANSACTION_LIMIT': 'Restore a valid session snapshot, or preserve a native checkpoint before a normal restart.',
    'RECOVERY_REQUIRED': 'Stop writes. Preserve a separate quarantine copy; recover from a previously verified native checkpoint. Restart alone is not recovery.',
    'EXTERNAL_EDIT_DETECTED': 'Stop editing. Inspect external changes and use a verified native checkpoint; do not traverse unknown Undo history.',
    'PLAYBACK_ACTIVE': 'Stop bridge-owned playback and verify stop before editing.',
    'FRAME_OUT_OF_RANGE': 'Select existing stored frames in the supported 0..120 range.',
    'UNSAFE_TRACK': 'Inspect locked/shared tracks; select a supported independent character without disabling rig constraints.',
    'CURVE_KEY_REQUIRED': 'Select existing keys on the edited tracks, or deliberately choose the key-authoring operation.',
    'UNSUPPORTED_EDIT_TRACK': 'Do not edit baked/FIXED tracks through the curve-preserving tool. Select supported controls.',
}

def inspect(view, scene, params):
    checks = []
    entry = character._journals.get(id(scene))
    used_snapshots = len(character._snapshots)
    used_transactions = len(entry['entries']) if entry is not None else 0
    remaining_snapshots = max(0, 16-used_snapshots)
    remaining_transactions = max(0, 8-used_transactions)
    remaining = min(remaining_snapshots, remaining_transactions)

    def issue(name, code, status='FAIL'):
        checks.append({'check': name, 'status': status, 'code': code,
            'next_step': NEXT.get(code, 'Inspect the reported native condition; use supported scene/rig/curve state. Do not force writes or automatically retry.')})

    def check(name, action):
        try:
            result = action()
        except BridgeError as exc:
            code = str(exc).split(':', 1)[0]
            unknown = code.endswith('_UNAVAILABLE') or code in ('NONFINITE_HOST_DATA', 'UNSUPPORTED_PROPERTY')
            issue(name, code, 'UNKNOWN' if unknown else 'FAIL')
            return None
        except Exception:
            issue(name, 'NATIVE_STATE_UNAVAILABLE', 'UNKNOWN')
            return None
        checks.append({'check': name, 'status': 'PASS'})
        return result

    def identity():
        if character.scene_id(view) != params['scene_id']:
            raise BridgeError('SCENE_MISMATCH')
        return True

    if not remaining_snapshots: issue('snapshot_capacity', 'SNAPSHOT_LIMIT')
    else: checks.append({'check': 'snapshot_capacity', 'status': 'PASS'})
    if not remaining_transactions: issue('transaction_capacity', 'TRANSACTION_LIMIT')
    else: checks.append({'check': 'transaction_capacity', 'status': 'PASS'})
    check('recovery_lock', lambda: character.require_recovered(scene))
    check('owned_playback', playback.require_idle)
    if check('scene_identity', identity):
        cid = params['character_id']
        rig = check('semantic_rig', lambda: semantics.mapping(view, scene, cid))
        def frames():
            count = scene.data_viewer().get_animation_size()
            if not 1 <= count <= 121:
                raise BridgeError('SCENE_LIMIT')
            if any(not 0 <= f < count for f in params['frames']):
                raise BridgeError('FRAME_OUT_OF_RANGE')
            return count
        count = check('stored_frames', frames)
        check('recoverable_interpolation', lambda: curve_edit.require_recoverable_curves(scene))
        def tracks():
            _, _, owned, _ = character.identify(scene, cid)
            character.writable_layers(scene, owned)
        check('character_tracks', tracks)
        if rig is not None and count is not None:
            def recovery_state():
                if params['operation'] == 'offset_semantic_pose_sequence_preserving_curves':
                    selected = {c['control_id'] for role in params['roles']
                                for c in rig['roles'][role]['controls'].values()}
                    state = curve_edit.preflight(scene, cid, params['frames'], selected).before
                else:
                    state = character.capture(scene)
                if entry is not None and entry['entries'] and not character.equivalent(state, entry['entries'][-1]['after']):
                    raise BridgeError('EXTERNAL_EDIT_DETECTED')
            check('recovery_state_and_edit_policy', recovery_state)
    status = ('BLOCKED' if any(x['status'] == 'FAIL' for x in checks) else
              'UNKNOWN' if any(x['status'] == 'UNKNOWN' for x in checks) else 'PREFLIGHT_PASSED')
    return {'scene_id': params['scene_id'], 'character_id': params['character_id'],
        'operation': params['operation'], 'frames': list(params['frames']), 'roles': list(params['roles']),
        'status': status, 'checks': checks, 'advisory_only': True,
        'capacity': {'snapshot_slots_remaining': remaining_snapshots,
            'transaction_slots_remaining': remaining_transactions,
            'edits_before_capacity_limit': remaining, 'checkpoint_recommended': remaining <= 1,
            'scope': 'snapshots are session-wide; transactions are per live scene; no slots reserved'},
        'target_feasibility': 'NOT_EVALUATED', 'external_playback': 'NOT_EVALUATED',
        'native_write_success': 'NOT_EVALUATED',
        'write_rechecks_required': True, 'automatic_retry_allowed': False}
