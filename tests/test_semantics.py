"""Input/profile regressions. Host acceptance uses separate real MCP probes."""
import copy
import json
import random
from pathlib import Path
import pytest
from cascadeur_mcp.bridge.protocol import BridgeError, validate_params, runtime_dir
from cascadeur_mcp.bridge.semantics import build_map
from cascadeur_mcp.bridge.durable import checked_path, load

CID='7db06f9b-ac9f-4086-8ebb-e62608f5bad9'
BASE={'scene_id':'a'*32,'character_id':CID,'frame':10,'pose':{'right_hand':{'center':[1,2,3]}}}

@pytest.mark.parametrize('patch',[
 {'pose':{'right_hand':{'rotation_wxyz':[1,0,0,0]}}},
 {'pose':{'arm_r':{'center':[0,0,0]}}}, {'pose':{'right_hand':{}}}, {'pose':{}},
 {'pose':{'right_hand':{'center':[True,0,0]}}},
 {'pose':{'right_hand':{'center':[0,float('inf'),0]}}},
 {'pose':{'right_hand':{'center':[0,0]}}},
 {'pose':{'right_hand':{'center':[10001,0,0]}}},
 {'frame':True}, {'frame':121}, {'character_id':'Cascy'}, {'scene_id':'../scene'},
 {'shell':'anything'}, {'pose':None},
])
def test_bad_semantic_patch(patch):
    with pytest.raises(BridgeError,match='INVALID_PARAMS'):
        validate_params('set_semantic_pose',{**BASE,**patch})

@pytest.mark.parametrize('poses',[
 [], [{'frame':0,'pose':BASE['pose']}]*2,
 [{'frame':n,'pose':BASE['pose']} for n in range(9)],
 [{'frame':0,'pose':BASE['pose'],'code':'anything'}],
 [{'frame':False,'pose':BASE['pose']}], [{'frame':0}], 'frames',
])
def test_bad_sequence(poses):
    with pytest.raises(BridgeError,match='INVALID_PARAMS'):
        validate_params('set_pose_sequence',{'scene_id':'a'*32,'character_id':CID,'poses':poses})

def fixture():
    from semantic_fixture import synthetic_skeleton
    return synthetic_skeleton()

def test_mapping_independent_of_iteration_order():
    original=fixture();expected=build_map(original)
    for key in ('joints','rig_objects','bindings','point_control_ids'):
        random.Random(42).shuffle(original[key])
    actual=build_map(original)
    assert actual==expected
    ids=[c['control_id'] for r in actual['roles'].values() for c in r['controls'].values()]
    assert len(ids)==len(set(ids))==43
    assert all(not r['joint_state']['writable'] for r in actual['roles'].values())

@pytest.mark.parametrize('change',['rename','duplicate','reparent','rebind','extra'])
def test_incompatible_rig_fails_closed(change):
    s=fixture();pelvis=next(o for o in s['joints'] if o['name']=='pelvis')
    if change=='rename': pelvis['name']='renamed pelvis'
    if change=='duplicate': s['joints'].append(copy.deepcopy(pelvis))
    if change=='reparent': pelvis['parent_id']=CID
    if change=='rebind':
        b=next(b for b in s['bindings'] if b['joint']==pelvis['id']);b['main_point']=CID
    if change=='extra': s['point_control_ids'].append(CID)
    with pytest.raises(BridgeError): build_map(s)

@pytest.mark.parametrize('path',['relative.json','../escape.json','C:/bad.txt','C:/x.json:secret','\\\\host\\share\\x.json',
    'C:/CON.json','C:/NUL/test.json','C:/bad./pose.json','C:/bad?/pose.json'])
def test_snapshot_path_rejects_unsafe_names(path):
    with pytest.raises(ValueError): checked_path(path)

def test_snapshot_excludes_private_runtime():
    with pytest.raises(ValueError): checked_path(str(runtime_dir()/'session.json'))

@pytest.mark.parametrize('raw',[b'{"x":1,"x":2}',b'{"payload":NaN,"sha256":"a"}',b'[]',b'{}',b'{'])
def test_malformed_snapshot_fails_before_host(tmp_path,raw):
    path=tmp_path/'pose.json';path.write_bytes(raw)
    with pytest.raises(BridgeError,match='INVALID_SNAPSHOT'): load(str(path))

def test_instances_do_not_accept_paths(monkeypatch):
    monkeypatch.setenv('CASCADEUR_MCP_INSTANCE','../../escape')
    with pytest.raises(BridgeError,match='INVALID_INSTANCE'): runtime_dir()
