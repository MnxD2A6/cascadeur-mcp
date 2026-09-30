"""Bounded UUID-addressed native character tools (Phase 4)."""
import math
import re

UUID = {'type':'string','pattern':'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'}
SCENE = {'type':'string','pattern':'^[0-9a-f]{32}$'}
FRAME = {'type':'integer','minimum':0,'maximum':120}
VECTOR = {'type':'array','minItems':3,'maxItems':3,'items':{'type':'number','minimum':-10000,'maximum':10000}}

def schema(props,required=()):
    return {'type':'object','properties':props,'required':list(required),'additionalProperties':False}

SCHEMAS = {
 'list_characters':schema({}),
 'get_character_skeleton':schema({'character_id':UUID},('character_id',)),
 'get_character_pose':schema({'character_id':UUID,'frame':FRAME},('character_id','frame')),
 'set_character_pose':schema({'scene_id':SCENE,'character_id':UUID,'frame':FRAME,
    'pose':{'type':'object','minProperties':1,'maxProperties':64,'propertyNames':UUID,
            'additionalProperties':schema({'position':VECTOR},('position',))}},('scene_id','character_id','frame','pose')),
 'play_animation':schema({'scene_id':SCENE,'start_frame':FRAME,'end_frame':FRAME},('scene_id','start_frame','end_frame')),
 'stop_animation':schema({'scene_id':SCENE},('scene_id',)),
}
DESCRIPTIONS = {
 'list_characters':'List actual RigInfo owner UUIDs in the saved scene; names are display labels only.',
 'get_character_skeleton':'Read full native joint hierarchy, rig controls, bindings, constraint references and shared tracks by character UUID.',
 'get_character_pose':'Read every character joint local/global transform plus all native Point targets in ONE call. Returned pose is writable by set_character_pose.',
 'set_character_pose':'Write the complete native Point target set in ONE native transaction at an EXISTING frame (0-120). Rig solves joints; constraints and IK mode retained. Captures full-scene snapshot; failures automatically verify rollback. Exclusive C01 pose editing required; timeout is unknown outcome, read back before retry.',
 'play_animation':'Start a bounded native Timeline.Play observation on a stopped scene. Returns pending: call stop_animation later for measured playback/stop evidence. Never advances frames with a script. Requires exclusive playback ownership; rejects edits while active.',
 'stop_animation':'Stop only playback owned by this bridge; return actual frame observations and stop verification. Idempotent after automatic end stop. Cannot stop arbitrary external playback.',
}

def validate(params):
    for field,spec in [('character_id',UUID),('scene_id',SCENE)]:
        if field in params and (type(params[field]) is not str or not re.fullmatch(spec['pattern'],params[field])):
            raise ValueError('invalid '+field)
    for key in ('frame','start_frame','end_frame'):
        if key in params and (type(params[key]) is not int or not 0<=params[key]<=120):
            raise ValueError(key+' must be an integer in [0,120]')
    if 'start_frame' in params and params['end_frame']<=params['start_frame']:
        raise ValueError('end_frame must exceed start_frame')
    if 'pose' in params:
        pose=params['pose']
        if type(pose) is not dict or not 1<=len(pose)<=64: raise ValueError('pose must contain 1-64 Point IDs')
        for oid,patch in pose.items():
            if type(oid) is not str or not re.fullmatch(UUID['pattern'],oid): raise ValueError('invalid Point UUID')
            if type(patch) is not dict or set(patch)!={'position'}: raise ValueError('Point requires exactly position')
            v=patch['position']
            if type(v) is not list or len(v)!=3 or any(type(n) not in (int,float) or abs(n)>10000 or not math.isfinite(n) for n in v):
                raise ValueError('position requires three finite numbers in [-10000,10000]')
