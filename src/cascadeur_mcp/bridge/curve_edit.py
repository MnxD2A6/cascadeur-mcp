"""Bounded existing-key editing; installed API provenance is documented separately.

No curve authoring or arbitrary action execution. Unsupported additive/cycle/
custom tangent state is refused because the current snapshot cannot restore it.
"""
import copy
import math
from . import character
from .protocol import BridgeError


def _id(value):
    return character.encoded(value)


def _metadata(scene):
    result={}
    for lid,layer in scene.layers_viewer().layers_map().items():
        result[_id(lid)]={
            'sections':character.sections(layer),
            'descriptions':{str(f):s.interval.description_for_ai_interpolation
                            for f,s in layer.sections.items()},
        }
    return copy.deepcopy(result)


def _unsupported_state(scene,count):
    import csc
    manager=csc.additive_layers.get_manager(scene)
    stack_count=manager.get_stacked_layers_count()
    if type(stack_count) is not int or stack_count<0:
        raise BridgeError('CURVE_STATE_UNAVAILABLE: invalid additive layer count')
    if stack_count:
        raise BridgeError('UNSUPPORTED_ADDITIVE_LAYERS: additive state cannot be fully restored')
    for layer in scene.layers_viewer().layers_map().values():
        if csc.layers.CyclesViewer(layer).any_cycles_exist_in_frames(0,count-1):
            raise BridgeError('UNSUPPORTED_CYCLES: cycle state is outside the recovery snapshot')
        if any(s.key is not None and int(s.key.tangents)!=0 for s in layer.sections.values()):
            raise BridgeError('UNSUPPORTED_CUSTOM_TANGENTS: full-scene custom spatial tangents cannot be verified')


class CurveGuard:
    def __init__(self,scene,cid,before,metadata,protected,point_keys,fixed_tracks):
        self.scene,self.cid=scene,cid
        self.before,self.metadata=before,metadata
        self.protected,self.point_keys=protected,point_keys
        self.fixed_tracks=fixed_tracks
        self.max_anchor_error=None

    def verify(self,after,poses):
        _unsupported_state(self.scene,self.before['count'])
        if after['tracks']!=self.before['tracks'] or _metadata(self.scene)!=self.metadata:
            raise BridgeError('CURVE_METADATA_CHANGED: track/key/interpolation/easing state differs')
        if after['values'].keys()!=self.before['values'].keys():
            raise BridgeError('CURVE_DATA_CHANGED: animated channel set differs')
        for key in self.protected:
            old,new=self.before['values'][key],after['values'][key]
            same=(old==new) if key.startswith('s:') else character.equivalent(old,new)
            if not same:
                raise BridgeError('PROTECTED_CURVE_DATA_CHANGED: unedited baked/external/settings channel '+key)
        for key,frames in self.point_keys.items():
            if any(not character.equivalent(self.before['values'][key][f],after['values'][key][f])
                   for f in frames):
                raise BridgeError('UNEDITED_KEY_CHANGED: untouched authored Point key '+key)
        worst=max(character.geometry(self.scene,self.cid,f)['max_connection_anchor_error']
                  for f in range(self.before['count']))
        if not math.isfinite(worst) or worst>.1:
            raise BridgeError('INTERPOLATED_RIG_CONNECTION_ERROR: full clip anchors differ')
        self.max_anchor_error=worst

    def verify_recovery(self):
        _unsupported_state(self.scene,self.before['count'])
        if _metadata(self.scene)!=self.metadata:
            raise BridgeError('CURVE_RECOVERY_FAILED: curve metadata was not restored')

    def report(self):
        return {'verified':True,'key_layout_and_track_metadata':'exact',
                'interpolation_easing_tangent_mode':'exact',
                'fixed_tracks_protected':len(self.fixed_tracks),
                'protected_animated_channels':len(self.protected),
                'frames_verified':self.before['count'],
                'max_connection_anchor_error':self.max_anchor_error,
                'additive_stacks':0,'cycles':False,'custom_tangents':False,
                'trajectory_shape_preserved':False,
                'scope':'metadata preservation; selected paths and solver-coupled rig Points/Joints at edited frames may change'}


def preflight(scene,cid,frames,edited_ids):
    """Read all safety state before a snapshot/write; absence never means safe."""
    try:
        _,_,owned,controls=character.identify(scene,cid)
        if not edited_ids or set(edited_ids)-set(controls):
            raise BridgeError('INVALID_CONTROL_SELECTION: require native Point IDs')
        count=scene.data_viewer().get_animation_size()
        if not 1<=count<=121:
            raise BridgeError('CLIP_LIMIT: at most 121 stored frames')
        _unsupported_state(scene,count)
        layers=scene.layers_viewer().layers_map()
        fixed=set();point_keys={};found=set()
        for lid,layer in layers.items():
            members=set(_id(o) for o in layer.obj_ids)
            if not set(layer.obj_ids) & owned:
                continue
            if layer.is_locked or set(layer.obj_ids)-owned:
                raise BridgeError('UNSAFE_TRACK: locked or shared character track')
            selected=members & set(edited_ids)
            found.update(selected)
            for frame,s in layer.sections.items():
                if s.key is not None:
                    if int(s.key.tangents)!=0:
                        raise BridgeError('UNSUPPORTED_CUSTOM_TANGENTS: spatial tangent state cannot be verified')
                    weights=(s.key.left_weight_velocity,s.key.right_weight_velocity)
                    if any(not math.isfinite(w) for w in weights):
                        raise BridgeError('CURVE_STATE_UNAVAILABLE: nonfinite easing weight')
                mode=int(s.interval.interpolation)
                if mode not in (0,1,2,3,4,6) or (selected and mode==4):
                    raise BridgeError('UNSUPPORTED_EDIT_TRACK: selected tracks require classic non-baked interpolation')
                if mode==4: fixed.add(_id(lid))
            if selected and any(f not in layer.sections or layer.sections[f].key is None for f in frames):
                raise BridgeError('CURVE_KEY_REQUIRED: every requested frame must already be a key on edited tracks')
            for obj in layer.obj_ids:
                if _id(obj) not in controls: continue
                untouched=[f for f,s in layer.sections.items() if s.key is not None
                           and f not in frames]
                # IK Point global targets are authored; local transforms,
                # velocity caches and other solver-derived data may recompute.
                bv=scene.behaviour_viewer()
                did=bv.get_behaviour_data(bv.get_behaviour_by_name(obj,'Transform'),'global_position')
                point_keys['d:'+_id(did)]=untouched
        if found!=set(edited_ids):
            raise BridgeError('UNSAFE_TRACK: selected control has no verified track')
        before=character.capture(scene)
        fixed_objects={_id(obj) for lid,layer in layers.items() if _id(lid) in fixed for obj in layer.obj_ids}
        protected={k for k in before['values'] if k.startswith('s:')}
        for obj in scene.model_viewer().get_objects():
            if obj not in owned or _id(obj) in fixed_objects:
                protected.update('d:'+_id(did) for did in scene.data_viewer().get_all_data_id(obj))
        protected &= before['values'].keys()
        point_keys={k:v for k,v in point_keys.items() if k in before['values']}
        return CurveGuard(scene,cid,before,_metadata(scene),protected,point_keys,fixed)
    except BridgeError:
        raise
    except Exception as exc:
        raise BridgeError('CURVE_STATE_UNAVAILABLE: required native curve state could not be read') from exc
