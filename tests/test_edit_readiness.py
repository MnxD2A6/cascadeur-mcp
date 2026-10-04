"""Offline preflight contracts; real Cascadeur acceptance is recorded separately."""
import copy
import hashlib
from types import SimpleNamespace as NS

import pytest
from test_curve_edit import native
from cascadeur_mcp.bridge import animation, character, playback, semantics
from cascadeur_mcp.bridge.protocol import BridgeError, validate_params

METHOD = 'get_character_edit_readiness'
SID = hashlib.sha256(b'readiness-test.casc').hexdigest()[:32]
PARAMS = {'scene_id': SID, 'character_id': '7db06f9b-ac9f-4086-8ebb-e62608f5bad9',
          'frames': [6, 10], 'operation': 'offset_semantic_pose_sequence_preserving_curves',
          'roles': ['right_hand']}


@pytest.fixture
def ready(native, monkeypatch):
    monkeypatch.setattr(character, '_snapshots', {})
    monkeypatch.setattr(character, '_journals', {})
    monkeypatch.setattr(playback, '_run', None)
    monkeypatch.setattr(semantics, 'mapping', lambda *args: {
        'profile': 'synthetic', 'roles': {
            'right_hand': {'controls': {'center': {'control_id': 'hand'}}},
            'left_foot': {'controls': {'center': {'control_id': 'foot'}}}}})
    native.view = NS(get_path_name=lambda: 'readiness-test.casc')
    return native


def call(ready, **patch):
    params = validate_params(METHOD, {**PARAMS, **patch})
    return animation.dispatch(ready.view, ready.scene, METHOD, params)


def codes(result):
    return {check.get('code') for check in result['checks'] if check['status'] != 'PASS'}


def test_preflight_accepts_existing_hand_keys_without_consuming_capacity(ready):
    before = copy.deepcopy(ready.state)
    result = call(ready)
    assert result['status'] == 'PREFLIGHT_PASSED'
    assert result['capacity']['snapshot_slots_remaining'] == 16
    assert result['capacity']['transaction_slots_remaining'] == 8
    assert result['capacity']['edits_before_capacity_limit'] == 8
    assert result['advisory_only'] is True
    assert result['native_write_success'] == 'NOT_EVALUATED'
    assert result['target_feasibility'] == 'NOT_EVALUATED'
    assert result['external_playback'] == 'NOT_EVALUATED'
    assert character._snapshots == character._journals == {}
    assert ready.state == before


@pytest.mark.parametrize('fault,expected', [
    ('locked', 'UNSAFE_TRACK'), ('shared', 'UNSAFE_TRACK'),
    ('fk', 'UNSUPPORTED_RIG_MODE'), ('ai', 'UNSUPPORTED_AI_INTERPOLATION'),
    ('clamped', 'UNSUPPORTED_CLAMPED_RECOVERY'), ('key', 'CURVE_KEY_REQUIRED'),
    ('fixed', 'UNSUPPORTED_EDIT_TRACK'), ('frame', 'FRAME_OUT_OF_RANGE'),
    ('snapshot', 'SNAPSHOT_LIMIT'), ('transaction', 'TRANSACTION_LIMIT'),
    ('recovery', 'RECOVERY_REQUIRED'), ('playback', 'PLAYBACK_ACTIVE'),
    ('identity', 'SCENE_MISMATCH'), ('external_edit', 'EXTERNAL_EDIT_DETECTED'),
])
def test_known_blockers_are_reported_without_writes(ready, fault, expected):
    patch = {}
    layer = ready.layers['hand-track']
    if fault == 'locked': layer.is_locked = True
    if fault == 'shared': layer.obj_ids.append('another-character')
    if fault == 'fk': layer.sections[6].key.common.ik_fk = 1
    if fault == 'ai': layer.sections[6].interval.interpolation = 7
    if fault == 'clamped': layer.sections[6].interval.interpolation = 6
    if fault == 'key': layer.sections[6].key = None
    if fault == 'fixed': layer.sections[6].interval.interpolation = 4
    if fault == 'frame': patch['frames'] = [120]
    if fault == 'snapshot': character._snapshots.update({str(n): {} for n in range(16)})
    if fault in ('transaction', 'recovery', 'external_edit'):
        entries = [{'id': str(n), 'after': copy.deepcopy(ready.state)} for n in range(8 if fault == 'transaction' else 1)]
        character._journals[id(ready.scene)] = {'scene': ready.scene, 'entries': entries,
                                             'locked': fault == 'recovery'}
        if fault == 'external_edit': ready.state['values']['d:hand-data'][6][0] += 1
    if fault == 'playback': playback._run = {'status': 'playing'}
    if fault == 'identity': patch['scene_id'] = 'f'*32
    before = copy.deepcopy(ready.state)
    snapshots = copy.deepcopy(character._snapshots)
    result = call(ready, **patch)
    assert result['status'] == 'BLOCKED'
    assert expected in codes(result)
    assert character._snapshots == snapshots
    assert ready.state == before
    assert all('next_step' in x for x in result['checks'] if x['status'] != 'PASS')


def test_unreadable_native_state_is_unknown_not_ready(ready):
    ready.scene.layers_viewer = lambda: (_ for _ in ()).throw(RuntimeError('unavailable'))
    result = call(ready)
    assert result['status'] == 'UNKNOWN'
    assert 'CURVE_STATE_UNAVAILABLE' in codes(result)


def test_capacity_is_global_for_snapshots_and_scene_local_for_transactions(ready):
    character._snapshots.update({str(n): {} for n in range(15)})
    other = object()
    character._journals[id(other)] = {'scene': other, 'entries': [{}]*8, 'locked': True}
    result = call(ready)
    assert result['status'] == 'PREFLIGHT_PASSED'
    assert result['capacity']['edits_before_capacity_limit'] == 1
    assert result['capacity']['checkpoint_recommended'] is True
    assert id(ready.scene) not in character._journals


@pytest.mark.parametrize('operation', ['set_pose_sequence', 'offset_semantic_pose_sequence'])
def test_authoring_preflight_accepts_nonkey_frames(ready, operation):
    result = call(ready, operation=operation, frames=[5])
    assert result['status'] == 'PREFLIGHT_PASSED'


def test_curve_preflight_inspects_selected_roles_only_but_all_rig_tracks(ready):
    hand = call(ready)
    foot = call(ready, roles=['left_foot'])
    assert hand['status'] == 'PREFLIGHT_PASSED'
    assert foot['status'] == 'BLOCKED' and 'UNSUPPORTED_EDIT_TRACK' in codes(foot)


@pytest.mark.parametrize('patch', [
    {'frames': []}, {'frames': [True]}, {'frames': [6, 6]}, {'frames': list(range(9))},
    {'frames': [121]}, {'roles': []}, {'roles': ['hand']}, {'roles': ['right_hand']*2},
    {'operation': 'execute_python'}, {'operation': []}, {'code': 'anything'},
    {'scene_id': 'bad'}, {'character_id': 'Cascy'}, {'frames': [1.0]},
])
def test_preflight_parameters_fail_closed(patch):
    with pytest.raises(BridgeError, match='INVALID_PARAMS'):
        validate_params(METHOD, {**PARAMS, **patch})


def test_real_writer_still_rejects_track_change_after_successful_preflight(ready):
    assert call(ready)['status'] == 'PREFLIGHT_PASSED'
    ready.layers['hand-track'].is_locked = True
    with pytest.raises(BridgeError, match='UNSAFE_TRACK'):
        character.set_sequence(ready.view, ready.scene, ready.cid,
            [{'frame': 6, 'pose': {'hand': {'position': [0., 0., 0.]},
                                'foot': {'position': [0., 0., 0.]}}}])
    assert character._snapshots == character._journals == {}
