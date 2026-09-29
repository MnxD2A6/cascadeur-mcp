"""Input guards only; real FBX/Unity acceptance lives in Phase 8 evidence."""
import pytest
from cascadeur_mcp.bridge.protocol import validate_params,BridgeError

def request(tmp_path):
    return {'scene_id':'a'*32,'character_id':'7db06f9b-ac9f-4086-8ebb-e62608f5bad9',
        'output_path':str(tmp_path/'clip.fbx'),'source_copy_path':str(tmp_path/'copy.casc'),
        'options':{'start_frame':0,'end_frame':22,'include_animation':True,'include_skeleton':True}}

def test_valid_export_plan(tmp_path):
    p=request(tmp_path)
    assert validate_params('export_fbx',p)==p

@pytest.mark.parametrize('field,value',[
    ('start_frame',True),('start_frame',1),('end_frame',False),('end_frame',121),
    ('include_animation',False),('include_skeleton',1),('unexpected',0)])
def test_reject_unsupported_options(tmp_path,field,value):
    p=request(tmp_path);p['options'][field]=value
    with pytest.raises(BridgeError,match='INVALID_PARAMS'):validate_params('export_fbx',p)

@pytest.mark.parametrize('field,value',[
    ('output_path','relative.fbx'),('output_path','file.exe'),('expected_sha256','not-a-hash'),
    ('command','arbitrary code')])
def test_bad_export_inputs(tmp_path,field,value):
    p=request(tmp_path);p[field]=value
    with pytest.raises(BridgeError,match='INVALID_PARAMS'):validate_params('export_fbx',p)

def test_native_source_copy_never_overwrites(tmp_path):
    p=request(tmp_path);source=tmp_path/'copy.casc';source.write_bytes(b'preserve')
    with pytest.raises(BridgeError,match='INVALID_PARAMS'):validate_params('export_fbx',p)
    assert source.read_bytes()==b'preserve'
