"""Bounded Phase 2 schemas, shared by MCP advertisement and host validation."""
import math

NAME = {"type": "string", "minLength": 1, "maxLength": 200}
FRAME = {"type": "integer", "minimum": 0, "maximum": 10000}
VEC3 = {"type": "array", "minItems": 3, "maxItems": 3,
        "items": {"type": "number", "minimum": -1000000, "maximum": 1000000}}
QUAT = {"type": "array", "minItems": 4, "maxItems": 4,
        "items": {"type": "number", "minimum": -1, "maximum": 1}}
WRITE_METHODS = {"set_current_frame", "set_transform", "set_keyframe", "set_pose",
                 "set_local_transform", "set_global_transform", "restore_pose_snapshot"}


def schema(properties, required=()):
    return {"type": "object", "properties": properties, "required": list(required),
            "additionalProperties": False}


SCHEMAS = {
    "get_current_frame": schema({}),
    "set_current_frame": schema({"scene": NAME, "frame": FRAME}, ("scene", "frame")),
    "get_transform": schema({"object": NAME, "frame": FRAME}, ("object",)),
    "set_transform": schema({"scene": NAME, "object": NAME, "frame": FRAME,
                              "position": VEC3, "rotation_wxyz": QUAT},
                             ("scene", "object", "frame")),
    "get_pose": schema({"frame": FRAME, "root": NAME, "objects": {"type": "array", "minItems": 1,
                        "maxItems": 32, "uniqueItems": True, "items": NAME}}, ("frame",)),
    "set_keyframe": schema({"scene": NAME, "object": NAME, "frame": FRAME},
                           ("scene", "object", "frame")),
}
PATCH = schema({'position': VEC3, 'rotation_wxyz': QUAT})
SCHEMAS.update({
    'get_local_transform': schema({'object': NAME, 'frame': FRAME}, ('object',)),
    'get_global_transform': schema({'object': NAME, 'frame': FRAME}, ('object',)),
    'set_pose': schema({'scene': NAME, 'root': NAME, 'frame': FRAME,
                        'space': {'type': 'string', 'enum': ['local', 'global'], 'default': 'local'},
                        'pose_data': {'type': 'object', 'minProperties': 1, 'maxProperties': 32,
                                      'additionalProperties': PATCH}}, ('scene','root','frame','pose_data')),
    'save_pose_snapshot': schema({'scene': NAME, 'root': NAME}, ('scene','root')),
    'restore_pose_snapshot': schema({'scene': NAME, 'snapshot_id': {'type': 'string', 'pattern': '^[0-9a-f]{32}$'}},
                                    ('scene','snapshot_id')),
})
for _space in ('local','global'):
    SCHEMAS['set_'+_space+'_transform'] = schema({'scene': NAME, 'root': NAME, 'object': NAME,
        'frame': FRAME, 'position': VEC3, 'rotation_wxyz': QUAT}, ('scene','root','object','frame'))
DESCRIPTIONS = {
    "get_current_frame": "Read current frame and available animation frame count.",
    "set_current_frame": "Switch to an existing frame; require expected scene name; returns actual frame.",
    "get_transform": "Read world position (scene units), rotation quaternion [w,x,y,z] and track key state for a unique object name.",
    "set_transform": "Set world position and/or unit quaternion [w,x,y,z] on an existing keyframe. Only isolated unlocked object tracks. Returns before/after. Timeout means unknown outcome: read back, never blindly retry.",
    "get_pose": "Read transforms at an existing frame for 1-32 explicit unique object names; does not move the playhead.",
    "set_keyframe": "Create a key on an isolated unlocked object's track at an existing frame, preserving pose. Not per-channel keying. Timeout means unknown outcome; read back before retrying.",
}
DESCRIPTIONS.update({
    'get_pose': 'Read an explicit object list (Phase 2) OR all real Joints under root (Phase 3), with parents and local/global transforms. One round-trip; does not move playhead.',
    'get_local_transform': 'Read actual parent-relative position/quaternion at frame, default current.',
    'get_global_transform': 'Read actual world position/quaternion at frame, default current.',
    'set_local_transform': 'Set one joint in local space using the bounded batch engine. Captures recovery snapshot first and interpolates linear FK tracks.',
    'set_global_transform': 'Set one joint in world space using the bounded batch engine; descendants follow through host update. Captures recovery snapshot first.',
    'set_pose': 'Batch-write 1-32 joints in one checked host transaction and one MCP call. Requires a <=121-frame, unit-scale, isolated-track linear FK Joint subtree. Automatically captures clip snapshot; returns before/after. Timeout is unknown outcome; read back before retry.',
    'save_pose_snapshot': 'Capture all local/global clip transforms and topology/key guards for a Joint subtree in host memory. Up to 32 snapshots per host session; invalid after restart.',
    'restore_pose_snapshot': 'Restore clip transforms from an opaque host-memory snapshot with identity/topology/key-layout guards and full readback. Not a general scene undo; refuses changed track structure.',
})


from . import character_schema
SCHEMAS.update(character_schema.SCHEMAS)
DESCRIPTIONS.update(character_schema.DESCRIPTIONS)
WRITE_METHODS.update({'set_character_pose','play_animation','stop_animation'})
SCHEMAS['save_pose_snapshot']=schema({'scene':NAME,'root':NAME,'scene_id':character_schema.SCENE,
    'character_id':character_schema.UUID,'path':{'type':'string','maxLength':240},'frame':character_schema.FRAME})
SCHEMAS['restore_pose_snapshot']=schema({'scene':NAME,'scene_id':character_schema.SCENE,
    'snapshot_id':character_schema.SCENE,'character_id':character_schema.UUID,'path':{'type':'string','maxLength':240}})
DESCRIPTIONS['save_pose_snapshot'] += ' Alternatively supply scene_id and character_id for full real-character state and bounded native history (16 snapshots).'
DESCRIPTIONS['restore_pose_snapshot'] += ' For character snapshots supply scene_id; uses bounded native Undo with full-state verification; refuses external scene edits.'
DESCRIPTIONS['save_pose_snapshot'] += ' Durable variant: scene_id, character_id, absolute new .json path and optional frame. Saves ONE pose, all Point controls and read-only joint verification; no vendor assets.'
DESCRIPTIONS['restore_pose_snapshot'] += ' Durable variant: scene_id, character_id, path. Restores ONE pose across restarts; verifies joints before commit, recomputes adjacent interpolation, refuses incompatible rigs. Not a whole-clip backup.'

from . import semantic_schema
SCHEMAS.update(semantic_schema.SCHEMAS)
DESCRIPTIONS.update(semantic_schema.DESCRIPTIONS)
WRITE_METHODS.update({'set_semantic_pose','set_pose_sequence','save_pose_snapshot'})


from . import polish_schema
SCHEMAS.update(polish_schema.SCHEMAS)
DESCRIPTIONS.update(polish_schema.DESCRIPTIONS)
WRITE_METHODS.update({'retime_character_motion','save_scene_copy'})

from . import export_schema
SCHEMAS.update(export_schema.SCHEMAS)
DESCRIPTIONS.update(export_schema.DESCRIPTIONS)
WRITE_METHODS.add('export_fbx')


def validate(method, params):
    spec = SCHEMAS[method]
    if set(params) - set(spec['properties']) or set(spec['required']) - set(params):
        raise ValueError('unexpected or missing fields')
    if method in export_schema.SCHEMAS:
        export_schema.validate(method,params)
        return dict(params)
    if method in polish_schema.SCHEMAS:
        polish_schema.validate(method,params)
        return dict(params)
    if method in semantic_schema.SCHEMAS:
        semantic_schema.validate(method,params)
    elif method in character_schema.SCHEMAS or 'scene_id' in params:
        character_schema.validate(params)
    if method=='save_pose_snapshot' and set(params) not in ({'scene','root'},{'scene_id','character_id'},
            {'scene_id','character_id','path'},{'scene_id','character_id','path','frame'}):
        raise ValueError('provide scene/root OR scene_id/character_id')
    if method=='restore_pose_snapshot' and set(params) not in ({'scene','snapshot_id'},{'scene_id','snapshot_id'},
            {'scene_id','character_id','path'}):
        raise ValueError('provide scene or scene_id with snapshot_id')
    if 'path' in params:
        from ..bridge.durable import checked_path
        checked_path(params['path'])
    for key in ('scene', 'object', 'root'):
        if key in params and not valid_name(params[key]):
            raise ValueError(key + ' must be a nonempty name of at most 200 characters without controls')
    if 'frame' in params and (type(params['frame']) is not int or not 0 <= params['frame'] <= 10000):
        raise ValueError('frame must be an integer in [0, 10000]')
    if 'objects' in params:
        names = params['objects']
        if (type(names) is not list or not 1 <= len(names) <= 32
                or not all(valid_name(n) for n in names) or len(set(names)) != len(names)):
            raise ValueError('objects must contain 1-32 distinct valid names')
    if method == 'get_pose' and ('root' in params) == ('objects' in params):
        raise ValueError('provide exactly one of root or objects')
    if 'space' in params and params['space'] not in ('local', 'global'):
        raise ValueError('space must be local or global')
    if 'snapshot_id' in params:
        import re
        if type(params['snapshot_id']) is not str or not re.fullmatch('[0-9a-f]{32}', params['snapshot_id']):
            raise ValueError('invalid snapshot ID')
    if method == 'set_pose':
        pose = params['pose_data']
        if type(pose) is not dict or not 1 <= len(pose) <= 32:
            raise ValueError('pose_data must contain 1-32 joint entries')
        for name, patch in pose.items():
            if not valid_name(name) or type(patch) is not dict or set(patch) - {'position','rotation_wxyz'}:
                raise ValueError('invalid joint name or pose patch fields')
            validate('set_transform', {'scene': params['scene'], 'object': name, 'frame': params['frame'], **patch})
    for key, size, bound in [('position', 3, 1000000), ('rotation_wxyz', 4, 1)]:
        if key in params:
            value = params[key]
            if (type(value) is not list or len(value) != size
                    or any(type(x) not in (int, float) or not math.isfinite(x) or abs(x) > bound for x in value)):
                raise ValueError(key + ' has invalid dimensions, nonfinite or out-of-range numbers')
    if 'rotation_wxyz' in params and abs(sum(x*x for x in params['rotation_wxyz']) - 1) > 1e-4:
        raise ValueError('rotation_wxyz must be a unit quaternion in w,x,y,z order')
    if method in ('set_transform','set_local_transform','set_global_transform') and not {'position', 'rotation_wxyz'} & set(params):
        raise ValueError('provide position and/or rotation_wxyz')
    return dict(params)


def valid_name(value):
    return (type(value) is str and 1 <= len(value) <= 200 and bool(value.strip())
            and all(ord(c) >= 32 and ord(c) != 127 for c in value))
