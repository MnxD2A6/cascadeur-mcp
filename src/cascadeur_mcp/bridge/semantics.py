"""Cascy semantic profile derived from verified names AND native rig references.

No list offsets, nearest-point heuristics, hardcoded Joint UUIDs or writable
Joint transforms. Unknown/duplicated profiles fail closed.
"""
import hashlib
import json
from . import character
from .protocol import BridgeError
from .edit_impact import build as build_edit_impact
from ..tools.semantic_schema import SLOTS

JOINTS = {'pelvis':'pelvis','chest':'chest','head':'head'}
for side,suffix in [('left','l'),('right','r')]:
    JOINTS.update({side+'_hand':'hand_'+suffix,side+'_elbow':'forearm_'+suffix,
                  side+'_foot':'foot_'+suffix,side+'_knee':'calf_'+suffix})

POINTS = {
 'pelvis':dict(zip(SLOTS['pelvis'], ['pelvis_MainPoint','pelvis_AdditionalPoint','thigh_MainPoint_l','thigh_MainPoint_r'])),
 'chest':dict(zip(SLOTS['chest'], ['stomach_MainPoint','stomach_AdditionalPoint','chest_MainPoint','chest_AdditionalPoint',
             'clavicle_MainPoint_l','clavicle_AdditionalPoint_l','arm_MainPoint_l',
             'clavicle_MainPoint_r','clavicle_AdditionalPoint_r','arm_MainPoint_r'])),
 'head':dict(zip(SLOTS['head'], ['neck_MainPoint','neck_AdditionalPoint','head_MainPoint','head_DirectionPoint','head_AdditionalPoint'])),
}
for side,suffix in [('left','l'),('right','r')]:
    for role,names in [('hand',['hand_MainPoint','hand_DirectionPoint','hand_AdditionalPoint']),
                       ('elbow',['forearm_MainPoint','forearm_AdditionalPoint']),
                       ('foot',['foot_MainPoint','foot_Self0Point','toe_MainPoint','toe_DirectionPoint','toe_AdditionalPoint']),
                       ('knee',['calf_MainPoint','calf_AdditionalPoint'])]:
        POINTS[side+'_'+role]=dict(zip(SLOTS[side+'_'+role], [n+'_'+suffix for n in names]))

PARENTS={'pelvis':None,'stomach':'pelvis','chest':'stomach','neck':'chest','head':'neck'}
for suffix in ('l','r'):
    for chain in (['chest','clavicle_'+suffix,'arm_'+suffix,'forearm_'+suffix,'hand_'+suffix],
                  ['pelvis','thigh_'+suffix,'calf_'+suffix,'foot_'+suffix,'toe_'+suffix]):
        PARENTS.update(zip(chain[1:],chain[:-1]))

def build_map(skeleton):
    objects=skeleton['joints']+skeleton['rig_objects']
    by_name={}
    for obj in objects: by_name.setdefault(obj['name'],[]).append(obj)
    def unique(name,kind):
        matches=by_name.get(name,[])
        if len(matches)!=1 or matches[0]['type']!=kind:
            raise BridgeError('UNSUPPORTED_SEMANTIC_RIG: expected unique '+kind+' '+name)
        return matches[0]
    joint_ids={name:unique(name,'Joint')['id'] for name in PARENTS}
    for name,parent in PARENTS.items():
        if unique(name,'Joint')['parent_id']!=(joint_ids[parent] if parent else None):
            raise BridgeError('SEMANTIC_HIERARCHY_MISMATCH: '+name)
    bindings={}
    for binding in skeleton['bindings']:
        if binding['joint'] in bindings: raise BridgeError('AMBIGUOUS_RIG_BINDING')
        bindings[binding['joint']]=binding
    # Every canonical named Point must be confirmed through RigAdditionalInfo.
    # Two Self0 foot helper Points have no such reference: their exact unique
    # name, native Point type and RigInfo membership are explicit profile guards.
    roles={};seen=set()
    for role,slots in POINTS.items():
        controls={}
        for slot,name in slots.items():
            obj=unique(name,'Point');oid=obj['id']
            if oid not in skeleton['point_control_ids'] or oid in seen:
                raise BridgeError('SEMANTIC_CONTROL_MEMBERSHIP_MISMATCH: '+name)
            seen.add(oid)
            if '_Self0Point_' not in name:
                stem,point=name.split('_',1)
                suffix=('_'+name[-1]) if name.endswith(('_l','_r')) else ''
                joint_name=stem+suffix
                prop={'MainPoint':'main_point','DirectionPoint':'direction_point','AdditionalPoint':'additional_point'}[point.removesuffix(suffix)]
                binding=bindings.get(joint_ids[joint_name],{})
                if binding.get(prop)!=oid:
                    raise BridgeError('SEMANTIC_BINDING_MISMATCH: '+name)
            controls[slot]={'control_id':oid,'name':name,'readable':True,'writable':True,
                            'semantic_role':role,'control_type':'Point.global_position'}
        jid=joint_ids[JOINTS[role]]
        roles[role]={'semantic_role':role,'readable':True,'writable':True,'control_type':'Point target group',
            'controls':controls,'joint_state':{'joint_id':jid,'name':JOINTS[role],
                'readable':True,'writable':False,'semantic_role':role,'control_type':'driven Joint'}}
    if seen!=set(skeleton['point_control_ids']): raise BridgeError('INCOMPLETE_SEMANTIC_PROFILE: unmapped native Points')
    identity={'character_id':skeleton['character_id'],'roles':roles,
              'hierarchy':sorted((o['id'],o['parent_id']) for o in skeleton['joints']),
              'bindings':sorted(skeleton['bindings'],key=lambda b:b['box_id'])}
    fingerprint=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    return {'profile':'cascy-points-v1','character_id':skeleton['character_id'],
            'scene_id':skeleton['scene_id'],'fingerprint':fingerprint,'roles':roles,
            'coordinate_space':'world positions in native scene units',
            'hand_shape_note':'Hand Point targets move/orient the palm; they do not curl fingers. Use get_hand_pose and set_hand_pose_sequence for verified Cascy finger-local channels.',
            'identity_scope':'UUIDs within saved rig; names plus native relationships validate profile; import/regeneration requires rediscovery',
            'unbound_helper_policy':'foot heel Self0: unique exact name, Point type and RigInfo membership; no invented box reference'}

def mapping(view,scene,cid):
    return build_map(character.skeleton(view,scene,cid))

def encode_pose(mapping, native, roles=None):
    return {role:{slot:native[c['control_id']]['position'] for slot,c in group['controls'].items()}
            for role,group in mapping['roles'].items() if roles is None or role in roles}

def select_pose(result,roles=None,include_joint_state=True):
    """Select response fields without rounding values or changing rig identity."""
    selected={**result,'pose':{role:pose for role,pose in result['pose'].items()
                             if roles is None or role in roles}}
    if include_joint_state:
        selected['joint_state']={role:state for role,state in result['joint_state'].items()
                                 if roles is None or role in roles}
    else:
        selected.pop('joint_state',None)
    return selected

def expand(mapping, native, patch):
    result={oid:{'position':list(item['position'])} for oid,item in native.items()}
    for role,slots in patch.items():
        for slot,value in slots.items():
            result[mapping['roles'][role]['controls'][slot]['control_id']]={'position':list(value)}
    return result

def get_pose(view,scene,cid,frame,rig=None,roles=None,include_joint_state=True):
    rig=rig or mapping(view,scene,cid)
    selected_roles=[role for role in rig['roles'] if roles is None or role in roles]
    control_ids={c['control_id'] for role in selected_roles
                 for c in rig['roles'][role]['controls'].values()}
    joint_ids=({rig['roles'][role]['joint_state']['joint_id'] for role in selected_roles}
               if include_joint_state else set())
    native=character.get_pose(view,scene,cid,frame,joint_ids=joint_ids,control_ids=control_ids)
    result={'scene_id':native['scene_id'],'character_id':cid,'frame':frame,
            'profile':rig['profile'],'fingerprint':rig['fingerprint'],
            'pose':encode_pose(rig,native['pose'],selected_roles),
            'joint_state':{role:native['joints'][rig['roles'][role]['joint_state']['joint_id']]
                           for role in selected_roles if include_joint_state},
            'joint_state_writable':False}
    return select_pose(result,roles,include_joint_state)

def _check_frames(scene,frames):
    from .animation import check_frame
    for frame in frames: check_frame(scene,frame)


def offset_sequence(view,scene,params,*,preserve_curves=False):
    """Preflight all targets, then enter the existing checked transaction once."""
    from ..tools.character_schema import validate as validate_native_targets
    cid=params['character_id']
    try:
        if params['scene_id']!=character.scene_id(view):
            raise BridgeError('SCENE_MISMATCH: wrong saved scene identity')
        rig=mapping(view,scene,cid)
        _check_frames(scene,params['frames'])
        guard=None
        if preserve_curves:
            from . import curve_edit
            edited_ids={c['control_id'] for role in params['offsets']
                        for c in rig['roles'][role]['controls'].values()}
            guard=curve_edit.preflight(scene,cid,params['frames'],edited_ids)
        entries=[]
        baselines={}
        for frame in params['frames']:
            old=character.get_pose(view,scene,cid,frame,joint_ids=set())['pose']
            if preserve_curves: baselines[frame]=old
            patch={role:{slot:[old[c['control_id']]['position'][i]+delta[i] for i in range(3)]
                         for slot,c in rig['roles'][role]['controls'].items()}
                   for role,delta in params['offsets'].items()}
            pose=expand(rig,old,patch)
            # Recheck every final absolute target, including untouched Points.
            # Input offsets being bounded does not imply the sums are bounded.
            validate_native_targets({'pose':pose})
            entries.append({'frame':frame,'pose':pose})
    except Exception as exc:
        message=str(exc) if isinstance(exc,BridgeError) else 'PREFLIGHT_FAILED: '+str(exc)
        raise BridgeError(message,execution_state='not_started') from exc
    # No catch around the transaction: preserve verified rollback/recovery errors.
    if preserve_curves:
        impact={}
        def verify_with_impact(after,poses):
            guard.verify(after,poses)
            impact['report']=build_edit_impact(rig,baselines,entries,poses,
                                             selected_roles=params['offsets'])
        result=character.set_sequence(view,scene,cid,entries,postcondition=verify_with_impact,
                                     write_control_ids=edited_ids,preserve_existing_keys=True,
                                     recovery_postcondition=guard.verify_recovery)
        result['curve_preservation']=guard.report()
        result['edit_impact']={**impact['report'],'protection':result['curve_preservation']}
    else:
        result=character.set_sequence(view,scene,cid,entries)
    result.pop('native_poses')
    return {**result,'profile':rig['profile'],'fingerprint':rig['fingerprint'],
            'offsets':{role:list(delta) for role,delta in params['offsets'].items()},
            'coordinate_space':rig['coordinate_space'],
            'poses':[get_pose(view,scene,cid,e['frame'],rig,roles=params['offsets'],
                              include_joint_state=False) for e in entries]}


def require_sampling_range(view,scene):
    boundary=view.animation_boundary()
    end=scene.data_viewer().get_animation_size()-1
    if boundary.first_frame>0 or boundary.first_visible_frame>0 or boundary.last_frame<end or boundary.last_visible_frame<end:
        raise BridgeError('FULL_TIMELINE_RANGE_REQUIRED: play/stop the full stored range before sampled motion so native Undo can refresh every frame',execution_state='not_started')


def dispatch(view,scene,method,params):
    if method=='offset_semantic_pose_sequence_preserving_curves':
        return offset_sequence(view,scene,params,preserve_curves=True)
    if method=='offset_semantic_pose_sequence': return offset_sequence(view,scene,params)
    if 'scene_id' in params and params['scene_id']!=character.scene_id(view):
        raise BridgeError('SCENE_MISMATCH: wrong saved scene identity')
    if params.get('sampled_motion',False):require_sampling_range(view,scene)
    cid=params['character_id'];rig=mapping(view,scene,cid)
    if method=='get_rig_semantics': return rig
    if method=='get_semantic_pose':
        return get_pose(view,scene,cid,params['frame'],rig,roles=params.get('roles'),
                        include_joint_state=params.get('include_joint_state',True))
    if method=='get_semantic_pose_sequence':
        _check_frames(scene,params['frames'])
        return {key:rig[key] for key in ('scene_id','character_id','profile','fingerprint')} | {
            'poses':[get_pose(view,scene,cid,frame,rig,roles=params.get('roles'),
                              include_joint_state=params.get('include_joint_state',True))
                     for frame in params['frames']]}
    entries=params['poses'] if method=='set_pose_sequence' else [{'frame':params['frame'],'pose':params['pose']}]
    native=[]
    for entry in entries:
        old=character.get_pose(view,scene,cid,entry['frame'])['pose']
        native.append({'frame':entry['frame'],'pose':expand(rig,old,entry['pose'])})
    sampled=params.get('sampled_motion',False)
    result=character.set_sequence(view,scene,cid,native,entry_limit=64 if sampled else 8)
    actual=result.pop('native_poses')
    if sampled:
        import hashlib,json
        digests=[{'frame':p['frame'],'native_point_sha256':hashlib.sha256(json.dumps(p['pose'],sort_keys=True,allow_nan=False).encode()).hexdigest()} for p in actual]
        result.pop('solver_adjustments',None)
        return {**result,'profile':rig['profile'],'fingerprint':rig['fingerprint'],
                'sampled_motion':True,'sample_count':len(entries),'actual_point_hashes':digests,
                'poses_omitted':True,'readback_tool':'get_semantic_pose_sequence'}
    return {**result,'profile':rig['profile'],'fingerprint':rig['fingerprint'],
            'poses':[get_pose(view,scene,cid,e['frame'],rig) for e in entries]}
