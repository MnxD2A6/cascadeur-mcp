"""Observed native Timeline.Play toggle; Qt timer ONLY observes, never animates."""
import time
from .protocol import BridgeError
from .character import scene_id

_run = None

def require_idle():
    if _run and _run['status'] in ('checking','playing','stopping'):
        raise BridgeError('PLAYBACK_ACTIVE: stop owned playback and verify before editing')

def public():
    return {k:v for k,v in _run.items() if k not in ('view','scene','timer','started','last_change','observed')}

def dispatch(view,scene,method,params):
    global _run
    import csc
    from PySide6.QtCore import QTimer,QCoreApplication
    if params['scene_id']!=scene_id(view): raise BridgeError('SCENE_MISMATCH: playback scene identity')
    if method=='stop_animation':
        if _run is None or _run['scene_id']!=scene_id(view):
            raise BridgeError('NO_OWNED_PLAYBACK: cannot toggle externally started playback')
        if _run['status']=='playing':
            csc.app.get_application().get_action_manager().call_action('Timeline.Play')
            _run['status']='stopping'; _run['stop_at']=time.perf_counter()-_run['started']
        elif _run['status']=='checking':
            _run['timer'].stop();_run['status']='cancelled'
        return public()
    require_idle()
    start,end=params['start_frame'],params['end_frame']
    if end>=scene.data_viewer().get_animation_size(): raise BridgeError('FRAME_OUT_OF_RANGE: playback requires existing frames')
    timer=QTimer(QCoreApplication.instance());timer.setInterval(10)
    _run={'scene_id':scene_id(view),'scene_name':view.name(),'start_frame':start,'end_frame':end,
          'status':'checking','samples':[],'frame_set_calls':0,'native_play_calls':0,'stop_verified':False,
          'view':view,'scene':scene,'timer':timer,'started':time.perf_counter(),
          'observed':scene.get_current_frame(False),'last_change':0.0}
    run=_run
    def tick():
        try:
            app=csc.app.get_application()
            if app.current_scene()!=view:
                raise BridgeError('SCENE_CHANGED: cannot toggle playback on another scene')
            elapsed=time.perf_counter()-run['started'];frame=scene.get_current_frame(False)
            if frame!=run['observed']: run['last_change']=elapsed
            run['observed']=frame
            if run['status']=='checking':
                if frame!=run.get('initial_frame',frame):
                    raise BridgeError('EXTERNAL_PLAYBACK: frame moved during stopped-state check')
                run['initial_frame']=frame
                if elapsed>=0.3:
                    boundary=view.animation_boundary();boundary.first_frame=start;boundary.last_frame=end
                    scene.set_current_frame(start);run['frame_set_calls']=1
                    app.get_action_manager().call_action('Timeline.Play');run['native_play_calls']=1
                    run['status']='playing';run['play_at']=elapsed
            elif run['status']=='playing':
                run['samples'].append({'elapsed_seconds':elapsed,'frame':frame})
                previous=run['samples'][-2]['frame'] if len(run['samples'])>1 else start
                if frame>=end or frame<previous or elapsed-run['play_at']>8:
                    app.get_action_manager().call_action('Timeline.Play')
                    run['status']='stopping';run['stop_at']=elapsed
            elif run['status']=='stopping' and elapsed-run['stop_at']>=0.3:
                run['stop_verified']=run['last_change']<=run['stop_at']+0.06
                run['final_frame']=frame
                frames=[s['frame'] for s in run['samples']]
                run['continuous_playback_observed']=len(set(frames))>=3 and max(frames)>=end-1
                run['status']='stopped' if run['stop_verified'] else 'failed'
                timer.stop();timer.deleteLater()
        except Exception as exc:
            run['status']='failed';run['error']=type(exc).__name__+': '+str(exc)
            timer.stop();timer.deleteLater()
    timer.timeout.connect(tick);timer.start()
    return public()
