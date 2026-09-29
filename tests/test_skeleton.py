"""Phase 3 safety regression only. Live hierarchy evidence is separate."""
from types import SimpleNamespace as NS
import sys
import pytest
from cascadeur_mcp.bridge.protocol import validate_params, BridgeError
from cascadeur_mcp.bridge import skeleton

B = {'scene':'test.casc','root':'Root','frame':10}


@pytest.mark.parametrize('method,args', [
    ('get_pose',{'frame':0}),
    ('get_pose',{'frame':0,'root':'Root','objects':['Root']}),
    ('get_pose',{'frame':0,'root':''}),
    ('set_pose',{**B,'pose_data':{}}),
    ('set_pose',{**B,'pose_data':{'Joint':{}}}),
    ('set_pose',{**B,'pose_data':{'Joint':{'position':[1,2]}}}),
    ('set_pose',{**B,'pose_data':{'Joint':{'rotation_wxyz':[0,0,0,0]}}}),
    ('set_pose',{**B,'pose_data':{'Joint':{'position':[float('nan'),0,0]}}}),
    ('set_pose',{**B,'pose_data':{'Joint':{'position':[True,0,0]}}}),
    ('set_pose',{**B,'pose_data':{'Joint':{'code':'anything'}}}),
    ('set_pose',{**B,'pose_data':{'Joint':{'position':[0,0,0]}},'space':'screen'}),
    ('set_pose',{**B,'pose_data':{str(i):{'position':[0,0,0]} for i in range(33)}}),
    ('set_pose',{**B,'pose_data':{'bad\nname':{'position':[0,0,0]}}}),
    ('save_pose_snapshot',{'scene':'test.casc','root':'Root','path':'C:/outside'}),
    ('restore_pose_snapshot',{'scene':'test.casc','snapshot_id':'../outside'}),
    ('restore_pose_snapshot',{'scene':'test.casc','snapshot_id':True}),
    ('restore_pose_snapshot',{'scene':'test.casc','snapshot_id':'a'*32,'pose_data':{}}),
    ('set_local_transform',{**B,'object':'Joint'}),
    ('set_global_transform',{**B,'object':'Joint','rotation_wxyz':[2,0,0,0]}),
])
def test_reject_unsafe_skeleton_input(method,args):
    with pytest.raises(BridgeError,match='INVALID_PARAMS'):
        validate_params(method,args)


def test_bounded_batch_accepts_multiple_joints():
    args={**B,'pose_data':{'Hips':{'rotation_wxyz':[1,0,0,0]},'Forearm':{'position':[12,0,0]}}}
    assert validate_params('set_pose',args)==args


def test_snapshot_limit_no_capture(monkeypatch):
    monkeypatch.setattr(skeleton,'_snapshots',{str(i):{} for i in range(32)})
    with pytest.raises(BridgeError,match='SNAPSHOT_LIMIT'):
        skeleton.save_snapshot(object(),object(),'Root')


def test_last_snapshot_slot_reserved_for_restore(monkeypatch):
    snapshots = {str(i):{} for i in range(31)}
    monkeypatch.setattr(skeleton,'_snapshots',snapshots)
    monkeypatch.setattr(skeleton,'guards',lambda *a: (0,{}))
    view = NS(name=lambda:'fixture.casc')
    with pytest.raises(BridgeError,match='SNAPSHOT_LIMIT'):
        skeleton.save_snapshot(view,object(),'Root',{})
    saved = skeleton.save_snapshot(view,object(),'Root',{},for_restore=True)
    assert saved['snapshot_id'] in snapshots and len(snapshots)==32
    with pytest.raises(BridgeError,match='SNAPSHOT_LIMIT'):
        skeleton.save_snapshot(view,object(),'Root',{},for_restore=True)


def test_missing_snapshot_refuses_without_scene_access(monkeypatch):
    monkeypatch.setattr(skeleton,'_snapshots',{})
    with pytest.raises(BridgeError,match='SNAPSHOT_NOT_FOUND'):
        skeleton.restore(object(),object(),'a'*32)


def test_snapshot_cannot_cross_scene(monkeypatch):
    monkeypatch.setattr(skeleton,'_snapshots',{'a'*32:{'scene_ref':object(),'scene_name':'a.casc'}})
    with pytest.raises(BridgeError,match='SNAPSHOT_SCENE_MISMATCH'):
        skeleton.restore(NS(name=lambda:'a.casc'),object(),'a'*32)


def test_changed_topology_refuses_before_recovery_or_write(monkeypatch):
    scene=object()
    monkeypatch.setattr(skeleton,'_snapshots',{'a'*32:{'scene_ref':scene,'scene_name':'a.casc',
        'root':'Root','count':11,'signature':{'Forearm':{'parent':'UpperArm'}}}})
    monkeypatch.setattr(skeleton,'subtree',lambda *args: {})
    monkeypatch.setattr(skeleton,'guards',lambda *args: (11,{'Forearm':{'parent':'Root'}}))
    with pytest.raises(BridgeError,match='SNAPSHOT_STRUCTURE_CHANGED'):
        skeleton.restore(NS(name=lambda:'a.casc'),scene,'a'*32)


def test_batch_outside_subtree_refuses_before_mutation(monkeypatch):
    monkeypatch.setattr(skeleton,'check_frame',lambda *args: None)
    monkeypatch.setattr(skeleton,'subtree',lambda *args: {'Root':object()})
    with pytest.raises(BridgeError,match='OUTSIDE_SUBTREE'):
        skeleton.set_pose(object(),object(),'Root',10,{'outside':{'position':[0,0,0]}},'local')


@pytest.mark.parametrize('start_mode,allowed',[(2,True),(3,False)])
def test_step_allowed_only_on_terminal_section(monkeypatch,start_mode,allowed):
    monkeypatch.setitem(sys.modules,'csc',NS(layers=NS(layer=NS(Interpolation=NS(LINEAR=2,STEP=3),IkFk=NS(FK=1)))))
    def section(mode): return NS(interval=NS(interpolation=mode,common=NS(ik_fk=1)),key=NS(common=NS(ik_fk=1)))
    layer=NS(key_frame_indices=lambda:[0,10],sections={0:section(start_mode),10:section(3)})
    monkeypatch.setattr(skeleton,'track',lambda *a,**kw:(NS(to_string=lambda:'layer'),layer))
    monkeypatch.setattr(skeleton,'parent_id',lambda *a:NS(is_null=lambda:True))
    dv=NS(get_animation_size=lambda:11,get_data_value=lambda *a:[1,1,1])
    bv=NS(get_behaviour_by_name=lambda *a:0,get_behaviour_data=lambda *a:0)
    scene=NS(data_viewer=lambda:dv,behaviour_viewer=lambda:bv)
    # Hashable node stand-in; only this test's host-signature plumbing is simulated.
    class Node:
        def to_string(self): return 'root'
    joints={'Root':Node()}
    if allowed:
        count,signature=skeleton.guards(scene,joints)
        assert count==11 and signature['Root']['sections']['10']==[3,1,1]
    else:
        with pytest.raises(BridgeError,match='UNSUPPORTED_INTERPOLATION'):
            skeleton.guards(scene,joints)
