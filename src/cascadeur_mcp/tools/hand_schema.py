"""Bounded semantic finger rotations; no arbitrary joint IDs or expressions."""
import math
from .character_schema import UUID, SCENE, FRAME, schema, validate as identity

FINGERS = tuple(f'{finger}{i}' for finger in ('thumb','index','middle','ring','pinky') for i in (1,2,3))
QUAT = {'type':'array','minItems':4,'maxItems':4,'items':{'type':'number','minimum':-1,'maximum':1}}
HAND = schema({name:QUAT for name in FINGERS})
HAND['minProperties'] = 1
POSE = schema({'left':HAND,'right':HAND})
POSE['minProperties'] = 1
ENTRY = schema({'frame':FRAME,'hands':POSE}, ('frame','hands'))
SCHEMAS = {
 'get_hand_pose':schema({'character_id':UUID,'frame':FRAME},('character_id','frame')),
 'set_hand_pose_sequence':schema({'scene_id':SCENE,'character_id':UUID,
   'poses':{'type':'array','minItems':1,'maxItems':8,'items':ENTRY}},('scene_id','character_id','poses')),
}
DESCRIPTIONS = {
 'get_hand_pose':'Read Cascy finger local rotations and verified hierarchy bindings; body hand Points do not control finger shape.',
 'set_hand_pose_sequence':'Write 1-8 frames of semantic left/right finger local unit quaternions in one checked native transaction. Only validated Cascy finger chains, not body joints. Preserves existing body keys and interpolation; read back after timeout.',
}

def validate_hands(hands):
    if type(hands) is not dict or not hands or set(hands)-{'left','right'}:
        raise ValueError('hands must contain left and/or right')
    for pose in hands.values():
        if type(pose) is not dict or not pose or set(pose)-set(FINGERS):
            raise ValueError('unknown or empty finger pose')
        for q in pose.values():
            if (type(q) is not list or len(q)!=4 or any(type(v) not in (int,float)
                or not math.isfinite(v) or abs(v)>1 for v in q)
                or abs(sum(v*v for v in q)-1)>1e-4):
                raise ValueError('finger rotation must be a finite unit quaternion [w,x,y,z]')

def validate(method, params):
    identity({k:v for k,v in params.items() if k!='poses'})
    if method=='get_hand_pose': return
    entries=params['poses']
    if type(entries) is not list or not 1<=len(entries)<=8: raise ValueError('require 1-8 frames')
    seen=set()
    for entry in entries:
        if type(entry) is not dict or set(entry)!={'frame','hands'}: raise ValueError('invalid hand entry')
        identity({'frame':entry['frame']})
        if entry['frame'] in seen: raise ValueError('duplicate frame')
        seen.add(entry['frame'])
        validate_hands(entry['hands'])
