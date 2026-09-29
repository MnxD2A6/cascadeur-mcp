"""Real Joint hierarchy, batch pose and bounded recovery. See PHASE3_DISCOVERY.md."""
import time
import uuid
from .protocol import BridgeError
from .animation import check_frame, resolve, track, check_readback

_snapshots = {}
METHODS = {'get_local_transform','get_global_transform','set_local_transform','set_global_transform',
           'set_pose','save_pose_snapshot','restore_pose_snapshot'}


def parent_id(scene, obj):
    bv = scene.behaviour_viewer()
    return bv.get_behaviour_object(bv.get_behaviour_by_name(obj, 'Basic'), 'parent')


def subtree(scene, root):
    mv, bv = scene.model_viewer(), scene.behaviour_viewer()
    all_ids = mv.get_objects()
    if len(all_ids) > 10000:
        raise BridgeError('SCENE_LIMIT: too many objects for bounded hierarchy scan')
    roots = [o for o in all_ids if mv.get_object_name(o) == root]
    if len(roots) != 1:
        raise BridgeError('ROOT_NOT_UNIQUE: expected one named root')
    children = {}
    for obj in all_ids:
        parent = parent_id(scene, obj)
        children.setdefault(parent, []).append(obj)
    result, visited = {}, set()
    def visit(obj):
        if obj in visited:
            raise BridgeError('INVALID_HIERARCHY: cycle')
        visited.add(obj)
        if len(visited) > 32:
            raise BridgeError('JOINT_LIMIT: subtree exceeds 32 nodes')
        if bv.get_behaviour_by_name(obj, 'Joint').is_null():
            raise BridgeError('NON_JOINT_SUBTREE: only pure Joint hierarchies supported')
        name = mv.get_object_name(obj)
        if name in result:
            raise BridgeError('AMBIGUOUS_JOINT: duplicate names in subtree')
        # The named resolution used by convenience tools must agree scene-wide.
        if sum(mv.get_object_name(o) == name for o in all_ids) != 1:
            raise BridgeError('AMBIGUOUS_JOINT: name is not unique in scene')
        result[name] = obj
        for child in children.get(obj, []):
            visit(child)
    visit(roots[0])
    return result


def fields_for(scene, obj, space):
    bv = scene.behaviour_viewer()
    tr = bv.get_behaviour_by_name(obj, 'Transform')
    if tr.is_null():
        raise BridgeError('NO_TRANSFORM: missing Joint transform')
    return {k: bv.get_behaviour_data(tr, space+'_'+k) for k in ('position','rotation')}


def transform(scene, obj, frame, space):
    dv = scene.data_viewer()
    fields = fields_for(scene, obj, space)
    pos = dv.get_data_value(fields['position'], frame)
    q = dv.get_data_value(fields['rotation'], frame).to_quaternion()
    return {'position':[float(x) for x in pos], 'rotation_wxyz':[q.w(),q.x(),q.y(),q.z()]}


def pose(view, scene, root, frame, joints=None):
    check_frame(scene, frame)
    joints = subtree(scene, root) if joints is None else joints
    result = {}
    for name,obj in joints.items():
        parent = parent_id(scene,obj)
        lid, layer = track(scene,obj)
        result[name] = {'object_id':obj.to_string(),
            'parent':None if parent.is_null() else scene.model_viewer().get_object_name(parent),
            'parent_id':None if parent.is_null() else parent.to_string(),
            'local':transform(scene,obj,frame,'local'), 'global':transform(scene,obj,frame,'global'),
            'is_key':layer.is_key(frame), 'layer_id':lid.to_string(),
            'track_sections':{str(f):{'interpolation':int(s.interval.interpolation),
                'interval_ik_fk':int(s.interval.common.ik_fk),'key_ik_fk':int(s.key.common.ik_fk)}
                for f,s in layer.sections.items()}}
    return {'scene_name':view.name(),'root':root,'frame':frame,'joint_count':len(joints),'joints':result}


def guards(scene, joints):
    """Snapshot contract excludes scale, parent-external rigs and non-FK tracks."""
    import csc
    count = scene.data_viewer().get_animation_size()
    if not 1 <= count <= 121:
        raise BridgeError('CLIP_LIMIT: Phase 3 supports 1-121 stored frames')
    ids = set(joints.values())
    signature = {}
    for name,obj in joints.items():
        parent = parent_id(scene,obj)
        if not parent.is_null() and parent not in ids:
            raise BridgeError('EXTERNAL_PARENT: choose the topmost Joint root')
        lid,layer = track(scene,obj,writable=True)
        keys = list(layer.key_frame_indices())
        if keys != [0, count-1]:
            raise BridgeError('KEY_LAYOUT: Phase 3 currently requires two endpoint keys per track')
        sections = {}
        for index,section in layer.sections.items():
            if section.key is None:
                raise BridgeError('UNSUPPORTED_SECTION: only keyed linear FK sections supported')
            config = [int(section.interval.interpolation),int(section.interval.common.ik_fk),int(section.key.common.ik_fk)]
            # Observed after save/load in 2026.2.2: terminal section is STEP.
            # There is no following interval inside the clip; preserve that flag.
            expected_modes = [int(csc.layers.layer.Interpolation.LINEAR)]
            if index == count-1:
                expected_modes.append(int(csc.layers.layer.Interpolation.STEP))
            if config[0] not in expected_modes or config[1:] != [int(csc.layers.layer.IkFk.FK)]*2:
                raise BridgeError(f'UNSUPPORTED_INTERPOLATION: {name} section {index}: {config}; expected linear FK [2,1,1]')
            sections[str(index)] = config
        tr = scene.behaviour_viewer().get_behaviour_by_name(obj,'Transform')
        scale_id = scene.behaviour_viewer().get_behaviour_data(tr,'local_scale')
        for frame in range(count):
            if any(abs(float(x)-1) > 1e-5 for x in scene.data_viewer().get_data_value(scale_id,frame)):
                raise BridgeError('UNSUPPORTED_SCALE: unit local scale required throughout clip')
        signature[name] = {'id':obj.to_string(),'parent':None if parent.is_null() else parent.to_string(),
                           'layer':lid.to_string(),'keys':keys,'sections':sections}
    return count, signature


def save_snapshot(view, scene, root, joints=None, *, for_restore=False):
    # Reserve the last slot so a write that fills the normal budget is recoverable.
    limit = 32 if for_restore else 31
    if len(_snapshots) >= limit:
        raise BridgeError('SNAPSHOT_LIMIT: 31 normal slots plus one restore slot; save scene and restart bridge to clear')
    joints = subtree(scene,root) if joints is None else joints
    count, signature = guards(scene,joints)
    frames = [pose(view,scene,root,f,joints)['joints'] for f in range(count)]
    sid = uuid.uuid4().hex
    _snapshots[sid] = {'scene_ref':scene,'scene_name':view.name(),'root':root,'count':count,
                       'signature':signature,'frames':frames}
    return {'snapshot_id':sid,'scene_name':view.name(),'root':root,'joint_count':len(joints),
            'frame_count':count,'storage':'host memory; invalid after restart; pose data only'}


def _native_values(scene, joints, patches, space):
    import csc
    import numpy as np
    result = {}
    for name,patch in patches.items():
        fields = fields_for(scene,joints[name],space)
        if 'position' in patch:
            result[fields['position']] = np.asarray(patch['position'],dtype=np.float32)
        if 'rotation_wxyz' in patch:
            result[fields['rotation']] = csc.math.Rotation.from_quaternion(*patch['rotation_wxyz'])
    return result


def set_pose(view, scene, root, frame, patches, space):
    started = time.perf_counter()
    check_frame(scene,frame)
    joints = subtree(scene,root)
    if set(patches)-set(joints):
        raise BridgeError('OUTSIDE_SUBTREE: pose names must belong to the selected skeleton')
    guards(scene,joints)
    # Existing keys only: recovery must not silently omit key/topology edits.
    for obj in joints.values():
        if not track(scene,obj)[1].is_key(frame):
            raise BridgeError('KEY_REQUIRED: every subtree track must already have a key at target frame')
    before = pose(view,scene,root,frame,joints)
    values = _native_values(scene,joints,patches,space)
    snapshot = save_snapshot(view,scene,root,joints)
    def modify(editor, update, updater):
        for data,value in values.items():
            editor.data_editor().set_data_value(data,frame,value)
        updater.run_update(set(values),frame)
        interpolator = updater.get_interpolator()
        interpolator.reload()
        interpolator.interpolate()
    if scene.modify_update('C01 Phase 3: batch '+space+' pose',modify) is not True:
        raise BridgeError('MODIFY_FAILED: inspect state; recovery snapshot '+snapshot['snapshot_id'])
    after = pose(view,scene,root,frame,joints)
    try:
        for name,patch in patches.items():
            check_readback(after['joints'][name][space],patch)
    except BridgeError as exc:
        raise BridgeError(str(exc)+'; recovery snapshot '+snapshot['snapshot_id']) from exc
    return {'scene_name':view.name(),'root':root,'frame':frame,'space':space,
            'joints_changed':list(patches),'snapshot_id':snapshot['snapshot_id'],
            'before':before,'after':after,'host_elapsed_ms':(time.perf_counter()-started)*1000,
            'mcp_calls_for_write':1,'transaction_count':1,'interpolation':'Cascadeur LINEAR FK'}


def restore(view,scene,sid):
    snap = _snapshots.get(sid)
    if snap is None:
        raise BridgeError('SNAPSHOT_NOT_FOUND: unknown or previous host-session snapshot')
    if scene != snap['scene_ref'] or view.name() != snap['scene_name']:
        raise BridgeError('SNAPSHOT_SCENE_MISMATCH: only original live scene can be restored')
    joints = subtree(scene,snap['root'])
    count,signature = guards(scene,joints)
    if count != snap['count'] or signature != snap['signature']:
        raise BridgeError('SNAPSHOT_STRUCTURE_CHANGED: topology, keys, track modes or frame count differ')
    recovery = save_snapshot(view,scene,snap['root'],joints,for_restore=True)
    def modify(editor,update,updater):
        for frame,original in enumerate(snap['frames']):
            values = _native_values(scene,joints,{name:item['local'] for name,item in original.items()},'local')
            for data,value in values.items():
                editor.data_editor().set_data_value(data,frame,value)
            updater.run_update(set(values),frame)
    if scene.modify_update('C01 Phase 3: restore pose snapshot',modify) is not True:
        raise BridgeError('RESTORE_FAILED: inspect state; recovery snapshot '+recovery['snapshot_id'])
    for frame,original in enumerate(snap['frames']):
        actual = pose(view,scene,snap['root'],frame,joints)['joints']
        for name in original:
            for space in ('local','global'):
                check_readback(actual[name][space], original[name][space])
    return {'scene_name':view.name(),'restored':True,'snapshot_id':sid,'recovery_snapshot_id':recovery['snapshot_id'],
            'joint_count':len(joints),'frames_verified':count,'spaces_verified':['local','global']}


def dispatch(view,scene,method,params):
    if 'scene' in params and params['scene'] != view.name():
        raise BridgeError('SCENE_MISMATCH: active scene differs; no changes made')
    if method == 'save_pose_snapshot':
        return save_snapshot(view,scene,params['root'])
    if method == 'restore_pose_snapshot':
        return restore(view,scene,params['snapshot_id'])
    frame = params.get('frame',scene.get_current_frame())
    check_frame(scene,frame)
    if method == 'get_pose':
        return pose(view,scene,params['root'],frame)
    if method in ('get_local_transform','get_global_transform'):
        obj,_ = resolve(scene,params['object'])
        space = 'local' if method == 'get_local_transform' else 'global'
        parent = parent_id(scene,obj)
        return {'scene_name':view.name(),'object':params['object'],'object_id':obj.to_string(),
                'parent':None if parent.is_null() else scene.model_viewer().get_object_name(parent),
                'space':space,'frame':frame,**transform(scene,obj,frame,space)}
    if method == 'set_pose':
        return set_pose(view,scene,params['root'],frame,params['pose_data'],params.get('space','local'))
    if method in ('set_local_transform','set_global_transform'):
        patch = {k:params[k] for k in ('position','rotation_wxyz') if k in params}
        return set_pose(view,scene,params['root'],frame,{params['object']:patch},
                        'local' if method == 'set_local_transform' else 'global')
    raise BridgeError('UNKNOWN_METHOD: no skeleton handler')
