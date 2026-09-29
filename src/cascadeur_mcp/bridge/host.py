"""Cascadeur host adapter, verified in Cascadeur 2026.2.2 on Windows.

Every csc call below is mapped to official sources in TECHNICAL_DISCOVERY.md.
Do not replace missing APIs with guessed aliases or background-thread calls.
"""

import os
import secrets
import sys
import threading
import time
import uuid

from .protocol import (BridgeError, ID, METHODS, check_path, read_json, runtime_dir,
                       validate_request, write_json)
from .permissions import make_private
from .errors import describe_error
from . import compatibility
from ..tools.animation_schema import WRITE_METHODS
from .. import __version__  # Frozen by package import in this host process.

_bridge = None


def dispatch(method, params):
    import csc
    # S3, S4: get_application() and Application.current_scene().
    app = csc.app.get_application()
    if app is None:
        raise BridgeError("NO_APPLICATION: csc returned no application")
    if method == 'get_bridge_capabilities':
        from .capabilities import describe
        return describe()
    if method == "ping_cascadeur":
        return {"host": "Cascadeur", "pid": os.getpid(), "python": sys.version,
                "thread_id": threading.get_ident(), "live_application": True}
    view = app.current_scene()
    if view is None:
        raise BridgeError("NO_SCENE: open a scene inside Cascadeur")
    # S6, S7, S8: view/domain/model access, enumeration and names.
    scene = view.domain_scene()
    from ..tools.animation_schema import SCHEMAS
    if method in SCHEMAS:
        from .animation import dispatch as animation_dispatch
        return animation_dispatch(view, scene, method, params)
    model = scene.model_viewer()
    objects = model.get_objects()
    if method == "get_scene_info":
        return {"scene_name": view.name(), "current_frame": scene.get_current_frame(),
                "object_count": len(objects), "pid": os.getpid()}
    if method == "get_objects":
        offset, limit = params["offset"], params["limit"]
        return {"scene_name": view.name(), "offset": offset, "total": len(objects),
                "objects": [{"name": model.get_object_name(obj),
                             "type": model.get_object_type_name(obj)}
                            for obj in objects[offset:offset + limit]],
                "identity_note": "Names may repeat; no writable object handles exposed."}
    raise BridgeError("UNKNOWN_METHOD: rejected by host dispatch")


class HostBridge:
    def __init__(self, root):
        self.root = check_path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        make_private(self.root)  # Before publishing a token or creating session files.
        self.session = uuid.uuid4().hex
        self.token = secrets.token_hex(32)
        self.folder = self.root / self.session
        self.folder.mkdir(mode=0o700)
        self.owner_thread = threading.get_ident()
        self.seen = set()
        self.timer = None

    def publish(self):
        if (self.root / "session.json").exists():
            raise BridgeError("SESSION_EXISTS: stop the existing bridge; verify stale PID before cleanup")
        write_json(self.root / "session.json", {"session": self.session, "token": self.token,
                                               "pid": os.getpid(), "protocol": 1,
                                               "bridge_package_version": __version__,
                                               "write_contract": compatibility.describe()})

    def tick(self):
        try:
            self._tick()
        except Exception as exc:
            # Transport/IO failures stop the timer and remain visible in stderr.
            self.last_transport_error = type(exc).__name__ + ': ' + str(exc)
            if self.timer is not None:
                self.timer.stop()
            print("C01 BRIDGE STOPPED: " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
            raise

    def _tick(self):
        if threading.get_ident() != self.owner_thread:
            raise BridgeError("WRONG_THREAD: bridge callback left its startup thread")
        # Bounded work per UI tick; generated file names cannot select other paths.
        handled = 0
        for request in self.folder.glob("*.request.json"):
            if handled >= 4:
                break
            handled += 1
            rid = request.name.removesuffix(".request.json")
            if not ID.fullmatch(rid):
                raise BridgeError("INVALID_FILENAME: unexpected request filename")
            response = self.folder / (rid + ".response.json")
            envelope = {"id": rid, "session": self.session}
            method = 'unknown'
            phase = 'host_validation'
            completed = False
            try:
                raw = read_json(request)
                candidate = raw.get('method')
                if isinstance(candidate, str) and candidate in METHODS:
                    method = candidate  # Classify rejected write requests conservatively.
                method, params = validate_request(raw, self.session, self.token, rid)
                if rid in self.seen:
                    raise BridgeError("DUPLICATE_REQUEST: already handled")
                if len(self.seen) >= 10000:
                    raise BridgeError("SESSION_LIMIT: restart bridge after 10000 requests")
                self.seen.add(rid)
                phase = 'host_dispatch'
                result = dispatch(method, params)
                completed = True
                phase = 'host_result'
                write_json(response, {**envelope, "ok": True, "result": result})
            except Exception as exc:
                details = describe_error(exc, operation=method, is_write=method in WRITE_METHODS,
                                         phase=phase, completed=completed)
                write_json(response, {**envelope, "ok": False,
                                      "error": details['code'] + ': ' + details['message'],
                                      "error_details": details})
            finally:
                request.unlink(missing_ok=True)
        # Late responses are bounded to this private session and expire after one minute.
        for response in self.folder.glob("*.response.json"):
            try:
                if time.time() - response.stat().st_mtime > 60:
                    response.unlink(missing_ok=True)
            except FileNotFoundError:
                # The MCP client claims/removes responses concurrently. A file
                # disappearing after enumeration is normal, not a host failure.
                continue


def start():
    """Call once on the initialized host's Qt thread, normally from scene_idle."""
    global _bridge
    if sys.version_info < (3, 10):
        raise BridgeError("UNSUPPORTED_PYTHON: candidate bridge requires embedded Python 3.10+")
    if _bridge is not None:
        raise BridgeError("ALREADY_STARTED: call stop() before starting again")
    try:
        from PySide6.QtCore import QCoreApplication, QThread, QTimer
    except ImportError as exc:
        raise BridgeError("UNSUPPORTED_HOST: PySide6 unavailable; inspect installed Cascadeur") from exc
    qt_app = QCoreApplication.instance()
    if qt_app is None or QThread.currentThread() != qt_app.thread():
        raise BridgeError("WRONG_THREAD: start from Cascadeur's Qt application thread")
    dispatch("ping_cascadeur", {})  # csc must work before any session is advertised.
    bridge = HostBridge(runtime_dir())
    bridge.timer = QTimer(qt_app)
    bridge.timer.setInterval(100)
    bridge.timer.timeout.connect(bridge.tick)
    try:
        bridge.publish()
        bridge.timer.start()
    except Exception:
        bridge.timer.deleteLater()
        raise
    _bridge = bridge
    qt_app.aboutToQuit.connect(stop)
    return {"started": True, "pid": os.getpid(), "runtime_dir": str(bridge.root)}


def stop():
    """Stop this process's bridge without deleting another process's descriptor."""
    global _bridge
    if _bridge is None:
        return {"stopped": False}
    if threading.get_ident() != _bridge.owner_thread:
        raise BridgeError("WRONG_THREAD: stop on the startup thread")
    release_scene_references()
    _bridge.timer.stop()
    path = _bridge.root / "session.json"
    if path.exists() and read_json(path).get("session") == _bridge.session:
        path.unlink()
    _bridge.timer.deleteLater()
    _bridge = None
    return {"stopped": True}


def release_scene_references():
    """Release native scene wrappers before Cascadeur destroys its C++ model."""
    for name in ('skeleton','character'):
        module=sys.modules.get('cascadeur_mcp.bridge.'+name)
        if module is not None:
            for field in ('_snapshots','_journals'):
                cache=getattr(module,field,None)
                if cache is not None: cache.clear()
    playback=sys.modules.get('cascadeur_mcp.bridge.playback')
    if playback is not None and playback._run:
        try: playback._run['timer'].stop()
        except RuntimeError: pass  # Qt may already have deleted a stopped timer.
        playback._run=None
