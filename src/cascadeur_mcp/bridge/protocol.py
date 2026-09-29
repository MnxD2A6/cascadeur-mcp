"""Small stdlib-only wire format shared by the MCP and host processes."""

import json
import math
import os
import re
import time
import uuid
from pathlib import Path
from ..tools.animation_schema import SCHEMAS, validate as validate_animation

MAX_BYTES = 262144
ID = re.compile(r"[0-9a-f]{32}\Z")
TOKEN = re.compile(r"[0-9a-f]{64}\Z")
METHODS = {"ping_cascadeur", "get_scene_info", "get_objects"} | set(SCHEMAS)


class BridgeError(RuntimeError):
    """An explicit, client-visible failure."""


def runtime_dir():
    base = Path(os.environ["LOCALAPPDATA"]) if os.name == "nt" else Path.home() / ".cache"
    # Process configuration, never a tool argument. Separate host instances must
    # not compete for another live host's authenticated session descriptor.
    instance = os.environ.get('CASCADEUR_MCP_INSTANCE', 'c01')
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,31}', instance):
        raise BridgeError('INVALID_INSTANCE: expected a short lowercase instance name')
    return base / "cascadeur-mcp" / instance


def check_path(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise BridgeError("UNSAFE_PATH: bridge paths must not contain symlinks/junctions")
    return path


def read_json(path):
    path = check_path(path)
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise BridgeError("MESSAGE_TOO_LARGE: JSON exceeds 256 KiB")
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise BridgeError("INVALID_JSON: bridge message is not valid JSON") from exc
    if type(result) is not dict:
        raise BridgeError("INVALID_MESSAGE: expected a JSON object")
    return result


def write_json(path, data):
    path = check_path(path)
    raw = json.dumps(data, ensure_ascii=True, allow_nan=False).encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise BridgeError("MESSAGE_TOO_LARGE: JSON exceeds 256 KiB")
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        fd = os.open(str(tmp), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
        os.replace(str(tmp), str(path))
    finally:
        tmp.unlink(missing_ok=True)


def validate_params(method, params):
    if not isinstance(method, str) or method not in METHODS:
        raise BridgeError("UNKNOWN_METHOD: operation is not in the fixed tool allowlist")
    if type(params) is not dict:
        raise BridgeError("INVALID_PARAMS: expected an object")
    if method in SCHEMAS:
        try:
            return validate_animation(method, params)
        except ValueError as exc:
            raise BridgeError('INVALID_PARAMS: ' + str(exc)) from exc
    if method != "get_objects":
        if params:
            raise BridgeError("INVALID_PARAMS: this operation takes no parameters")
        return {}
    if set(params) - {"offset", "limit"}:
        raise BridgeError("INVALID_PARAMS: unknown pagination fields")
    offset, limit = params.get("offset", 0), params.get("limit", 100)
    if type(offset) is not int or not 0 <= offset <= 1000000:
        raise BridgeError("INVALID_PARAMS: offset must be an integer in [0, 1000000]")
    if type(limit) is not int or not 1 <= limit <= 200:
        raise BridgeError("INVALID_PARAMS: limit must be an integer in [1, 200]")
    return {"offset": offset, "limit": limit}


def validate_request(data, session, token, filename_id):
    if set(data) != {"version", "id", "session", "token", "expires_at", "method", "params"}:
        raise BridgeError("INVALID_REQUEST: unexpected or missing fields")
    if type(data["version"]) is not int or data["version"] != 1:
        raise BridgeError("INVALID_VERSION: expected protocol 1")
    if data["id"] != filename_id:
        raise BridgeError("INVALID_ID: filename and request ID differ")
    import secrets
    if (data["session"] != session or not isinstance(data["token"], str)
            or not secrets.compare_digest(data["token"], token)):
        raise BridgeError("UNAUTHORIZED: incorrect bridge session or token")
    expiry = data["expires_at"]
    if type(expiry) not in (int, float) or not math.isfinite(expiry):
        raise BridgeError("INVALID_EXPIRY: expected a finite timestamp")
    if not time.time() < expiry <= time.time() + 30:
        raise BridgeError("EXPIRED_REQUEST: deadline expired or exceeds 30 seconds")
    return data["method"], validate_params(data["method"], data["params"])
