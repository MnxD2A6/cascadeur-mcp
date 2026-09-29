"""Semantic Cascy v1: explicit role/slot vocabulary, strict finite targets."""
import math
from .character_schema import UUID, SCENE, FRAME, VECTOR, schema

# Named slots describe native control targets, not joint rotation channels.
SLOTS = {
 'pelvis': ('center','orientation','left_hip','right_hip'),
 'chest': ('waist','waist_orientation','center','orientation','left_clavicle',
           'left_clavicle_orientation','left_shoulder','right_clavicle',
           'right_clavicle_orientation','right_shoulder'),
 'head': ('neck','neck_orientation','center','direction','orientation'),
 'left_hand': ('center','direction','orientation'),
 'right_hand': ('center','direction','orientation'),
 'left_elbow': ('center','bend'), 'right_elbow': ('center','bend'),
 'left_foot': ('center','heel','toe','toe_direction','toe_orientation'),
 'right_foot': ('center','heel','toe','toe_direction','toe_orientation'),
 'left_knee': ('center','bend'), 'right_knee': ('center','bend'),
}
POSE = schema({role:schema({slot:VECTOR for slot in slots}) for role,slots in SLOTS.items()})
POSE['minProperties'] = 1
for spec in POSE['properties'].values(): spec['minProperties'] = 1
ENTRY = schema({'frame':FRAME,'pose':POSE}, ('frame','pose'))
SCHEMAS = {
 'get_rig_semantics': schema({'character_id':UUID}, ('character_id',)),
 'get_semantic_pose': schema({'character_id':UUID,'frame':FRAME}, ('character_id','frame')),
 'set_semantic_pose': schema({'scene_id':SCENE,'character_id':UUID,'frame':FRAME,'pose':POSE},
                              ('scene_id','character_id','frame','pose')),
 'set_pose_sequence': schema({'scene_id':SCENE,'character_id':UUID,
    'poses':{'type':'array','minItems':1,'maxItems':8,'items':ENTRY}}, ('scene_id','character_id','poses')),
}
DESCRIPTIONS = {
 'get_rig_semantics':'Discover and validate Cascy v1 role groups, native Point UUIDs, rig bindings and topology fingerprint. Driven joints are read-only. Refuses ambiguous names or unsupported topology.',
 'get_semantic_pose':'Read 11 role groups of named native Point targets in world scene units, plus read-only joint states. Returned pose is writable without knowing joint UUIDs.',
 'set_semantic_pose':'Patch named role/slot world-position targets in one native transaction; omitted slots retain the target frame values. Preserves rig constraints. Read solver-adjusted result; timeout means unknown outcome.',
 'set_pose_sequence':'Write 1-8 unique existing frames of semantic Point targets in ONE MCP call / ONE checked native transaction. Patches merge with pre-transaction state. Failure checks restoration; unverified recovery locks further writes. No timeline extension. Read back after timeout.',
}

def validate_pose(pose):
    if type(pose) is not dict or not pose or set(pose)-set(SLOTS):
        raise ValueError('pose requires known semantic roles')
    for role, patch in pose.items():
        if type(patch) is not dict or not patch or set(patch)-set(SLOTS[role]):
            raise ValueError('invalid semantic slots for '+role)
        for vector in patch.values():
            if (type(vector) is not list or len(vector)!=3 or any(type(x) not in (int,float)
                 or not math.isfinite(x) or abs(x)>10000 for x in vector)):
                raise ValueError('semantic targets require three finite numbers in [-10000,10000]')

def validate(method,params):
    from .character_schema import validate as character_validate
    character_validate({k:v for k,v in params.items() if k not in ('pose','poses')})
    if 'pose' in params: validate_pose(params['pose'])
    if 'poses' in params:
        entries=params['poses']
        if type(entries) is not list or not 1<=len(entries)<=8:
            raise ValueError('sequence requires 1-8 frames')
        frames=set()
        for entry in entries:
            if type(entry) is not dict or set(entry)!={'frame','pose'}:
                raise ValueError('sequence entries require exactly frame and pose')
            character_validate({'frame':entry['frame']})
            if entry['frame'] in frames: raise ValueError('duplicate sequence frame')
            frames.add(entry['frame'])
            validate_pose(entry['pose'])
