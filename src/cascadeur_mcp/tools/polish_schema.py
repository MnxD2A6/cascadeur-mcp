"""Bounded curve editing; no arbitrary actions or executable input."""
import math
from .character_schema import SCENE, UUID, FRAME, schema, validate as identity

KEY = schema({'source':FRAME, 'target':FRAME,
    'interpolation':{'type':'string','enum':['LINEAR','BEZIER','LOW_AMPLITUDE_BEZIER']},
    'left_weight':{'type':'number','minimum':0.01,'maximum':0.99},
    'right_weight':{'type':'number','minimum':0.01,'maximum':0.99}},
    ('source','target','interpolation','left_weight','right_weight'))
SCHEMAS = {
    'get_fbx_export_status':schema({}),
    'inspect_character_motion':schema({'character_id':UUID},('character_id',)),
    'retime_character_motion':schema({'scene_id':SCENE,'character_id':UUID,
        'keys':{'type':'array','minItems':2,'maxItems':8,'items':KEY},
        'stabilize_contacts':{'type':'boolean'}},('scene_id','character_id','keys')),
    'save_scene_copy':schema({'scene_id':SCENE,'destination':{'type':'string','maxLength':240}},('scene_id','destination')),
}
DESCRIPTIONS = {
    'get_fbx_export_status':'Read the current native FBX export entitlement and loader methods. No export or file writes. Method availability is not proof of a successful export.',
    'inspect_character_motion':'Read native track curves, rigid-body mass-weighted COM and rig connection errors at every stored frame (max 121). Does not move the playhead.',
    'retime_character_motion':'Retime 2-8 complete synchronized character keys and set native interpolation/easing weights in ONE checked transaction. Preserves solved Point poses and verifies all joint key states; only exclusive IK character tracks. Snapshot/rollback automatic. No arbitrary tangent vectors or AI interpolation. Read back after timeout.',
    'save_scene_copy':'Save the active native scene to a NEW absolute .casc file; never overwrite. Returns file SHA256. Native scene identity can change: rediscover afterwards.',
}

def native_path(value):
    from pathlib import Path
    from ..bridge.durable import checked_path
    if type(value) is not str or not value.lower().endswith('.casc'):
        raise ValueError('destination must end in .casc')
    path=Path(value)
    checked_path(str(path.with_suffix('.json')))
    if path.exists() or path.is_symlink():
        raise ValueError('destination already exists')
    return path

def validate(method,p):
    identity(p)
    if method=='save_scene_copy': native_path(p['destination'])
    if method!='retime_character_motion': return
    if 'stabilize_contacts' in p and type(p['stabilize_contacts']) is not bool: raise ValueError('stabilize_contacts must be boolean')
    keys=p['keys']
    if type(keys) is not list or not 2<=len(keys)<=8: raise ValueError('require 2-8 keys')
    for key in keys:
        if type(key) is not dict or set(key)!=set(KEY['required']): raise ValueError('invalid key fields')
        if any(type(key[n]) is not int or not 0<=key[n]<=120 for n in ('source','target')):
            raise ValueError('invalid frame')
        if key['interpolation'] not in KEY['properties']['interpolation']['enum']: raise ValueError('invalid interpolation')
        for n in ('left_weight','right_weight'):
            if type(key[n]) not in (int,float) or not math.isfinite(key[n]) or not .01<=key[n]<=.99:
                raise ValueError('weight must be finite in [.01,.99]')
    for n in ('source','target'):
        frames=[k[n] for k in keys]
        if frames!=sorted(set(frames)): raise ValueError('keys must be strictly increasing')
    if keys[0]['source']!=keys[0]['target'] or keys[-1]['source']!=keys[-1]['target']:
        raise ValueError('endpoints must stay fixed')
