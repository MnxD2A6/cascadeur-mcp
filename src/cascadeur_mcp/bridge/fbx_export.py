"""Native FBX adapter. Official references and live provenance: Phase 8 report."""
import hashlib
import os
import uuid
from pathlib import Path
from . import character,polish
from .protocol import BridgeError
from ..tools.export_schema import output_path

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def export(view,scene,p):
    import csc
    app=csc.app.get_application()
    if not app.is_export_available(): raise BridgeError('EXPORT_UNAVAILABLE: activate/sync an official export entitlement')
    if character.scene_id(view)!=p['scene_id']: raise BridgeError('SCENE_MISMATCH')
    _,joints,owned,_=character.identify(scene,p['character_id'])
    bv=scene.behaviour_viewer();mv=scene.model_viewer()
    if len(bv.get_behaviours('RigInfo'))!=1: raise BridgeError('EXPORT_SCOPE: only one character is supported')
    exportable={o for o in mv.get_objects() if mv.get_object_type_name(o)=='Joint'}
    exportable|={bv.get_behaviour_owner(b) for b in bv.get_behaviours('MeshObject')}
    if not exportable<=owned: raise BridgeError('EXPORT_SCOPE: unrelated joints or meshes present')
    count=scene.data_viewer().get_animation_size()
    if p['options']['end_frame']!=count-1: raise BridgeError('EXPORT_RANGE: require the entire stored range 0..'+str(count-1))
    dst=output_path(p['output_path']);expected=p.get('expected_sha256')
    if dst.exists():
        if not expected or sha(dst)!=expected: raise BridgeError('EXPORT_CONFLICT: destination exists or changed; provide matching expected_sha256')
    elif expected: raise BridgeError('EXPORT_CONFLICT: expected destination is missing')
    before=character.capture(scene)
    saved=polish.dispatch(view,scene,'save_scene_copy',{'scene_id':p['scene_id'],'destination':p['source_copy_path']})
    # Cascadeur names the FBX Take after the basename. Randomize the directory,
    # never the basename, or Unity's clip local file ID breaks on every reimport.
    stage=dst.parent/('.c01-export-'+uuid.uuid4().hex)
    stage.mkdir()
    tmp=stage/dst.name
    try:
        settings=csc.fbx.FbxSettings()
        settings.mode=csc.fbx.FbxSettingsMode.Ascii
        settings.up_axis=csc.fbx.FbxSettingsAxis.Y
        settings.bake_animation=True
        settings.apply_euler_filter=True
        loader=app.get_tools_manager().get_tool('FbxSceneLoader').get_fbx_loader(view)
        loader.set_settings(settings)
        loader.export_all_objects(str(tmp))
        if not tmp.is_file() or tmp.stat().st_size<1024: raise BridgeError('EXPORT_FAILED: no usable output file')
        with tmp.open('rb') as stream: header=stream.read(128)
        if not header.startswith(b'; FBX '): raise BridgeError('EXPORT_FAILED: unexpected FBX header')
        if not character.equivalent(before,character.capture(scene)):
            raise BridgeError('EXPORT_STATE_CHANGED: native scene changed; saved copy retained, output not committed')
        if expected:
            if not dst.exists() or sha(dst)!=expected: raise BridgeError('EXPORT_CONFLICT: output changed during export')
            os.replace(tmp,dst)
        else:
            # Hard-link publication is exclusive: never silently overwrite a racing creator.
            os.link(tmp,dst);tmp.unlink()
        return {'exported':True,'path':str(dst),'bytes':dst.stat().st_size,'sha256':sha(dst),
            'saved_scene':saved,'scene_id':character.scene_id(view),'character_id':p['character_id'],
            'stored_frame_count':count,'options':p['options'],
            'settings':{'mode':'Ascii','up_axis':'Y','bake_animation':True,'apply_euler_filter':True},
            'scope':'whole single-character scene; selection ignored','scene_state_preserved':True}
    finally:
        tmp.unlink(missing_ok=True)
        stage.rmdir()
