"""Phase 2 host calls; sources mapped in PHASE2_DISCOVERY.md.

All entrypoints run on HostBridge's existing Qt thread. No background csc calls.
"""
import math
from .protocol import BridgeError


def frame_info(view, scene):
    return {'scene_name': view.name(), 'current_frame': scene.get_current_frame(),
            'frame_count': scene.model_viewer().data_viewer().get_animation_size()}


def check_frame(scene, frame):
    count = scene.model_viewer().data_viewer().get_animation_size()
    if not 0 <= frame < count:
        raise BridgeError(f'FRAME_OUT_OF_RANGE: requested {frame}; valid range is 0..{count - 1}')


def resolve(scene, name):
    mv = scene.model_viewer()
    matches = [obj for obj in mv.get_objects() if mv.get_object_name(obj) == name]
    if len(matches) != 1:
        raise BridgeError('OBJECT_NOT_UNIQUE: expected exactly one object named ' + repr(name))
    obj = matches[0]
    bv = mv.behaviour_viewer()
    transform = bv.get_behaviour_by_name(obj, 'Transform')
    if transform.is_null():
        raise BridgeError('NO_TRANSFORM: object does not have a Transform behavior')
    fields = {key: bv.get_behaviour_data(transform, 'global_' + key) for key in ('position', 'rotation')}
    if any(data.is_null() for data in fields.values()):
        raise BridgeError('UNSUPPORTED_TRANSFORM: missing global_position/global_rotation data')
    return obj, fields


def track(scene, obj, writable=False):
    lv = scene.layers_viewer()
    lid = lv.layer_id_by_obj_id(obj)
    if lid.is_null():
        raise BridgeError('NO_TRACK: object has no animation track')
    layer = lv.layer(lid)
    if writable:
        if layer.is_locked:
            raise BridgeError('LOCKED_TRACK: unlock the target track before editing')
        if set(layer.obj_ids) != {obj}:
            raise BridgeError('SHARED_TRACK: this PoC only writes isolated single-object tracks')
    return lid, layer


def read_transform(scene, name, frame):
    check_frame(scene, frame)
    obj, fields = resolve(scene, name)
    dv = scene.model_viewer().data_viewer()
    pos = dv.get_data_value(fields['position'], frame)
    rot = dv.get_data_value(fields['rotation'], frame).to_quaternion()
    lid, layer = track(scene, obj)
    return {'object': name, 'object_id': obj.to_string(), 'frame': frame, 'space': 'world',
            'position': [float(x) for x in pos],
            'rotation_wxyz': [rot.w(), rot.x(), rot.y(), rot.z()],
            'layer_id': lid.to_string(), 'is_key': layer.is_key(frame)}


def check_readback(after, params):
    if 'position' in params and any(not math.isclose(x, y, rel_tol=1e-5, abs_tol=1e-4)
                                   for x, y in zip(after['position'], params['position'])):
        raise BridgeError('READBACK_MISMATCH: position differs; scene may have changed; do not blindly retry')
    if 'rotation_wxyz' in params:
        a, b = after['rotation_wxyz'], params['rotation_wxyz']
        # q and -q represent the same physical rotation.
        if min(sum((x-y)**2 for x,y in zip(a,b)), sum((x+y)**2 for x,y in zip(a,b))) > 1e-7:
            raise BridgeError('READBACK_MISMATCH: rotation differs; scene may have changed; do not blindly retry')


def dispatch(view, scene, method, params):
    from . import skeleton, character, playback
    if method in ('play_animation','stop_animation'):
        return playback.dispatch(view,scene,method,params)
    from ..tools.animation_schema import WRITE_METHODS
    if method in WRITE_METHODS:
        playback.require_idle()
    if method in ('get_hand_pose','set_hand_pose_sequence'):
        from . import hands
        return hands.dispatch(view,scene,method,params)
    if method=='export_fbx':
        from .fbx_export import export
        return export(view,scene,params)
    from ..tools.polish_schema import SCHEMAS as POLISH_METHODS
    if method in POLISH_METHODS:
        from . import polish
        return polish.dispatch(view,scene,method,params)
    if method in ('save_pose_snapshot','restore_pose_snapshot') and 'path' in params:
        from . import durable
        return durable.dispatch(view,scene,method,params)
    from ..tools.semantic_schema import SCHEMAS as SEMANTIC_METHODS
    if method in SEMANTIC_METHODS:
        from . import semantics
        return semantics.dispatch(view,scene,method,params)
    if method in character.METHODS or (method in ('save_pose_snapshot','restore_pose_snapshot') and 'scene_id' in params):
        return character.dispatch(view,scene,method,params)
    if method in skeleton.METHODS or (method == 'get_pose' and 'root' in params):
        return skeleton.dispatch(view,scene,method,params)
    if 'scene' in params and view.name() != params['scene']:
        raise BridgeError('SCENE_MISMATCH: active scene differs from expected scene; no changes made',
                          execution_state='not_started')
    if method == 'get_current_frame':
        return frame_info(view, scene)
    frame = params.get('frame', scene.get_current_frame())
    check_frame(scene, frame)
    if method == 'set_current_frame':
        previous = scene.get_current_frame()
        scene.set_current_frame(frame)
        result = frame_info(view, scene)
        if result['current_frame'] != frame:
            raise BridgeError('FRAME_READBACK_MISMATCH: host did not select requested frame')
        return {**result, 'previous_frame': previous}
    if method == 'get_transform':
        return {'scene_name': view.name(), **read_transform(scene, params['object'], frame)}
    if method == 'get_pose':
        return {'scene_name': view.name(), 'frame': frame, 'current_frame': scene.get_current_frame(),
                'scope': 'explicit object subset, not full character pose',
                'objects': [read_transform(scene, name, frame) for name in params['objects']]}
    obj, fields = resolve(scene, params['object'])
    lid, layer = track(scene, obj, writable=True)
    before = read_transform(scene, params['object'], frame)
    if method == 'set_keyframe':
        status = {}
        def add_key(editor, update, domain):
            status['changed'] = editor.layers_editor().set_fixed_interpolation_or_key_if_need(lid, frame, True)
            editor.layers_editor().normalize_sections(scene)
        if scene.modify('C01 Phase 2: set track key', add_key) is not True:
            raise BridgeError('MODIFY_FAILED: key transaction failed; read back before retrying')
        after = read_transform(scene, params['object'], frame)
        if not after['is_key']:
            raise BridgeError('KEY_READBACK_FAILED: host track did not retain key')
        check_readback(after, before)
        return {'scene_name': view.name(), 'before': before, 'after': after,
                'key_operation_return': status.get('changed'), 'scope': 'object track key'}
    if method != 'set_transform':
        raise BridgeError('UNKNOWN_METHOD: no animation handler')
    if not before['is_key']:
        raise BridgeError('KEY_REQUIRED: create a track key at this frame before changing its transform')
    import csc
    import numpy as np
    values = {}
    if 'position' in params:
        values[fields['position']] = np.asarray(params['position'], dtype=np.float32)
    if 'rotation_wxyz' in params:
        values[fields['rotation']] = csc.math.Rotation.from_quaternion(*params['rotation_wxyz'])
    def modify(editor, update, updater):
        for data, value in values.items():
            editor.data_editor().set_data_value(data, frame, value)
        updater.run_update(set(values), frame)
    if scene.modify_update('C01 Phase 2: set world transform', modify) is not True:
        raise BridgeError('MODIFY_FAILED: transform transaction failed; outcome requires readback')
    after = read_transform(scene, params['object'], frame)
    check_readback(after, params)
    return {'scene_name': view.name(), 'before': before, 'after': after, 'modified': True}
