"""Phase 4 input/recovery guards; real host acceptance is recorded separately."""
import copy
import pytest
from cascadeur_mcp.bridge.protocol import BridgeError,validate_params
from cascadeur_mcp.bridge import character,playback
CID='7db06f9b-ac9f-4086-8ebb-e62608f5bad9'
BASE={'scene_id':'a'*32,'character_id':CID,'frame':10,'pose':{CID:{'position':[0,0,0]}}}
@pytest.mark.parametrize('patch',[
 {'character_id':'Rig info'},{'scene_id':'../scene'},{'frame':True},{'frame':121},
 {'pose':{}},{'pose':{CID:{'rotation':[1,0,0,0]}}},{'pose':{CID:{'position':[True,0,0]}}},
 {'pose':{CID:{'position':[float('nan'),0,0]}}},{'pose':{CID:{'position':[10001,0,0]}}},
 {'pose':{'hand':{'position':[0,0,0]}}},{'code':'anything'},
])
def test_bad_character_input(patch):
 with pytest.raises(BridgeError,match='INVALID_PARAMS'):validate_params('set_character_pose',{**BASE,**patch})
@pytest.mark.parametrize('method,args',[
 ('save_pose_snapshot',{}),('save_pose_snapshot',{'scene':'a','character_id':CID}),
 ('restore_pose_snapshot',{'scene':'a','scene_id':'a'*32,'snapshot_id':'a'*32}),
 ('play_animation',{'scene_id':'a'*32,'start_frame':22,'end_frame':0}),
 ('play_animation',{'scene_id':'a'*32,'start_frame':0,'end_frame':True}),
 ('stop_animation',{}),
])
def test_invalid_snapshot_playback_variants(method,args):
 with pytest.raises(BridgeError,match='INVALID_PARAMS'):validate_params(method,args)
def test_character_input_accepts_uuid_batch():
 assert validate_params('set_character_pose',BASE)==BASE
 assert validate_params('save_pose_snapshot',{'scene_id':'a'*32,'character_id':CID})
def test_snapshot_compare_never_tolerates_structure_or_settings_change():
 a={'count':23,'objects':{'name':'original'},'static':{'limit':0.1},'tracks':{},'values':{'s:flag':[0],'d:pos':[[0.0,0.0,0.0]]}}
 for key,patch in [('objects',{'name':'changed'}),('static',{'limit':0.100001}),('count',24)]:
  b=copy.deepcopy(a);b[key]=patch;assert not character.equivalent(a,b)
 b=copy.deepcopy(a);b['values']['s:flag']=[1];assert not character.equivalent(a,b)
 b=copy.deepcopy(a);b['values']['d:pos'][0][0]=1.;assert not character.equivalent(a,b)
 assert not character.equivalent(1000000,1000001)
def test_active_native_playback_blocks_writes(monkeypatch):
 monkeypatch.setattr(playback,'_run',{'status':'playing'})
 with pytest.raises(BridgeError,match='PLAYBACK_ACTIVE'):playback.require_idle()

def test_bridge_stop_releases_native_scene_wrappers(monkeypatch):
 import sys
 from types import SimpleNamespace as NS
 from cascadeur_mcp.bridge.host import release_scene_references
 stopped=[]
 a=NS(_snapshots={'x':object()},_journals={'x':object()})
 b=NS(_snapshots={'y':object()})
 p=NS(_run={'timer':NS(stop=lambda:stopped.append(True))})
 monkeypatch.setitem(sys.modules,'cascadeur_mcp.bridge.character',a)
 monkeypatch.setitem(sys.modules,'cascadeur_mcp.bridge.skeleton',b)
 monkeypatch.setitem(sys.modules,'cascadeur_mcp.bridge.playback',p)
 release_scene_references()
 assert a._snapshots=={} and a._journals=={} and b._snapshots=={} and p._run is None and stopped==[True]

def test_pose_precision_does_not_hide_large_rotation_or_translation():
 assert character.equivalent([1.0,2.0,3.0],[1.001,2.0,3.0])
 assert not character.equivalent([1.0,2.0,3.0],[1.1,2.0,3.0])
 assert not character.equivalent([1.,0.,0.,0.],[1.,0.005,0.,0.])
