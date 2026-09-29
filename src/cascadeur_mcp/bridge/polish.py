"""Native timing/curves experiment. Sources and limits: POLISH_DISCOVERY.md."""
import hashlib
import math
from . import character
from .protocol import BridgeError

def inspect(view,scene,cid):
    _,_,owned,_=character.identify(scene,cid)
    bv,dv=scene.behaviour_viewer(),scene.data_viewer()
    count=dv.get_animation_size()
    if not 1<=count<=121: raise BridgeError('CLIP_LIMIT: max 121 frames')
    bodies=[b for b in bv.get_behaviours('RigidBody') if bv.get_behaviour_owner(b) in owned]
    coms=bv.get_behaviours('CenterOfMass')
    def data(b,n,f):
        did=bv.get_behaviour_data(b,n)
        return character.encoded(dv.get_data_value(did,f) if int(dv.get_data(did).mode)==1 else dv.get_data_value(did))
    frames=[]
    for f in range(count):
        mass=0.;total=[0.,0.,0.]
        for b in bodies:
            m=data(b,'mass',f)
            # RigidBody.position is an offset. Transform.global_position is the
            # live rigid-body center in world space (checked against native COM).
            p=character.transform(scene,bv.get_behaviour_owner(b),f)['global']['position']
            if not math.isfinite(m) or m<0: raise BridgeError('INVALID_RIG_MASS')
            mass+=m
            total=[t+m*x for t,x in zip(total,p)]
        if mass<=0: raise BridgeError('NO_RIG_MASS')
        frames.append({'frame':f,'mass_weighted_com':[x/mass for x in total],
            'native_com':[{'id':bv.get_behaviour_owner(b).to_string(),
                'transform':character.transform(scene,bv.get_behaviour_owner(b),f),
                'target':data(b,'pos_global_target',f)} for b in coms],
            **character.geometry(scene,cid,f)})
    return {'scene_id':character.scene_id(view),'character_id':cid,'rigid_body_count':len(bodies),
        'total_mass':mass,'frames':frames,'tracks':character.skeleton(view,scene,cid)['tracks']}

def retime(view,scene,cid,keys,stabilize_contacts=False):
    import csc
    source=[k['source'] for k in keys]
    target=[k['target'] for k in keys]
    _,_,owned,_=character.identify(scene,cid)
    layers={lid:layer for lid,layer in scene.layers_viewer().layers_map().items() if set(layer.obj_ids)&owned}
    if not layers or any(list(layer.key_frame_indices())!=source or sorted(layer.sections)!=source for layer in layers.values()):
        raise BridgeError('KEY_LAYOUT_MISMATCH: all character tracks must have exactly the supplied source keys')
    originals=[character.get_pose(view,scene,cid,f) for f in source]
    saved_sections={lid:dict(layer.sections) for lid,layer in layers.items()}
    entries=[{'frame':f,'pose':p['pose']} for f,p in zip(target,originals)]
    contacts={};contact_report={}
    if stabilize_contacts:
        from . import semantics
        rig=semantics.mapping(view,scene,cid)
        for role,slots in [('left_foot',('center','heel','toe','toe_direction','toe_orientation')),
                           ('right_foot',('toe','toe_direction','toe_orientation'))]:
            for slot in slots:
                oid=rig['roles'][role]['controls'][slot]['control_id']
                anchor=originals[0]['pose'][oid]['position']
                if any(math.dist(p['pose'][oid]['position'],anchor)>.02 for p in originals):
                    raise BridgeError('MOVING_CONTACT: profile requires stationary left foot and right toes at all keys')
                contacts[oid]=anchor
    def configure(le,layers):
        for lid in layers:
            le.set_sections({k['target']:saved_sections[lid][k['source']] for k in keys},lid)
            for k in keys:
                def edit(s,k=k):
                    if k['target']!=target[-1]: s.interval.interpolation=getattr(csc.layers.layer.Interpolation,k['interpolation'])
                    s.key.left_weight_velocity=k['left_weight']
                    s.key.right_weight_velocity=k['right_weight']
                le.change_section(k['target'],lid,edit)
    errors={}
    def stabilize(editor,updater):
        # Bake only the two native foot tracks. Retain original key poses and
        # the intentionally lifting right heel; pin the eight support targets.
        bv,lv=scene.behaviour_viewer(),scene.layers_viewer()
        _,_,_,controls=character.identify(scene,cid)
        ids={oid:bv.get_behaviour_data(bv.get_behaviour_by_name(controls[oid],'Transform'),'global_position') for oid in contacts}
        foot_lids={lv.layer_id_by_obj_id(controls[oid]) for oid in contacts}
        for lid in foot_lids:
            for f in target[:-1]:
                def fixed(s): s.interval.interpolation=csc.layers.layer.Interpolation.FIXED
                editor.layers_editor().change_section(f,lid,fixed)
        count=scene.data_viewer().get_animation_size()
        for f in range(count):
            if f in target: continue
            for oid,anchor in contacts.items(): character._write_point(editor,ids[oid],f,anchor)
            updater.run_update(set(ids.values()),f)
        updater.get_interpolator().reload()
        worst=max(math.dist(character.get_pose(view,scene,cid,f)['pose'][oid]['position'],anchor)
                  for f in range(count) for oid,anchor in contacts.items())
        contact_report.update(max_planted_error=worst,baked_tracks=len(foot_lids),
                              point_writes=(count-len(target))*len(contacts))
        if worst>.03: raise BridgeError('CONTACT_STABILITY_FAILED: '+str(worst))
    def verify(state,poses):
        for old,new in zip(originals,poses):
            if not character.equivalent(old['joints'],new['joints']):
                raise BridgeError('KEY_POSE_CHANGED: joint state differs after retiming')
            errors[str(new['frame'])]=max(abs(a-b) for oid,p in old['pose'].items()
                for a,b in zip(p['position'],new['pose'][oid]['position']))
        if max(errors.values())>.01: raise BridgeError('KEY_POSE_CHANGED: Point error exceeds .01')
        if any(list(scene.layers_viewer().layer(lid).key_frame_indices())!=target for lid in layers):
            raise BridgeError('KEY_READBACK_MISMATCH')
        if max(character.geometry(scene,cid,f)['max_connection_anchor_error']
               for f in range(scene.data_viewer().get_animation_size()))>.1:
            raise BridgeError('INTERPOLATED_RIG_CONNECTION_ERROR')
    result=character.set_sequence(view,scene,cid,entries,verify,configure,stabilize if stabilize_contacts else None)
    result.pop('native_poses')
    return {**result,'source_frames':source,'target_frames':target,'key_pose_point_errors':errors,'contacts':contact_report}

def dispatch(view,scene,method,p):
    if 'scene_id' in p and p['scene_id']!=character.scene_id(view): raise BridgeError('SCENE_MISMATCH')
    if method=='get_fbx_export_status':
        # Official Application.is_export_available / FbxSceneLoader APIs;
        # live 2026.2.2 evidence is in PHASE8_UNITY_BRIDGE_REPORT.md.
        import csc
        app=csc.app.get_application()
        available=bool(app.is_export_available())
        loader=app.get_tools_manager().get_tool('FbxSceneLoader').get_fbx_loader(view)
        return {'scene_name':view.name(),'scene_id':character.scene_id(view),
                'export_available':available,'loader_type':type(loader).__name__,
                'loader_methods':[n for n in dir(loader) if n.startswith('export_') and callable(getattr(loader,n))],
                'export_verified':False,
                'status':'AVAILABLE_NOT_VALIDATED' if available else 'EXPORT_UNAVAILABLE',
                'message':'Runtime capability check only; no FBX was generated. Export success, range, axes and scale require a real file and Unity validation.'}
    if method=='inspect_character_motion': return inspect(view,scene,p['character_id'])
    if method=='retime_character_motion': return retime(view,scene,p['character_id'],p['keys'],p.get('stabilize_contacts',False))
    if method=='save_scene_copy':
        from ..tools.polish_schema import native_path
        path=native_path(p['destination'])
        # Reserve with exclusive creation. The native saver replaces our empty
        # reservation; arbitrary pre-existing destination files are rejected.
        with path.open('xb'): pass
        view.save(str(path))
        if not path.exists() or path.stat().st_size<1024: raise BridgeError('NATIVE_SAVE_FAILED: inspect reserved destination')
        return {'saved':True,'path':str(path),'bytes':path.stat().st_size,
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'scene_id':character.scene_id(view)}
    raise BridgeError('UNKNOWN_METHOD: polish')
