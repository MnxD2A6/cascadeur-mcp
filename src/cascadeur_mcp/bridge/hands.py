"""Cascy finger-local channels, verified by the native hand-shape probe.

Installed provenance: ml/editable_animation.py SetPositions writes Local Rotation
and runs the updater with its data ID. This adapter never changes body rig modes.
"""
import uuid
from . import character
from .protocol import BridgeError
from ..tools.hand_schema import FINGERS

def bindings(scene, cid):
    _, joints, _, _ = character.identify(scene,cid)
    mv,bv,dv=scene.model_viewer(),scene.behaviour_viewer(),scene.data_viewer()
    by_name={}
    for obj in joints: by_name.setdefault(mv.get_object_name(obj),[]).append(obj)
    def unique(name):
        matches=by_name.get(name,[])
        if len(matches)!=1: raise BridgeError('UNSUPPORTED_HAND_RIG: expected one '+name)
        return matches[0]
    result={}
    for side,suffix in [('left','l'),('right','r')]:
        hand=unique('hand_'+suffix)
        group={}
        for finger in ('thumb','index','middle','ring','pinky'):
            parent=hand
            for i in range(1,5):
                name=f'f_{finger}{i}_{suffix}'
                obj=unique(name)
                basic=bv.get_behaviour_by_name(obj,'Basic')
                if bv.get_behaviour_object(basic,'parent')!=parent:
                    raise BridgeError('HAND_HIERARCHY_MISMATCH: '+name)
                parent=obj
                if i==4: continue
                did=bv.get_behaviour_data(bv.get_behaviour_by_name(obj,'Transform'),'local_rotation')
                if did.is_null() or not dv.has_data(did): raise BridgeError('MISSING_FINGER_ROTATION: '+name)
                if int(dv.get_data(did).mode)!=1: raise BridgeError('NONANIMATED_FINGER_ROTATION: '+name)
                group[finger+str(i)]=(obj,did)
        result[side]=group
    return result

def read(view,scene,cid,frame,links=None):
    from .animation import check_frame
    check_frame(scene,frame)
    links=links or bindings(scene,cid)
    return {'scene_id':character.scene_id(view),'character_id':cid,'frame':frame,
        'space':'finger local rotation, quaternion wxyz',
        'hands':{side:{name:character.encoded(scene.data_viewer().get_data_value(did,frame))
                       for name,(obj,did) in group.items()} for side,group in links.items()},
        'bindings':{side:{name:{'joint_id':obj.to_string(),'readable':True,'writable':True,
                      'control_type':'finger.local_rotation'} for name,(obj,did) in group.items()}
                    for side,group in links.items()}}

def write(view,scene,cid,entries):
    import csc
    from .animation import check_frame
    links=bindings(scene,cid)
    bv,lv=scene.behaviour_viewer(),scene.layers_viewer()
    finger_ids={obj for group in links.values() for obj,did in group.values()}
    _,character_joints,owned,_=character.identify(scene,cid)
    terminal_ids={o for o in character_joints
                  if scene.model_viewer().get_object_name(o) in
                  {f'f_{finger}4_{s}' for finger in ('thumb','index','middle','ring','pinky') for s in ('l','r')}}
    # Native Fingers tracks also contain their Box controls. Accept only Boxes
    # whose real RigAdditionalInfo reference points to our validated finger Joint.
    finger_boxes=set()
    for obj in owned:
        if scene.model_viewer().get_object_type_name(obj)!='Box': continue
        info=bv.get_behaviour_by_name(obj,'RigAdditionalInfo')
        if info.is_null(): continue
        ref=bv.get_behaviour_reference(info,'joint')
        if not ref.is_null() and bv.get_behaviour_owner(ref) in finger_ids:
            finger_boxes.add(obj)
    layers={}
    for entry in entries:
        check_frame(scene,entry['frame'])
        for side,patch in entry['hands'].items():
            for name in patch:
                obj,_=links[side][name]
                lid=lv.layer_id_by_obj_id(obj)
                if lid.is_null(): raise BridgeError('NO_FINGER_TRACK')
                layer=lv.layer(lid)
                if layer.is_locked or set(layer.obj_ids)-(finger_ids|terminal_ids|finger_boxes):
                    raise BridgeError('UNSAFE_FINGER_TRACK: locked or contains non-finger objects')
                if any(int(s.interval.interpolation)==7 for s in layer.sections.values()):
                    raise BridgeError('UNSUPPORTED_AI_INTERPOLATION')
                layers[lid]=layer
    journal=character.journal(scene)
    if len(journal['entries'])>=8: raise BridgeError('TRANSACTION_LIMIT: restore or save/restart')
    snapshot=character.save_snapshot(view,scene,cid)
    before=character._snapshots[snapshot['snapshot_id']]['state']
    body_before=[character.get_pose(view,scene,cid,f) for f in range(before['count'])]
    finger_names={f'f_{finger}{i}_{s}' for finger in ('thumb','index','middle','ring','pinky')
                  for i in range(1,5) for s in ('l','r')}
    status={}
    def modify(editor,update,updater):
        try:
            for entry in entries:
                f=entry['frame'];changed=set()
                for side,patch in entry['hands'].items():
                    for name,q in patch.items():
                        obj,did=links[side][name]
                        editor.layers_editor().set_fixed_interpolation_or_key_if_need(lv.layer_id_by_obj_id(obj),f,True)
                        editor.data_editor().set_data_value(did,f,csc.math.Rotation.from_quaternion(*q))
                        changed.add(did)
                updater.run_update(changed,f)
            ip=updater.get_interpolator();ip.reload();ip.interpolate()
            for entry in entries:
                actual=read(view,scene,cid,entry['frame'],links)['hands']
                for side,patch in entry['hands'].items():
                    for name,q in patch.items():
                        a=actual[side][name]
                        if min(sum((x-y)**2 for x,y in zip(a,q)),sum((x+y)**2 for x,y in zip(a,q)))>1e-7:
                            raise BridgeError('FINGER_READBACK_MISMATCH: '+side+'.'+name)
            after=character.capture(scene)
            if any(before[k]!=after[k] for k in ('count','objects','static')):
                raise BridgeError('HAND_RIG_STRUCTURE_CHANGED')
            if before['tracks'].keys()!=after['tracks'].keys():
                raise BridgeError('HAND_TRACK_SET_CHANGED')
            for lid,track in before['tracks'].items():
                for key in ('objects','name','parent','locked'):
                    if track[key]!=after['tracks'][lid][key]:
                        raise BridgeError('HAND_TRACK_METADATA_CHANGED')
                if lid not in {x.to_string() for x in layers} and track!=after['tracks'][lid]:
                    raise BridgeError('BODY_TRACK_CHANGED')
            for f,old in enumerate(body_before):
                new=character.get_pose(view,scene,cid,f)
                if not character.equivalent(old['pose'],new['pose']): raise BridgeError('BODY_POINTS_CHANGED')
                for oid,joint in old['joints'].items():
                    if joint['name'] not in finger_names and not character.equivalent(joint,new['joints'][oid]):
                        raise BridgeError('BODY_JOINT_CHANGED: '+joint['name'])
            status['after']=after
        except Exception as exc:
            status['error']=str(exc)
            raise
    try:
        ok=scene.modify_update('C01: atomic semantic hand shapes',modify)
        if ok is not True or 'error' in status: raise BridgeError('HAND_WRITE_FAILED: '+str(status.get('error')))
        journal['entries'].append({'id':uuid.uuid4().hex,'before':before,'after':status['after']})
        return {'snapshot_id':snapshot['snapshot_id'],'scene_id':character.scene_id(view),
                'transaction_count':1,'mcp_calls_for_sequence_write':1,'body_preserved':True,
                'poses':[read(view,scene,cid,e['frame'],links) for e in entries]}
    except Exception as exc:
        raise character._transaction_failure(scene,before,journal,exc,
                                             snapshot['snapshot_id'],'HAND_WRITE_FAILED') from exc

def dispatch(view,scene,method,params):
    if 'scene_id' in params and params['scene_id']!=character.scene_id(view): raise BridgeError('SCENE_MISMATCH')
    if method=='get_hand_pose': return read(view,scene,params['character_id'],params['frame'])
    return write(view,scene,params['character_id'],params['poses'])
