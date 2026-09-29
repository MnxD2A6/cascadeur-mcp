"""Phase 8 bounded export inputs. Whole single-character scene only."""
import re
from pathlib import Path
from .character_schema import SCENE,UUID,FRAME,schema,validate as identity

OPTIONS=schema({'start_frame':FRAME,'end_frame':FRAME,
    'include_animation':{'type':'boolean','const':True},
    'include_skeleton':{'type':'boolean','const':True}},
    ('start_frame','end_frame','include_animation','include_skeleton'))
SCHEMAS={'export_fbx':schema({'scene_id':SCENE,'character_id':UUID,
    'output_path':{'type':'string','maxLength':240},
    'source_copy_path':{'type':'string','maxLength':240},'options':OPTIONS,
    'expected_sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'}},
    ('scene_id','character_id','output_path','source_copy_path','options'))}
DESCRIPTIONS={'export_fbx':'Export the complete single-character scene with baked skeleton/mesh/animation via native FbxLoader. Full stored frame range only; ASCII, Y-up, Euler filter. Saves a NEW .casc copy first (scene identity changes). New FBX by default; replacing a file requires its exact expected_sha256. Rejects unsupported scopes. Read back files after timeout.'}

def output_path(value):
    from ..bridge.durable import checked_path
    if type(value) is not str or not value.lower().endswith('.fbx'):
        raise ValueError('output_path must be an absolute .fbx filename')
    p=Path(value)
    checked_path(str(p.with_suffix('.json')))
    if p.exists() and (not p.is_file() or p.is_symlink() or getattr(p.lstat(),'st_file_attributes',0)&0x400):
        raise ValueError('FBX destination must be a regular file, not a link')
    return p

def validate(method,p):
    from .polish_schema import native_path
    identity(p);output_path(p['output_path']);native_path(p['source_copy_path'])
    options=p['options']
    if type(options) is not dict or set(options)!=set(OPTIONS['required']):
        raise ValueError('require exactly the four supported export options')
    if any(type(options[k]) is not int or not 0<=options[k]<=120 for k in ('start_frame','end_frame')):
        raise ValueError('frames must be integers in [0,120]')
    if options['start_frame']!=0 or options['end_frame']<options['start_frame']:
        raise ValueError('only complete clips starting at zero are supported')
    if any(options[k] is not True for k in ('include_animation','include_skeleton')):
        raise ValueError('only skeleton+animation export is supported')
    if 'expected_sha256' in p and (type(p['expected_sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',p['expected_sha256'])):
        raise ValueError('expected_sha256 must be a lowercase SHA256')
