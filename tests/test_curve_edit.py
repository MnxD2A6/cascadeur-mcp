"""Synthetic contract regressions; native curve acceptance is separate."""
import copy
from types import SimpleNamespace as NS
import sys

import pytest

from cascadeur_mcp.bridge.protocol import BridgeError, validate_params
from cascadeur_mcp.tools.animation_schema import WRITE_METHODS

METHOD = 'offset_semantic_pose_sequence_preserving_curves'
PARAMS = {'scene_id': 'a'*32, 'character_id': '7db06f9b-ac9f-4086-8ebb-e62608f5bad9',
          'frames': [6, 10], 'offsets': {'right_hand': [-.05, 0., 0.]}}


def test_new_tool_is_a_strict_bounded_write():
    assert validate_params(METHOD, PARAMS) == PARAMS
    assert METHOD in WRITE_METHODS


@pytest.mark.parametrize('patch', [
    {'frames': []}, {'frames': [10, 10]}, {'frames': [True]}, {'frames': list(range(9))},
    {'frames': [121]}, {'offsets': {}}, {'offsets': {'right_hand': [float('nan'), 0, 0]}},
    {'offsets': {'right_hand': [10**400, 0, 0]}}, {'offsets': {'hand': [0, 0, 0]}},
    {'allow_unsafe': True}, {'code': 'do anything'}, {'interpolation': 'LINEAR'},
])
def test_new_tool_rejects_invalid_input(patch):
    with pytest.raises(BridgeError, match='INVALID_PARAMS'):
        validate_params(METHOD, {**PARAMS, **patch})


@pytest.fixture
def native(monkeypatch):
    from cascadeur_mcp.bridge import curve_edit, character
    sections = {f: NS(interval=NS(interpolation=2, common=NS(ik_fk=0, fixation=0),
                                 description_for_ai_interpolation=''),
                      key=NS(common=NS(ik_fk=0, fixation=0), label=None, tangents=0,
                             left_weight_velocity=.2, right_weight_velocity=.45))
                for f in (0, 6, 10, 22)}
    hand = NS(obj_ids=['hand'], sections=sections, is_locked=False)
    foot = copy.deepcopy(hand); foot.obj_ids=['foot']
    for f in (0, 6, 10): foot.sections[f].interval.interpolation = 4
    layers = {'hand-track': hand, 'foot-track': foot}
    manager = NS(count=0, get_stacked_layers_count=lambda: manager.count)
    csc = NS(additive_layers=NS(get_manager=lambda scene: manager),
             layers=NS(CyclesViewer=lambda layer: NS(any_cycles_exist_in_frames=lambda a, b: False)))
    monkeypatch.setitem(sys.modules, 'csc', csc)
    state = {'count': 23, 'objects': {}, 'static': {},
             'tracks': {lid: {'objects': layer.obj_ids, 'sections': character.sections(layer)}
                        for lid, layer in layers.items()},
             'values': {'d:hand-data': [[float(f), 0., 0.] for f in range(23)],
                        'd:foot-data': [[0., 0., 0.] for f in range(23)]}}
    scene = NS(data_viewer=lambda: NS(get_animation_size=lambda: 23,
                                      get_all_data_id=lambda obj: [obj+'-data']),
               model_viewer=lambda: NS(get_objects=lambda: ['hand','foot']),
               behaviour_viewer=lambda: NS(get_behaviour_by_name=lambda obj,name:obj,
                                          get_behaviour_data=lambda obj,name:obj+'-data'),
               layers_viewer=lambda: NS(layers_map=lambda: layers))
    monkeypatch.setattr(character, 'identify', lambda s, cid: (None, {}, {'hand','foot'}, {'hand':'hand','foot':'foot'}))
    monkeypatch.setattr(character, 'capture', lambda s: copy.deepcopy(state))
    monkeypatch.setattr(character, 'geometry', lambda s,cid,f: {'max_connection_anchor_error':0.})
    return NS(module=curve_edit, scene=scene, cid=PARAMS['character_id'],
              layers=layers, manager=manager, state=state, csc=csc)


def test_existing_keys_and_unedited_fixed_tracks_are_accepted(native):
    native.module.preflight(native.scene, native.cid, [6,10], {'hand'})


@pytest.mark.parametrize('mode', [0, 1, 2, 3])
@pytest.mark.parametrize('weights', [(.01, .99), (.2, .45)])
def test_classic_modes_retain_easing_and_step_endpoint(native, mode, weights):
    from cascadeur_mcp.bridge import character
    layer = native.layers['hand-track']
    for frame, section in layer.sections.items():
        section.interval.interpolation = 3 if frame == 22 else mode
        section.key.left_weight_velocity, section.key.right_weight_velocity = weights
    native.state['tracks']['hand-track']['sections'] = character.sections(layer)
    guard = native.module.preflight(native.scene, native.cid, [6, 10], {'hand'})
    changed = copy.deepcopy(native.state)
    changed['values']['d:hand-data'][6][0] += .05
    guard.verify(changed, [])
    assert guard.report()['interpolation_easing_tangent_mode'] == 'exact'
    layer.sections[6].key.right_weight_velocity += .001
    with pytest.raises(BridgeError, match='CURVE_METADATA_CHANGED'):
        guard.verify(changed, [])


@pytest.mark.parametrize('field', ['left_weight_velocity', 'right_weight_velocity'])
def test_nonfinite_native_easing_fails_closed(native, field):
    setattr(native.layers['hand-track'].sections[6].key, field, float('nan'))
    with pytest.raises(BridgeError, match='CURVE_STATE_UNAVAILABLE'):
        native.module.preflight(native.scene, native.cid, [6, 10], {'hand'})


@pytest.mark.parametrize('reader', ['get_stacked_layers_count', 'CyclesViewer'])
def test_native_state_reader_failure_is_not_treated_as_absence(native, reader):
    def unavailable(*args):
        raise RuntimeError('synthetic native read failure')
    if reader == 'get_stacked_layers_count':
        native.manager.get_stacked_layers_count = unavailable
    else:
        native.csc.layers.CyclesViewer = unavailable
    with pytest.raises(BridgeError, match='CURVE_STATE_UNAVAILABLE'):
        native.module.preflight(native.scene, native.cid, [6, 10], {'hand'})


@pytest.mark.parametrize('fault,code', [
    ('missing_key','CURVE_KEY_REQUIRED'), ('additive','UNSUPPORTED_ADDITIVE_LAYERS'),
    ('custom_tangent','UNSUPPORTED_CUSTOM_TANGENTS'), ('selected_fixed','UNSUPPORTED_EDIT_TRACK'),
    ('none','UNSUPPORTED_EDIT_TRACK'), ('ai','UNSUPPORTED_EDIT_TRACK'),
    ('locked','UNSAFE_TRACK'), ('shared','UNSAFE_TRACK'), ('cycle','UNSUPPORTED_CYCLES'),
    ('missing_api','CURVE_STATE_UNAVAILABLE'),
])
def test_unsupported_curve_states_fail_closed_before_write(native, fault, code):
    hand=native.layers['hand-track']
    if fault=='missing_key': hand.sections[6].key=None
    if fault=='additive': native.manager.count=1
    if fault=='custom_tangent': hand.sections[6].key.tangents=1
    if fault=='selected_fixed': hand.sections[0].interval.interpolation=4
    if fault=='none': hand.sections[0].interval.interpolation=5
    if fault=='ai': hand.sections[0].interval.interpolation=7
    if fault=='locked': hand.is_locked=True
    if fault=='shared': hand.obj_ids.append('other-character')
    if fault=='cycle': native.csc.layers.CyclesViewer=lambda layer: NS(any_cycles_exist_in_frames=lambda a,b: True)
    if fault=='missing_api': del native.csc.additive_layers
    with pytest.raises(BridgeError, match=code):
        native.module.preflight(native.scene,native.cid,[6,10],{'hand'})


def test_postcondition_detects_weight_or_key_layout_damage(native):
    guard=native.module.preflight(native.scene,native.cid,[6,10],{'hand'})
    changed=copy.deepcopy(native.state)
    changed['tracks']['hand-track']['sections']['6']['key']['right_weight_velocity']=.3
    with pytest.raises(BridgeError, match='CURVE_METADATA_CHANGED'):
        guard.verify(changed, [])


def test_preflight_keeps_its_own_metadata_copy(native):
    guard=native.module.preflight(native.scene,native.cid,[6,10],{'hand'})
    native.layers['hand-track'].sections[6].key.left_weight_velocity=.8
    with pytest.raises(BridgeError, match='CURVE_METADATA_CHANGED'):
        guard.verify(native.state, [])


def test_unedited_tracks_need_not_share_edited_key_frames(native):
    del native.layers['foot-track'].sections[6]
    native.state['tracks']['foot-track']['sections'].pop('6')
    native.module.preflight(native.scene,native.cid,[6,10],{'hand'})


@pytest.mark.parametrize('channel,frame,code', [
    ('d:foot-data',5,'PROTECTED_CURVE_DATA_CHANGED'),
    ('d:hand-data',22,'UNEDITED_KEY_CHANGED'),
])
def test_protected_baked_values_and_other_keys_cannot_change(native,channel,frame,code):
    guard=native.module.preflight(native.scene,native.cid,[6,10],{'hand'})
    changed=copy.deepcopy(native.state)
    changed['values'][channel][frame][0]+=.5
    with pytest.raises(BridgeError, match=code):
        guard.verify(changed, [])


def test_edited_key_and_adjacent_path_may_change_with_metadata_retained(native):
    guard=native.module.preflight(native.scene,native.cid,[6,10],{'hand'})
    changed=copy.deepcopy(native.state)
    for frame in (5,6,7,9,10,11): changed['values']['d:hand-data'][frame][0]+=.05
    guard.verify(changed, [])
    assert guard.report()['fixed_tracks_protected']==1
    assert guard.report()['frames_verified']==23
    assert guard.report()['trajectory_shape_preserved'] is False


def test_full_clip_geometry_not_only_edited_frames_is_checked(native,monkeypatch):
    from cascadeur_mcp.bridge import character
    guard=native.module.preflight(native.scene,native.cid,[6,10],{'hand'})
    monkeypatch.setattr(character,'geometry',lambda s,cid,f: {'max_connection_anchor_error':.2 if f==7 else 0.})
    with pytest.raises(BridgeError,match='INTERPOLATED_RIG_CONNECTION_ERROR'):
        guard.verify(native.state, [])


def test_semantic_write_delegates_only_selected_channels_and_no_layer_edits(monkeypatch):
    from cascadeur_mcp.bridge import semantics,curve_edit,character
    rig={'roles':{'right_hand':{'controls':{'center':{'control_id':'h1'},'direction':{'control_id':'h2'}}}},
         'profile':'synthetic','fingerprint':'synthetic','coordinate_space':'world'}
    baseline={'h1':{'position':[1.,2.,3.]},'h2':{'position':[2.,2.,3.]},'unselected':{'position':[0.,0.,0.]}}
    calls=[]
    guard=NS(verify=lambda after,poses:None,verify_recovery=lambda:None,report=lambda:{'verified':True})
    monkeypatch.setattr(character,'scene_id',lambda view:PARAMS['scene_id'])
    monkeypatch.setattr(semantics,'mapping',lambda *args:rig)
    monkeypatch.setattr(semantics,'_check_frames',lambda *args:None)
    monkeypatch.setattr(character,'get_pose',lambda *args,**kwargs:{'pose':copy.deepcopy(baseline)})
    monkeypatch.setattr(curve_edit,'preflight',lambda s,cid,frames,ids:guard)
    from cascadeur_mcp.tools import character_schema
    monkeypatch.setattr(character_schema,'validate',lambda params:None)
    monkeypatch.setattr(semantics,'get_pose',lambda *args,**kwargs:{'actual_solved':True})
    def write(view,scene,cid,entries,**kwargs):
        calls.append((entries,kwargs))
        poses=[{'frame':e['frame'],'pose':copy.deepcopy(e['pose'])} for e in entries]
        # Native set_sequence checks before and after commit. Do not suppress
        # mandatory verification with a partial transaction double.
        kwargs['postcondition']({},poses)
        poses[-1]['pose']['h1']['position'][1]+=.01
        kwargs['postcondition']({},poses)
        return {'native_poses':poses,'snapshot_id':'c'*32}
    monkeypatch.setattr(character,'set_sequence',write)
    result=semantics.dispatch(None,None,METHOD,PARAMS)
    assert len(calls)==1
    entries,kwargs=calls[0]
    assert kwargs['write_control_ids']=={'h1','h2'}
    assert kwargs['preserve_existing_keys'] is True
    assert callable(kwargs['postcondition'])
    assert 'configure_tracks' not in kwargs
    assert [e['frame'] for e in entries]==[6,10]
    for entry in entries:
        assert entry['pose']['unselected']==baseline['unselected']
        assert entry['pose']['h1']['position']==[.95,2.,3.]
    assert result['curve_preservation']['verified'] is True
    assert result['edit_impact']['frames'][-1]['direct_roles']['right_hand']['slots']['center']['target_error']==pytest.approx(.01)
    assert result['edit_impact']['protection']['verified'] is True
    failure=BridgeError('CHARACTER_POSE_FAILED',execution_state='rolled_back',rollback_verified=True)
    def fail(*args,**kwargs): raise failure
    monkeypatch.setattr(character,'set_sequence',fail)
    with pytest.raises(BridgeError) as caught: semantics.dispatch(None,None,METHOD,PARAMS)
    assert caught.value is failure


def test_solver_coupling_at_requested_key_is_allowed_but_other_keys_protected(native):
    del native.layers['foot-track']
    native.layers['hand-track'].obj_ids.append('foot')
    native.state['tracks'].pop('foot-track')
    native.state['tracks']['hand-track']['objects']=['hand','foot']
    guard=native.module.preflight(native.scene,native.cid,[6,10],{'hand'})
    changed=copy.deepcopy(native.state)
    changed['values']['d:foot-data'][6][0]+=.5
    guard.verify(changed,[])
    changed['values']['d:foot-data'][22][0]+=.5
    with pytest.raises(BridgeError,match='UNEDITED_KEY_CHANGED'):
        guard.verify(changed,[])


def test_external_custom_tangent_is_rejected(native):
    outside=copy.deepcopy(native.layers['hand-track']);outside.obj_ids=['outside']
    outside.sections[6].key.tangents=1
    native.layers['outside-track']=outside
    with pytest.raises(BridgeError,match='UNSUPPORTED_CUSTOM_TANGENTS'):
        native.module.preflight(native.scene,native.cid,[6,10],{'hand'})


@pytest.mark.parametrize('location', ['selected', 'unedited', 'external'])
def test_clamped_recovery_is_refused_before_snapshot(native, monkeypatch, location):
    from cascadeur_mcp.bridge import character
    layer = native.layers['hand-track' if location == 'selected' else 'foot-track']
    if location == 'external':
        layer = copy.deepcopy(layer)
        layer.obj_ids = ['outside']
        native.layers['outside-track'] = layer
    layer.sections[6].interval.interpolation = 6
    captures = []
    def capture(scene):
        captures.append(scene)
        return copy.deepcopy(native.state)
    monkeypatch.setattr(character, 'capture', capture)
    with pytest.raises(BridgeError, match='UNSUPPORTED_CLAMPED_RECOVERY') as caught:
        native.module.preflight(native.scene, native.cid, [6, 10], {'hand'})
    assert caught.value.execution_state == 'not_started'
    assert captures == []


@pytest.mark.parametrize('writer', ['points', 'fingers'])
def test_regular_character_writes_also_refuse_clamped_before_snapshot(native, monkeypatch, writer):
    from cascadeur_mcp.bridge import character, hands
    native.layers['foot-track'].sections[6].interval.interpolation = 6
    snapshots = []
    def snapshot(*args):
        snapshots.append(True)
        raise BridgeError('SNAPSHOT_STARTED: write preflight was missed')
    monkeypatch.setattr(character, 'save_snapshot', snapshot)
    if writer == 'points':
        entries = [{'frame': 6, 'pose': {key: {'position': [0., 0., 0.]}
                                        for key in ('hand', 'foot')}}]
        call = lambda: character.set_sequence(None, native.scene, native.cid, entries)
    else:
        call = lambda: hands.write(None, native.scene, native.cid,
                                   [{'frame': 6, 'hands': {'right': {'index1': [1., 0., 0., 0.]}}}])
    with pytest.raises(BridgeError, match='UNSUPPORTED_CLAMPED_RECOVERY') as caught:
        call()
    assert caught.value.execution_state == 'not_started'
    assert snapshots == []


def test_extra_metadata_damage_cannot_report_verified_rollback(native):
    from cascadeur_mcp.bridge import character
    guard=native.module.preflight(native.scene,native.cid,[6,10],{'hand'})
    native.layers['hand-track'].sections[6].interval.description_for_ai_interpolation='changed'
    journal={'locked':False}
    error=character._transaction_failure(native.scene,native.state,journal,
                                       BridgeError('CURVE_METADATA_CHANGED'),'c'*32,
                                       'CHARACTER_POSE_FAILED',guard.verify_recovery)
    assert error.execution_state=='recovery_required'
    assert error.rollback_verified is False
    assert journal['locked'] is True
