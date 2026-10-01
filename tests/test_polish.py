"""Safety boundaries. Native curve behavior is tested on the live Cascy scene."""
import copy
import pytest
from cascadeur_mcp.bridge.protocol import validate_params,BridgeError

def test_export_status_is_readonly_and_rejects_inputs():
    from cascadeur_mcp.tools.animation_schema import WRITE_METHODS
    assert 'get_fbx_export_status' not in WRITE_METHODS
    assert validate_params('get_fbx_export_status',{})=={}
    with pytest.raises(BridgeError,match='INVALID_PARAMS'):
        validate_params('get_fbx_export_status',{'command':'export'})

def plan():
    return {'scene_id':'a'*32,'character_id':'7db06f9b-ac9f-4086-8ebb-e62608f5bad9',
        'keys':[{'source':f,'target':f,'interpolation':'LINEAR','left_weight':.3,'right_weight':.3} for f in (0,10,22)]}

@pytest.mark.parametrize('field,value',[
    ('source',True),('target',121),('source',-1),('interpolation','AI'),
    ('interpolation','CLAMPED_BEZIER'),
    ('left_weight',float('nan')),('right_weight',float('inf')),('left_weight',True),
    ('right_weight',1.0),('left_weight',-.1),('interpolation','exec(script)'),
])
def test_bad_keys(field,value):
    p=plan();p['keys'][1][field]=value
    with pytest.raises(BridgeError,match='INVALID_PARAMS'): validate_params('retime_character_motion',p)

@pytest.mark.parametrize('case',['empty','duplicate','reverse','endpoint','extra','contacts'])
def test_bad_plans(case):
    p=plan()
    if case=='empty':p['keys']=[]
    if case=='duplicate':p['keys'][1]['target']=0
    if case=='reverse':p['keys'].reverse()
    if case=='endpoint':p['keys'][-1]['target']=21
    if case=='extra':p['action']='Scene.Undo'
    if case=='contacts':p['stabilize_contacts']='yes'
    with pytest.raises(BridgeError,match='INVALID_PARAMS'):validate_params('retime_character_motion',p)

def test_valid_preserving_retime():
    p=plan();p['keys'][1]['target']=11;p['stabilize_contacts']=True
    assert validate_params('retime_character_motion',p)==p

def test_save_never_overwrites(tmp_path):
    dst=tmp_path/'existing.casc';dst.write_bytes(b'important')
    with pytest.raises(BridgeError,match='INVALID_PARAMS'):
        validate_params('save_scene_copy',{'scene_id':'a'*32,'destination':str(dst)})
    assert dst.read_bytes()==b'important'

@pytest.mark.parametrize('path',['relative.casc','C:/tmp/../wrong.casc','C:/tmp/command.exe'])
def test_save_rejects_unsafe_paths(path):
    with pytest.raises(BridgeError,match='INVALID_PARAMS'):
        validate_params('save_scene_copy',{'scene_id':'a'*32,'destination':path})
