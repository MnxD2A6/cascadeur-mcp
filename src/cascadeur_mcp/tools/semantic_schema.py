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
FRAMES = {'type':'array','minItems':1,'maxItems':8,'uniqueItems':True,'items':FRAME}
SELECTION = {
    'roles':{'type':'array','minItems':1,'maxItems':len(SLOTS),'uniqueItems':True,
             'items':{'type':'string','enum':list(SLOTS)}},
    'include_joint_state':{'type':'boolean','default':True},
}
OFFSETS = schema({role:VECTOR for role in SLOTS})
OFFSETS['minProperties'] = 1
SCHEMAS = {
 'get_rig_semantics': schema({'character_id':UUID}, ('character_id',)),
 'get_semantic_pose': schema({'character_id':UUID,'frame':FRAME,
    'roles':{'type':'array','minItems':1,'maxItems':len(SLOTS),'uniqueItems':True,
             'items':{'type':'string','enum':list(SLOTS)}},
    'include_joint_state':{'type':'boolean','default':True}}, ('character_id','frame')),
 'set_semantic_pose': schema({'scene_id':SCENE,'character_id':UUID,'frame':FRAME,'pose':POSE},
                              ('scene_id','character_id','frame','pose')),
 'set_pose_sequence': schema({'scene_id':SCENE,'character_id':UUID,
    'poses':{'type':'array','minItems':1,'maxItems':8,'items':ENTRY}}, ('scene_id','character_id','poses')),
 'get_semantic_pose_sequence': schema({'character_id':UUID,'frames':FRAMES,**SELECTION},
                                      ('character_id','frames')),
 'offset_semantic_pose_sequence': schema({'scene_id':SCENE,'character_id':UUID,
    'frames':FRAMES,'offsets':OFFSETS}, ('scene_id','character_id','frames','offsets')),
 'offset_semantic_pose_sequence_preserving_curves': schema({'scene_id':SCENE,'character_id':UUID,
    'frames':FRAMES,'offsets':OFFSETS}, ('scene_id','character_id','frames','offsets')),
}
DESCRIPTIONS = {
 'get_rig_semantics':'Discover and validate Cascy v1 role groups, native Point UUIDs, rig bindings and topology fingerprint. Driven joints are read-only. Refuses ambiguous names or unsupported topology.',
 'get_semantic_pose':'Read named Point targets in world scene units. Defaults to all 11 roles plus read-only joint states. Optional roles selects 1-11 unique semantic roles; include_joint_state=false omits joint states. Full rig validation always runs. A partial read does not validate animation quality or whole-body motion.',
 'set_semantic_pose':'Patch named role/slot world-position targets in one native transaction; omitted slots retain the target frame values. Preserves rig constraints. Read solver-adjusted result; timeout means unknown outcome.',
 'set_pose_sequence':'Write 1-8 unique existing frames of semantic Point targets in ONE MCP call / ONE checked native transaction. Patches merge with pre-transaction state. Failure checks restoration; unverified recovery locks further writes. No timeline extension. Read back after timeout.',
 'get_semantic_pose_sequence':'Read 1-8 unique existing frames in ONE MCP call, in requested frame order. Optional roles and include_joint_state select values after complete rig validation. Uses native stored values, without moving the playhead or caching a rig between requests.',
 'offset_semantic_pose_sequence':'Translate every Point slot of each named role by its world-space [dx,dy,dz] at 1-8 existing frames. Each frame uses its own current targets. ONE checked transaction with full-scene snapshot and rollback verification. Creates full-character keys and LINEAR intervals; does not preserve authored easing. Returns actual solved edited roles, not requested values. Not idempotent: another call adds the offset again. Never auto-retry after timeout; read back first. No rotation, scale, timeline extension or finger curling.',
 'offset_semantic_pose_sequence_preserving_curves':'Offset named Point role groups at 1-8 EXISTING KEYS on their tracks, in one checked transaction. Preserves key layout, track membership, interpolation, easing weights and supported tangent metadata; no key creation. Writes only selected Point channels. Checks all-frame geometry, unedited FIXED/baked tracks and Point keys outside requested frames. Rejects editing FIXED tracks, custom tangents, additive stacks, cycles or unavailable state. Edited trajectories and solver-coupled rig Points/Joints can change; read actual adjustments. Not idempotent; read back after timeout. No rotation, finger curling or timeline extension.',
}

def validate_pose(pose):
    if type(pose) is not dict or not pose or set(pose)-set(SLOTS):
        raise ValueError('pose requires known semantic roles')
    for role, patch in pose.items():
        if type(patch) is not dict or not patch or set(patch)-set(SLOTS[role]):
            raise ValueError('invalid semantic slots for '+role)
        for vector in patch.values():
            if (type(vector) is not list or len(vector)!=3 or any(type(x) not in (int,float)
                 or abs(x)>10000 or not math.isfinite(x) for x in vector)):
                raise ValueError('semantic targets require three finite numbers in [-10000,10000]')

def validate(method,params):
    from .character_schema import validate as character_validate
    character_validate({k:v for k,v in params.items() if k not in ('pose','poses','roles','include_joint_state','frames','offsets')})
    if 'frames' in params:
        frames=params['frames']
        if type(frames) is not list or not 1<=len(frames)<=8:
            raise ValueError('frames requires 1-8 unique existing frames')
        for frame in frames: character_validate({'frame':frame})
        if len(set(frames))!=len(frames): raise ValueError('duplicate sequence frame')
    if 'offsets' in params:
        offsets=params['offsets']
        if type(offsets) is not dict or not offsets or set(offsets)-set(SLOTS):
            raise ValueError('offsets requires known semantic roles')
        validate_pose({role:{SLOTS[role][0]:vector} for role,vector in offsets.items()})
    if 'roles' in params:
        roles=params['roles']
        if (type(roles) is not list or not 1<=len(roles)<=len(SLOTS)
                or any(type(role) is not str or role not in SLOTS for role in roles)
                or len(set(roles))!=len(roles)):
            raise ValueError('roles requires 1-11 unique known semantic roles')
    if 'include_joint_state' in params and type(params['include_joint_state']) is not bool:
        raise ValueError('include_joint_state must be a boolean')
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
