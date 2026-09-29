"""Open, data-only single-pose snapshots. No native caches or vendor assets.

One frame is the contract. Restoring a key may recompute adjacent interpolation;
this is not a whole-scene backup or a substitute for the native .casc file.
"""
import hashlib
import json
import os
import re
from pathlib import Path
from . import character, semantics
from .protocol import BridgeError, runtime_dir
from ..tools.semantic_schema import validate_pose, SLOTS

MAX_BYTES=2*1024*1024
FORMAT='cascadeur-mcp.semantic-pose'

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def checked_path(value):
    if type(value) is not str or not 1<=len(value)<=240 or any(ord(c)<32 for c in value):
        raise ValueError('path must be a bounded absolute JSON filename')
    path=Path(value)
    if not path.is_absolute() or path.suffix.lower()!='.json' or '..' in path.parts:
        raise ValueError('path must be absolute, end in .json, and contain no traversal')
    if os.name=='nt' and (str(path).startswith('\\\\') or ':' in str(path)[2:]):
        raise ValueError('UNC, device paths and alternate streams are not allowed')
    if os.name=='nt':
        from pathlib import PureWindowsPath
        if any(PureWindowsPath(part).is_reserved() or part.endswith((' ','.'))
               or any(c in part for c in '<>"|?*') for part in path.parts[1:]):
            raise ValueError('reserved device names, ambiguous suffixes and invalid path characters are not allowed')
    for part in (path,*path.parents):
        try: info=part.lstat()
        except FileNotFoundError: continue
        if part.is_symlink() or getattr(info,'st_file_attributes',0)&0x400:
            raise ValueError('snapshot paths must not contain symlinks or reparse points')
    if not path.parent.is_dir(): raise ValueError('snapshot parent directory must already exist')
    root=runtime_dir().parent.resolve()
    if path.resolve().is_relative_to(root):
        raise ValueError('snapshot must be outside the private bridge runtime')
    return path

def save(view,scene,cid,path,frame=None):
    path=checked_path(path)
    if path.exists(): raise BridgeError('SNAPSHOT_EXISTS: choose a new path; snapshots never overwrite files')
    if frame is None: frame=scene.get_current_frame()
    rig=semantics.mapping(view,scene,cid)
    native=character.get_pose(view,scene,cid,frame)
    state=character.capture(scene)
    payload={'format':FORMAT,'version':1,'scope':'single-key-pose','profile':rig['profile'],
        'character_id':cid,'rig_fingerprint':rig['fingerprint'],'frame':frame,
        'frame_count':state['count'],'static_sha256':digest(state['static']),
        'objects_sha256':digest(state['objects']),
        'pose':semantics.encode_pose(rig,native['pose']),
        'reference_joints':native['joints'],
        'tolerance':{'position_scene_units':0.01,'quaternion_component':0.0001}}
    envelope={'payload':payload,'sha256':digest(payload)}
    raw=json.dumps(envelope,indent=2,allow_nan=False).encode('utf-8')
    if len(raw)>MAX_BYTES: raise BridgeError('SNAPSHOT_TOO_LARGE')
    # Exclusive creation prevents overwriting user files, including concurrent saves.
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return {'saved':True,'path':str(path),'sha256':envelope['sha256'],'bytes':len(raw),
            'frame':frame,'character_id':cid,'rig_fingerprint':rig['fingerprint'],
            'scope':'single-key-pose','storage':'portable JSON; no session/native-history dependency'}

def load(path):
    path=checked_path(path)
    with path.open('rb') as stream: raw=stream.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES: raise BridgeError('SNAPSHOT_TOO_LARGE')
    def pairs(items):
        result={}
        for k,v in items:
            if k in result: raise ValueError('duplicate JSON field')
            result[k]=v
        return result
    def bad_constant(s): raise ValueError('nonfinite JSON constant '+s)
    try:
        envelope=json.loads(raw,object_pairs_hook=pairs,parse_constant=bad_constant)
        if type(envelope) is not dict or set(envelope)!={'payload','sha256'}: raise ValueError('invalid envelope')
        p=envelope['payload']
        expected={'format','version','scope','profile','character_id','rig_fingerprint','frame','frame_count',
                  'static_sha256','objects_sha256','pose','reference_joints','tolerance'}
        if type(p) is not dict or set(p)!=expected: raise ValueError('invalid payload fields')
        if envelope['sha256']!=digest(p): raise ValueError('checksum mismatch')
        if p['format']!=FORMAT or type(p['version']) is not int or p['version']!=1 or p['scope']!='single-key-pose':
            raise ValueError('unsupported snapshot format/version/scope')
        if p['profile']!='cascy-points-v1': raise ValueError('unsupported profile')
        from ..tools.character_schema import validate
        validate({'character_id':p['character_id'],'frame':p['frame']})
        if type(p['frame_count']) is not int or not 1<=p['frame_count']<=121 or p['frame']>=p['frame_count']:
            raise ValueError('invalid frame bounds')
        for key in ('rig_fingerprint','static_sha256','objects_sha256'):
            if type(p[key]) is not str or not re.fullmatch('[0-9a-f]{64}',p[key]): raise ValueError('invalid guard hash')
        validate_pose(p['pose'])
        if set(p['pose'])!=set(SLOTS) or any(set(p['pose'][r])!=set(SLOTS[r]) for r in SLOTS):
            raise ValueError('durable snapshot must include all roles and slots')
        if p['tolerance']!={'position_scene_units':0.01,'quaternion_component':0.0001}:
            raise ValueError('snapshot cannot change recovery tolerances')
        refs=p['reference_joints']
        if type(refs) is not dict or not 1<=len(refs)<=128: raise ValueError('invalid reference joints')
        for oid,joint in refs.items():
            validate({'character_id':oid})
            if type(joint) is not dict or set(joint)!={'name','local','global'} or type(joint['name']) is not str:
                raise ValueError('invalid joint reference fields')
            for space in ('local','global'):
                t=joint[space]
                if type(t) is not dict or set(t)!={'position','rotation_wxyz'}: raise ValueError('invalid transform reference')
                from ..tools.animation_schema import validate as transform_validate
                transform_validate('set_transform',{'scene':'snapshot','object':'reference','frame':p['frame'],**t})
        return p,envelope['sha256']
    except (ValueError,TypeError,KeyError,RecursionError) as exc:
        raise BridgeError('INVALID_SNAPSHOT: '+str(exc)) from exc

def restore(view,scene,cid,path):
    payload,checksum=load(path)
    rig=semantics.mapping(view,scene,cid)
    if payload['character_id']!=cid or payload['rig_fingerprint']!=rig['fingerprint']:
        raise BridgeError('SNAPSHOT_RIG_MISMATCH: rediscover the original saved rig')
    before=character.capture(scene)
    if (before['count']!=payload['frame_count'] or digest(before['static'])!=payload['static_sha256']
        or digest(before['objects'])!=payload['objects_sha256']):
        raise BridgeError('SNAPSHOT_STRUCTURE_MISMATCH: frame bounds, rig/settings or topology changed')
    frame=payload['frame']
    current=character.get_pose(view,scene,cid,frame)
    if set(payload['reference_joints'])!=set(current['joints']): raise BridgeError('SNAPSHOT_JOINT_SET_MISMATCH')
    native=semantics.expand(rig,current['pose'],payload['pose'])
    def verify(state,poses):
        actual=poses[0]
        if not character.equivalent(actual['joints'],payload['reference_joints']):
            raise BridgeError('DURABLE_POSE_MISMATCH: rig did not reproduce saved joint state; transaction must roll back')
        if not character.equivalent(actual['pose'],native):
            raise BridgeError('DURABLE_CONTROL_MISMATCH: saved native Point state not reproduced')
    # v1 already stores every finger's local rotation in reference_joints. Body
    # Point targets alone cannot restore these independently animated channels.
    from . import hands
    finger_links=hands.bindings(scene,cid)
    def restore_fingers(editor,updater):
        import csc
        changed=set()
        for group in finger_links.values():
            for obj,did in group.values():
                q=payload['reference_joints'][obj.to_string()]['local']['rotation_wxyz']
                editor.data_editor().set_data_value(did,frame,csc.math.Rotation.from_quaternion(*q))
                changed.add(did)
        updater.run_update(changed,frame)
        ip=updater.get_interpolator();ip.reload();ip.interpolate()
    # Restoring a pose does not authorize resetting the entire clip to LINEAR.
    # Existing interpolation/weights are retained; key insertion remains native.
    result=character.set_sequence(view,scene,cid,[{'frame':frame,'pose':native}],postcondition=verify,
                                  configure_tracks=lambda editor,layers:None,
                                  after_interpolation=restore_fingers)
    result.pop('native_poses')
    return {**result,'restored':True,'path':str(path),'sha256':checksum,'frame':frame,
            'scope':'single-key-pose','joints_verified':len(current['joints']),
            'adjacent_interpolation':'recomputed by native rig; not a whole-clip snapshot'}

def dispatch(view,scene,method,params):
    if params['scene_id']!=character.scene_id(view): raise BridgeError('SCENE_MISMATCH')
    if method=='save_pose_snapshot': return save(view,scene,params['character_id'],params['path'],params.get('frame'))
    return restore(view,scene,params['character_id'],params['path'])
