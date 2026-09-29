"""Cascy semantic profile derived from verified names AND native rig references.

No list offsets, nearest-point heuristics, hardcoded Joint UUIDs or writable
Joint transforms. Unknown/duplicated profiles fail closed.
"""
import hashlib
import json
from . import character
from .protocol import BridgeError
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
            'identity_scope':'UUIDs within saved rig; names plus native relationships validate profile; import/regeneration requires rediscovery',
            'unbound_helper_policy':'foot heel Self0: unique exact name, Point type and RigInfo membership; no invented box reference'}

def mapping(view,scene,cid):
    return build_map(character.skeleton(view,scene,cid))

def encode_pose(mapping, native):
    return {role:{slot:native[c['control_id']]['position'] for slot,c in group['controls'].items()}
            for role,group in mapping['roles'].items()}

def expand(mapping, native, patch):
    result={oid:{'position':list(item['position'])} for oid,item in native.items()}
    for role,slots in patch.items():
        for slot,value in slots.items():
            result[mapping['roles'][role]['controls'][slot]['control_id']]={'position':list(value)}
    return result

def get_pose(view,scene,cid,frame,rig=None):
    rig=rig or mapping(view,scene,cid)
    native=character.get_pose(view,scene,cid,frame)
    return {'scene_id':native['scene_id'],'character_id':cid,'frame':frame,
            'profile':rig['profile'],'fingerprint':rig['fingerprint'],
            'pose':encode_pose(rig,native['pose']),
            'joint_state':{role:native['joints'][group['joint_state']['joint_id']] for role,group in rig['roles'].items()},
            'joint_state_writable':False}

def dispatch(view,scene,method,params):
    if 'scene_id' in params and params['scene_id']!=character.scene_id(view):
        raise BridgeError('SCENE_MISMATCH: wrong saved scene identity')
    cid=params['character_id'];rig=mapping(view,scene,cid)
    if method=='get_rig_semantics': return rig
    if method=='get_semantic_pose': return get_pose(view,scene,cid,params['frame'],rig)
    entries=params['poses'] if method=='set_pose_sequence' else [{'frame':params['frame'],'pose':params['pose']}]
    native=[]
    for entry in entries:
        old=character.get_pose(view,scene,cid,entry['frame'])['pose']
        native.append({'frame':entry['frame'],'pose':expand(rig,old,entry['pose'])})
    result=character.set_sequence(view,scene,cid,native)
    result.pop('native_poses')
    return {**result,'profile':rig['profile'],'fingerprint':rig['fingerprint'],
            'poses':[get_pose(view,scene,cid,e['frame'],rig) for e in entries]}
