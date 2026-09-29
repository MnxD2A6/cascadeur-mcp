"""MCP-side file transport. Never manufactures a successful host response."""

import time
import uuid

from .protocol import (BridgeError, ID, TOKEN, read_json, runtime_dir,
                       validate_params, write_json)
from ..tools.animation_schema import WRITE_METHODS


class BridgeClient:
    def __init__(self, root=None, timeout=20.0):
        self.root = root if root is not None else runtime_dir()
        self.timeout = timeout
        if not 0 < timeout <= 20:
            raise ValueError("timeout must be in (0, 20]")

    def call(self, method, params=None):
        params = validate_params(method, {} if params is None else params)
        try:
            session = read_json(self.root / "session.json")
        except FileNotFoundError as exc:
            raise BridgeError("BRIDGE_UNAVAILABLE: start the bridge inside Cascadeur first") from exc
        sid, token = session.get("session"), session.get("token")
        if (not isinstance(sid, str) or not ID.fullmatch(sid)
                or not isinstance(token, str) or not TOKEN.fullmatch(token)):
            raise BridgeError("INVALID_SESSION: invalid bridge session descriptor")
        folder = self.root / sid
        rid = uuid.uuid4().hex
        request = folder / (rid + ".request.json")
        response = folder / (rid + ".response.json")
        deadline = time.monotonic() + self.timeout
        try:
            write_json(request, {"version": 1, "id": rid, "session": sid, "token": token,
                                "expires_at": time.time() + self.timeout,
                                "method": method, "params": params})
            while time.monotonic() < deadline:
                if response.exists():
                    data = read_json(response)
                    if data.get("id") != rid or data.get("session") != sid:
                        raise BridgeError("INVALID_RESPONSE: correlation does not match")
                    if data.get("ok") is not True:
                        raise BridgeError("HOST_ERROR: " + str(data.get("error", "missing error")))
                    if type(data.get("result")) is not dict:
                        raise BridgeError("INVALID_RESPONSE: result must be an object")
                    return {"request_id": rid, "session": sid, **data["result"]}
                time.sleep(0.05)
            if method in WRITE_METHODS:
                raise BridgeError(f'WRITE_OUTCOME_UNKNOWN: request {rid}; session {sid}; timed out. Read host state before retrying.')
            raise BridgeError("BRIDGE_TIMEOUT: no live Cascadeur response before deadline")
        finally:
            request.unlink(missing_ok=True)
            response.unlink(missing_ok=True)
