"""Bounded real RigInfo/Point controller adapter. Sources: PHASE4_DISCOVERY.md.

Native rig update remains enabled. Joint rotations are read-only on this adapter:
the tested Cascy rig overwrites direct Joint/Box rotation writes.
"""
import hashlib
import json
import math
import time
import uuid
from .protocol import BridgeError

_journals = {}
_snapshots = {}
METHODS = {'list_characters','get_character_skeleton','get_character_pose','set_character_pose'}
NULL = '00000000-0000-0000-0000-000000000000'


def encoded(value):
    if value is None or isinstance(value,(str,bool,int,float)):
        if isinstance(value,float) and not math.isfinite(value):
            raise BridgeError('NONFINITE_HOST_DATA: scene contains nonfinite values')
        return value
    if hasattr(value,'to_string'): return value.to_string()
    if hasattr(value,'to_quaternion'):
        q=value.to_quaternion()
        values=[q.w(),q.x(),q.y(),q.z()]
        # Canonical quaternion sign makes full-scene comparisons meaningful.
        sign=next((1 if v>0 else -1 for v in values if abs(v)>1e-8),1)
        return [v*sign for v in values]
    if hasattr(value,'tolist'): return encoded(value.tolist())
    if all(hasattr(value,k) for k in ('w','x','y','z')):
        return encoded([value.w(),value.x(),value.y(),value.z()])
    if isinstance(value,(list,tuple,set)): return [encoded(v) for v in value]
    raise BridgeError('UNSUPPORTED_HOST_VALUE: '+type(value).__name__)


def equivalent(a,b):
    if isinstance(a,dict):
        if set(a)=={'count','objects','values','static','tracks'}:
            # Only animated data may incur rig solver roundoff. Identity, track
            # metadata, static constraints and every stored setting remain exact.
            return (isinstance(b,dict) and a.keys()==b.keys()
                    and all(a[k]==b[k] for k in ('count','objects','static','tracks'))
                    and a['values'].keys()==b['values'].keys()
                    and all((v==b['values'][k] if k.startswith('s:') else equivalent(v,b['values'][k]))
                            for k,v in a['values'].items()))
        return isinstance(b,dict) and a.keys()==b.keys() and all(equivalent(v,b[k]) for k,v in a.items())
    if isinstance(a,list):
        if len(a)==4 and all(isinstance(row,list) and len(row)==4 and all(type(v) is float for v in row) for row in a):
            return (isinstance(b,list) and len(b)==4 and all(isinstance(row,list) and len(row)==4 for row in b)
                    and all(type(b[i][j]) is float and math.isclose(a[i][j],b[i][j],rel_tol=1e-6,abs_tol=0.01 if j==3 else 1e-4)
                            for i in range(4) for j in range(4)))
        if len(a)==4 and all(type(v) is float for v in a):
            return isinstance(b,list) and len(b)==4 and all(type(y) is float and math.isclose(x,y,abs_tol=1e-4,rel_tol=1e-6) for x,y in zip(a,b))
        return isinstance(b,list) and len(a)==len(b) and all(equivalent(x,y) for x,y in zip(a,b))
    if type(a) is float and type(b) is float:
        # Native Undo regenerates IK outputs. Position tolerance is 0.01 scene
        # units (0.1 mm at Cascy scale); quaternions use the stricter check above.
        # UUIDs, topology, integer modes and booleans still compare exactly.
        return math.isclose(a,b,rel_tol=1e-6,abs_tol=0.01)
    return type(a)==type(b) and a==b


def scene_id(view):
    path=view.get_path_name()
    if not path: raise BridgeError('UNSAVED_SCENE: save the character scene before editing')
    return hashlib.sha256(path.replace('\\','/').casefold().encode()).hexdigest()[:32]


def identify(scene,cid):
    bv=scene.behaviour_viewer()
    matches=[b for b in bv.get_behaviours('RigInfo') if bv.get_behaviour_owner(b).to_string()==cid]
    if len(matches)!=1: raise BridgeError('CHARACTER_NOT_FOUND: require one RigInfo owner UUID in the active scene')
    rig=matches[0]
    joints=set(bv.get_behaviour_objects_range(rig,'related_joints'))
    owned=set(bv.get_behaviour_objects_range(rig,'rig_objects'))|joints|{bv.get_behaviour_owner(rig)}
    owned.update(bv.get_behaviour_objects_range(rig,'related_objects'))
    # Cascy's mesh is on Torso but not in RigInfo.rig_objects. Associate it only
    # through the actual skin joint references, never through its display name.
    for mesh in bv.get_behaviours('MeshObject'):
        links=set(bv.get_behaviour_objects_range(mesh,'linked_objects'))
        if links and links<=joints: owned.add(bv.get_behaviour_owner(mesh))
    if not 1<=len(joints)<=128 or len(owned)>1024:
        raise BridgeError('CHARACTER_LIMIT: supports 1-128 joints and at most 1024 rig objects')
    mv=scene.model_viewer()
    controls={o.to_string():o for o in owned if mv.get_object_type_name(o)=='Point'}
    if not 1<=len(controls)<=64: raise BridgeError('UNSUPPORTED_RIG: expected 1-64 native Point controls')
    return rig,joints,owned,controls


def transform(scene,obj,frame):
    bv,dv=scene.behaviour_viewer(),scene.data_viewer()
    tr=bv.get_behaviour_by_name(obj,'Transform')
    if tr.is_null(): return None
    result={}
    for space in ('local','global'):
        fields={}
        for field in ('position','rotation'):
            did=bv.get_behaviour_data(tr,space+'_'+field)
            if not did.is_null(): fields['rotation_wxyz' if field=='rotation' else field]=encoded(dv.get_data_value(did,frame))
        if fields: result[space]=fields
    return result


def sections(layer):
    return {str(f):{'interpolation':int(s.interval.interpolation),'ik_fk':int(s.interval.common.ik_fk),
        'fixation':int(s.interval.common.fixation),'key':None if s.key is None else
        {'ik_fk':int(s.key.common.ik_fk),'fixation':int(s.key.common.fixation),'label':encoded(s.key.label),
         'tangents':int(s.key.tangents),'left_weight_velocity':s.key.left_weight_velocity,
         'right_weight_velocity':s.key.right_weight_velocity}} for f,s in layer.sections.items()}


def skeleton(view,scene,cid):
    rig,joints,owned,controls=identify(scene,cid)
    bv,mv,lv=scene.behaviour_viewer(),scene.model_viewer(),scene.layers_viewer()
    nodes=[]
    control_objects=[]
    for obj in sorted(owned,key=lambda o:o.to_string()):
        basic=bv.get_behaviour_by_name(obj,'Basic')
        parent=bv.get_behaviour_object(basic,'parent')
        item={'id':obj.to_string(),'name':mv.get_object_name(obj),'type':mv.get_object_type_name(obj),
              'parent_id':None if parent.is_null() else parent.to_string(),
              'behaviours':sorted(bv.get_behaviour_name(b) for b in bv.get_behaviours(obj))}
        if obj in joints: nodes.append(item)
        else: control_objects.append(item)
    tracks={}
    for lid,layer in lv.layers_map().items():
        if not set(layer.obj_ids)&owned: continue
        tracks[lid.to_string()]={'name':layer.header.name,'objects':sorted(encoded(layer.obj_ids)),
            'locked':layer.is_locked,'keys':list(layer.key_frame_indices()),'sections':sections(layer),
            'contains_outside_character':bool(set(layer.obj_ids)-owned)}
    bindings=[]
    constraints=[]
    for obj in owned:
        for b in bv.get_behaviours(obj):
            name=bv.get_behaviour_name(b)
            if name=='RigAdditionalInfo':
                refs={}
                for prop in ('joint','main_point','direction_point','additional_point','rigid_body','limb_direction'):
                    ref=bv.get_behaviour_reference(b,prop)
                    refs[prop]=None if ref.is_null() else bv.get_behaviour_owner(ref).to_string()
                bindings.append({'box_id':obj.to_string(),**refs})
            if name in ('AngleConstraints','ConnectionPointTwoBody','AttractionPoint'):
                props={}
                dv=scene.data_viewer()
                for prop in bv.get_behaviour_property_names(b):
                    kind=bv.get_property_type(b,prop).name
                    if kind=='BehaviourType':
                        ref=bv.get_behaviour_reference(b,prop)
                        props[prop]={'behaviour_id':ref.to_string(),'object_id':None if ref.is_null() else bv.get_behaviour_owner(ref).to_string()}
                    elif kind in ('DataType','SettingType'):
                        setting=kind=='SettingType'
                        did=(bv.get_behaviour_setting if setting else bv.get_behaviour_data)(b,prop)
                        exists=(dv.has_setting if setting else dv.has_data)(did)
                        item={'id':did.to_string(),'stored':exists}
                        if exists:
                            info=(dv.get_setting if setting else dv.get_data)(did)
                            getter=dv.get_setting_value if setting else dv.get_data_value
                            item['mode']=info.mode.name
                            if int(info.mode)==0: item['value']=encoded(getter(did))
                        props[prop]=item
                constraints.append({'id':b.to_string(),'type':name,'owner_id':obj.to_string(),'properties':props})
    return {'scene_id':scene_id(view),'scene_name':view.name(),'character_id':cid,'joints':nodes,
            'bindings':bindings,'constraints':constraints,
            'rig_objects':control_objects,'tracks':tracks,'point_control_ids':sorted(controls),
            'pose_write_space':'global Point controller targets; rig computes joints',
            'identity_scope':'RigInfo owner/ObjectId UUIDs within this saved scene; import/regeneration may change IDs'}


def get_pose(view,scene,cid,frame,*,joint_ids=None,control_ids=None):
    """Default full character read; internal selectors never change write checks.

    Counts describe the complete identified character, not the selected values.
    None reads everything; an empty set deliberately reads no such values.
    """
    from .animation import check_frame
    check_frame(scene,frame)
    rig,joints,owned,controls=identify(scene,cid)
    selected_joints=joints
    selected_controls=controls
    if joint_ids is not None:
        if not set(joint_ids)<={o.to_string() for o in joints}:
            raise BridgeError('CHARACTER_READ_SELECTION_MISMATCH: joint outside identified character')
        selected_joints={o for o in joints if o.to_string() in joint_ids}
    if control_ids is not None:
        if not set(control_ids)<=controls.keys():
            raise BridgeError('CHARACTER_READ_SELECTION_MISMATCH: Point outside identified character')
        selected_controls={oid:o for oid,o in controls.items() if oid in control_ids}
    mv=scene.model_viewer()
    return {'scene_id':scene_id(view),'scene_name':view.name(),'character_id':cid,'frame':frame,
        'joints':{o.to_string():{'name':mv.get_object_name(o),**transform(scene,o,frame)} for o in sorted(selected_joints,key=lambda o:o.to_string())},
        'pose':{oid:{'position':transform(scene,o,frame)['global']['position']} for oid,o in sorted(selected_controls.items())},
        'joint_count':len(joints),'point_control_count':len(controls),'pose_space':'global native Point targets'}


def capture(scene):
    """Read all stored model data, settings, topology and tracks for Undo verification."""
    bv,mv,dv,lv=scene.behaviour_viewer(),scene.model_viewer(),scene.data_viewer(),scene.layers_viewer()
    count=dv.get_animation_size()
    objects=mv.get_objects()
    if not 1<=count<=121 or len(objects)>1024: raise BridgeError('SCENE_LIMIT: transaction capture bound exceeded')
    result={'count':count,'objects':{},'values':{},'static':{},'tracks':{}}
    for obj in objects:
        oid=obj.to_string()
        behaviours=[]
        for b in bv.get_behaviours(obj):
            props={}
            for name in bv.get_behaviour_property_names(b):
                kind=bv.get_property_type(b,name).name
                getters={'ObjectType':'get_behaviour_object','ObjectRangeType':'get_behaviour_objects_range',
                    'BehaviourType':'get_behaviour_reference','BehaviourRangeType':'get_behaviour_reference_range',
                    'DataType':'get_behaviour_data','DataRangeType':'get_behaviour_data_range',
                    'SettingType':'get_behaviour_setting','SettingRangeType':'get_behaviour_settings_range',
                    'AssetType':'get_behaviour_asset','AssetRangeType':'get_behaviour_asset_range','StringType':'get_behaviour_string'}
                if kind not in getters: raise BridgeError('UNSUPPORTED_PROPERTY: '+kind)
                value=encoded(getattr(bv,getters[kind])(b,name))
                if kind=='StringType': value=hashlib.sha256(value.encode()).hexdigest()
                props[name]=[kind,value]
            behaviours.append([b.to_string(),bv.get_behaviour_name(b),props])
        result['objects'][oid]={'name':mv.get_object_name(obj),'type':mv.get_object_type_name(obj),'behaviours':behaviours}
        for setting,ids in ((False,dv.get_all_data_id(obj)),(True,dv.get_all_settings_id(obj))):
            for did in ids:
                value_info=(dv.get_setting if setting else dv.get_data)(did)
                mode=int(value_info.mode)
                getter=dv.get_setting_value if setting else dv.get_data_value
                key=('s:' if setting else 'd:')+did.to_string()
                if mode==1: result['values'][key]=[encoded(getter(did,f)) for f in range(count)]
                else: result['static'][key]=encoded(getter(did))
    for lid,layer in lv.layers_map().items():
        result['tracks'][lid.to_string()]={'objects':sorted(encoded(layer.obj_ids)),'name':layer.header.name,
            'parent':layer.header.parent.to_string(),'locked':layer.is_locked,'sections':sections(layer)}
    return result


def geometry(scene,cid,frame):
    """Check rig connection anchors against their two live rigid-body transforms."""
    import numpy as np
    rig,joints,owned,controls=identify(scene,cid)
    bv,dv=scene.behaviour_viewer(),scene.data_viewer()
    worst=0.0
    checked=0
    for b in bv.get_behaviours('ConnectionPointTwoBody'):
        if bv.get_behaviour_owner(b) not in owned: continue
        points=[]
        for suffix in ('first','second'):
            rb=bv.get_behaviour_reference(b,'rigid_body_'+suffix)
            body=bv.get_behaviour_owner(rb)
            tr=bv.get_behaviour_by_name(body,'Transform')
            pos=dv.get_data_value(bv.get_behaviour_data(tr,'global_position'),frame)
            rot=dv.get_data_value(bv.get_behaviour_data(tr,'global_rotation'),frame).to_rotation_matrix()
            local=dv.get_data_value(bv.get_behaviour_data(b,'pos_local_'+suffix),frame) if dv.get_data(bv.get_behaviour_data(b,'pos_local_'+suffix)).mode.name=='Animation' else dv.get_data_value(bv.get_behaviour_data(b,'pos_local_'+suffix))
            points.append(np.asarray(pos)+np.asarray(rot)@np.asarray(local))
        error=float(np.linalg.norm(points[0]-points[1]))
        if not math.isfinite(error): raise BridgeError('NONFINITE_RIG: connection anchor')
        worst=max(worst,error)
        checked+=1
    return {'connection_count':checked,'max_connection_anchor_error':worst}


def journal(scene):
    # Keep the native scene alive for identity, reject accidental cross-scene reuse.
    key=id(scene)
    if key not in _journals: _journals[key]={'scene':scene,'entries':[],'locked':False}
    j=_journals[key]
    if j['locked']:
        raise BridgeError('RECOVERY_REQUIRED: prior rollback could not be verified',
                          execution_state='recovery_required',rollback_verified=False)
    return j


def save_snapshot(view,scene,cid):
    identify(scene,cid)
    if len(_snapshots)>=16: raise BridgeError('SNAPSHOT_LIMIT: save scene and restart to clear 16 character snapshots')
    j=journal(scene)
    snap=capture(scene)
    sid=uuid.uuid4().hex
    _snapshots[sid]={'scene':scene,'scene_id':scene_id(view),'character_id':cid,'state':snap,
                     'lineage':[e['id'] for e in j['entries']]}
    return {'scene_id':scene_id(view),'scene_name':view.name(),'character_id':cid,'snapshot_id':sid,
            'frame_count':snap['count'],'storage':'full-state guards plus bounded native history; expires on restart'}


def restore_native(scene,snap,known_states):
    """Undo until the full target state matches, never assume one Undo per pose.

    Native history includes playhead/selection actions. Every resulting model
    state must match a recorded C01 state (or the unchanged preceding state).
    Maximum 12 actions; no arbitrary external edit history is traversed.
    """
    import csc
    target=snap['state'];current=capture(scene)
    for steps in range(13):
        if equivalent(current,target): return steps
        if steps==12: raise BridgeError('RESTORE_STEP_LIMIT: target not reached within 12 native actions')
        if not any(equivalent(current,s) for s in known_states):
            raise BridgeError('RESTORE_HISTORY_MISMATCH: state outside recorded C01 transactions')
        csc.app.get_application().get_action_manager().call_action('Scene.Undo')
        after=capture(scene)
        if not equivalent(after,current) and not any(equivalent(after,s) for s in known_states):
            raise BridgeError('RESTORE_HISTORY_MISMATCH: native Undo yielded unrecorded state')
        current=after
    raise BridgeError('RESTORE_FAILED: unreachable target')


def _write_point(editor,did,frame,value):
    import numpy as np
    editor.data_editor().set_data_value(did,frame,np.asarray(value,dtype=np.float32))


def _verify_committed(scene,snapshot,verify,callback_state):
    """Validate synchronous native commit before admitting it to the journal.

    LayersEditor change_section may finalize only when modify_update returns.
    No event-loop yield is allowed between that return and this readback. On a
    failed postcondition, traverse only the states observed in this transaction.
    Callers must still verify recovery and lock the journal on recovery failure.
    """
    committed_state=capture(scene)
    try:
        return verify()
    except Exception:
        restore_native(scene,snapshot,[snapshot['state'],callback_state,committed_state])
        raise


def _transaction_failure(scene,before,transaction_journal,exc,snapshot_id,code,recovery_postcondition=None):
    """Attach state evidence only after capture succeeds and equality is checked."""
    restored=False
    recovery_error=None
    try:
        restored=equivalent(capture(scene),before)
        if restored and recovery_postcondition is not None:
            recovery_postcondition()
    except Exception as recovery_exc:
        restored=False
        recovery_error=type(recovery_exc).__name__
    if not restored:
        transaction_journal['locked']=True
    return BridgeError(code+': '+str(exc)+'; rollback_verified='+str(restored)+
                       '; recovery_error='+str(recovery_error)+'; snapshot_id='+snapshot_id,
                       execution_state='rolled_back' if restored else 'recovery_required',
                       rollback_verified=restored,recovery_snapshot_id=snapshot_id)


def set_pose(view,scene,cid,frame,pose):
    result=set_sequence(view,scene,cid,[{'frame':frame,'pose':pose}])
    native=result.pop('native_poses')[0]
    result['rig_metrics']=result['rig_metrics'][0]
    result['solver_adjustments']={key.split(':',1)[1]:value for key,value in result['solver_adjustments'].items()}
    return {**native,**result,'mcp_calls_for_pose_write':1}


def set_sequence(view,scene,cid,entries,postcondition=None,configure_tracks=None,after_interpolation=None,
                 *,write_control_ids=None,preserve_existing_keys=False,recovery_postcondition=None):
    """One native transaction, including every frame and postcondition.

    The callbacks are internal callables, never accepted from MCP or deserialized.
    postcondition must raise before commit on mismatch. Track configuration and
    bounded contact baking also run inside the same rollback boundary.
    """
    import csc
    started=time.perf_counter()
    rig,joints,owned,controls=identify(scene,cid)
    if not 1<=len(entries)<=8 or len({e['frame'] for e in entries})!=len(entries):
        raise BridgeError('INVALID_SEQUENCE: require 1-8 distinct frames')
    for entry in entries:
        if set(entry['pose'])!=set(controls): raise BridgeError('INCOMPLETE_CHARACTER_POSE: supply exactly all returned native Point IDs')
        if not 0<=entry['frame']<min(scene.data_viewer().get_animation_size(),121):
            raise BridgeError('FRAME_OUT_OF_RANGE: character writes require an existing stored frame (max 120)')
    bv,dv,lv=scene.behaviour_viewer(),scene.data_viewer(),scene.layers_viewer()
    write_ids=set(controls) if write_control_ids is None else set(write_control_ids)
    if not write_ids or write_ids-set(controls):
        raise BridgeError('INVALID_CONTROL_SELECTION: require a nonempty native Point subset',execution_state='not_started')
    if preserve_existing_keys and configure_tracks is not None:
        raise BridgeError('INVALID_EDIT_POLICY: preserving edits cannot configure tracks',execution_state='not_started')
    layers={lid:layer for lid,layer in lv.layers_map().items() if set(layer.obj_ids)&owned}
    if any(layer.is_locked or set(layer.obj_ids)-owned for layer in layers.values()):
        raise BridgeError('UNSAFE_TRACK: locked or shared with another character')
    # Preserve original IK/FK and fixation settings. Reject AI interpolation entirely.
    if any(int(s.interval.interpolation)==7 for layer in layers.values() for s in layer.sections.values()):
        raise BridgeError('UNSUPPORTED_AI_INTERPOLATION: no AI motion features in this phase')
    if any(int(s.interval.common.ik_fk)!=0 or (s.key is not None and int(s.key.common.ik_fk)!=0)
           for layer in layers.values() for s in layer.sections.values()):
        raise BridgeError('UNSUPPORTED_RIG_MODE: only verified native IK Point tracks are writable')
    j=journal(scene)
    if len(j['entries'])>=8: raise BridgeError('TRANSACTION_LIMIT: restore a snapshot or save/restart after 8 outstanding character transactions')
    snapshot=save_snapshot(view,scene,cid)
    before=_snapshots[snapshot['snapshot_id']]['state']
    fields={oid:bv.get_behaviour_data(bv.get_behaviour_by_name(controls[oid],'Transform'),'global_position') for oid in write_ids}
    mutation={'callback_error':None,'writes':0,'stage':'keys'}
    def verify():
        poses=[get_pose(view,scene,cid,e['frame']) for e in entries]
        adjustments={str(e['frame'])+':'+oid:max(abs(x-y) for x,y in zip(after['pose'][oid]['position'],patch['position']))
                     for e,after in zip(entries,poses) for oid,patch in e['pose'].items()}
        worst=max(adjustments.values())
        if worst>3.0:
            oid=max(adjustments,key=adjustments.get)
            raise BridgeError('RIG_TARGET_MISMATCH: solver adjustment exceeds 3 scene units: '+oid+
                              '; max_error='+str(worst))
        after_state=capture(scene)
        if before['count']!=after_state['count'] or before['tracks'].keys()!=after_state['tracks'].keys():
            raise BridgeError('TRACK_STRUCTURE_CHANGED: frame count or track set differs')
        if before['objects']!=after_state['objects'] or before['static']!=after_state['static']:
            raise BridgeError('RIG_STRUCTURE_CHANGED: topology, bindings or static constraints differ')
        for lid,old in before['tracks'].items():
            new=after_state['tracks'][lid]
            for k in ('objects','name','parent','locked'):
                if old[k]!=new[k]: raise BridgeError('TRACK_STRUCTURE_CHANGED: '+lid)
        metrics=[{'frame':e['frame'],**geometry(scene,cid,e['frame'])} for e in entries]
        if any(m['max_connection_anchor_error']>0.1 for m in metrics):
            raise BridgeError('RIG_CONNECTION_ERROR: rigid-body anchors separated')
        if postcondition: postcondition(after_state,poses)
        return poses,adjustments,worst,after_state,metrics
    def modify(editor,update,updater):
        try:
            le=editor.layers_editor()
            if configure_tracks is not None:
                configure_tracks(le,layers)
            for lid,layer in layers.items():
                if preserve_existing_keys:
                    continue
                for entry in entries:
                    le.set_fixed_interpolation_or_key_if_need(lid,entry['frame'],True)
                # A one-frame sample has terminal STEP. New intervals use ordinary
                # LINEAR interpolation while keeping the rig's original IK/FK mode.
                for f in list(scene.layers_viewer().layer(lid).sections):
                    if f<before['count']-1 and configure_tracks is None:
                        def linear(section): section.interval.interpolation=csc.layers.layer.Interpolation.LINEAR
                        le.change_section(f,lid,linear)
            for entry in entries:
                frame,pose=entry['frame'],entry['pose']
                mutation['stage']='point writes frame '+str(frame)
                for oid in sorted(write_ids):
                    _write_point(editor,fields[oid],frame,pose[oid]['position'])
                    mutation['writes']+=1
                mutation['stage']='rig update frame '+str(frame)
                updater.run_update(set(fields.values()),frame)
            ip=updater.get_interpolator()
            mutation['stage']='interpolator reload'
            ip.reload()
            mutation['stage']='interpolation'
            ip.interpolate()
            if after_interpolation is not None:
                mutation['stage']='bounded inbetween postprocess'
                after_interpolation(editor,updater)
            mutation['stage']='postcondition validation'
            mutation['verified']=verify()
        except Exception as exc:
            mutation['callback_error']=mutation['stage']+': '+type(exc).__name__+': '+str(exc)
            raise
    committed=False
    try:
        committed=scene.modify_update('C01: atomic character Point sequence',modify) is True
        if not committed or mutation['callback_error']:
            raise BridgeError('NATIVE_MODIFY_FAILED: '+str(mutation['callback_error']))
        poses,adjustments,worst,after_state,metrics=_verify_committed(
            scene,_snapshots[snapshot['snapshot_id']],verify,mutation['verified'][3])
        j['entries'].append({'id':uuid.uuid4().hex,'before':before,'after':after_state})
        return {'scene_id':scene_id(view),'character_id':cid,'native_poses':poses,
            'snapshot_id':snapshot['snapshot_id'],'joints_read':len(joints),'controls_written':len(write_ids)*len(entries),
            'frames_written':[e['frame'] for e in entries],
            'mcp_calls_for_sequence_write':1,'transaction_count':1,'rig_metrics':metrics,
            'solver_adjustments':{k:v for k,v in adjustments.items() if v>0.03},
            'max_target_adjustment':worst,
            'host_elapsed_ms':(time.perf_counter()-started)*1000}
    except Exception as exc:
        raise _transaction_failure(scene,before,j,exc,snapshot['snapshot_id'],'CHARACTER_POSE_FAILED',recovery_postcondition) from exc


def restore(view,scene,sid):
    snap=_snapshots.get(sid)
    if snap is None: raise BridgeError('SNAPSHOT_NOT_FOUND: unknown character snapshot')
    if scene!=snap['scene'] or scene_id(view)!=snap['scene_id']:
        raise BridgeError('SNAPSHOT_SCENE_MISMATCH: only original live scene')
    j=journal(scene)
    prefix=snap['lineage']
    if [e['id'] for e in j['entries'][:len(prefix)]]!=prefix or len(j['entries'])<len(prefix):
        raise BridgeError('SNAPSHOT_HISTORY_CHANGED: snapshot belongs to an abandoned branch')
    undone=len(j['entries'])-len(prefix)
    steps=0
    if undone:
        last=j['entries'][-1]
        if not equivalent(capture(scene),last['after']):
            raise BridgeError('EXTERNAL_EDIT_DETECTED: state changed outside C01')
        states=[s for e in j['entries'][len(prefix):] for s in (e['before'],e['after'])]
        try: steps=restore_native(scene,snap,states)
        except Exception as exc:
            j['locked']=True
            raise BridgeError('RESTORE_FAILED: '+str(exc),execution_state='recovery_required',
                              rollback_verified=False,recovery_snapshot_id=sid) from exc
        del j['entries'][len(prefix):]
    try:
        if not equivalent(capture(scene),snap['state']):
            raise BridgeError('SNAPSHOT_STATE_MISMATCH: external edit detected')
    except Exception as exc:
        j['locked']=True
        raise BridgeError('SNAPSHOT_STATE_MISMATCH: restore could not be verified',
                          execution_state='recovery_required',rollback_verified=False,
                          recovery_snapshot_id=sid) from exc
    return {'scene_id':scene_id(view),'scene_name':view.name(),'character_id':snap['character_id'],
            'snapshot_id':sid,'restored':True,'transactions_undone':undone,'native_undo_actions':steps,'frames_verified':snap['state']['count']}


def dispatch(view,scene,method,params):
    if 'scene_id' in params and params['scene_id']!=scene_id(view):
        raise BridgeError('SCENE_MISMATCH: wrong saved scene identity')
    if method=='list_characters':
        bv,mv=scene.behaviour_viewer(),scene.model_viewer()
        return {'scene_id':scene_id(view),'scene_name':view.name(),'characters':[
            {'character_id':bv.get_behaviour_owner(b).to_string(),'display_name':mv.get_object_name(bv.get_behaviour_owner(b)),
             'joint_count':len(bv.get_behaviour_objects_range(b,'related_joints'))} for b in bv.get_behaviours('RigInfo')]}
    if method=='restore_pose_snapshot': return restore(view,scene,params['snapshot_id'])
    cid=params['character_id']
    if method=='save_pose_snapshot': return save_snapshot(view,scene,cid)
    if method=='get_character_skeleton': return skeleton(view,scene,cid)
    if method=='get_character_pose': return get_pose(view,scene,cid,params['frame'])
    if method=='set_character_pose': return set_pose(view,scene,cid,params['frame'],params['pose'])
    raise BridgeError('UNKNOWN_METHOD: character adapter')
