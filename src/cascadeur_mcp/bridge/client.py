"""MCP-side file transport. Never manufactures a successful host response."""

import time
import uuid

from .protocol import (BridgeError, ID, TOKEN, METHODS, read_json, runtime_dir,
                       validate_params, write_json)
from .errors import describe_error, validate_remote_error
from . import compatibility
from ..tools.animation_schema import WRITE_METHODS


class BridgeClient:
    def __init__(self, root=None, timeout=20.0):
        self.root = root if root is not None else runtime_dir()
        self.timeout = timeout
        if not 0 < timeout <= 20:
            raise ValueError("timeout must be in (0, 20]")

    def call(self, method, params=None):
        phase = 'client_validation'
        rid = sid = request = response = result = failure = None
        is_write = isinstance(method, str) and method in WRITE_METHODS
        operation = method if isinstance(method, str) and method in METHODS else 'unknown'
        try:
            params = validate_params(method, {} if params is None else params)
            phase = 'client_session'
            try:
                session = read_json(self.root / 'session.json')
            except FileNotFoundError as exc:
                raise BridgeError('BRIDGE_UNAVAILABLE: start the bridge inside Cascadeur first') from exc
            sid, token = session.get('session'), session.get('token')
            if (not isinstance(sid, str) or not ID.fullmatch(sid)
                    or not isinstance(token, str) or not TOKEN.fullmatch(token)
                    or type(session.get('protocol')) is not int or session['protocol'] != 1):
                sid = None
                raise BridgeError('INVALID_SESSION: invalid bridge session descriptor')
            if is_write:
                status = compatibility.status(session.get('write_contract'))
                if status != 'COMPATIBLE':
                    raise BridgeError(status + ': no write request was published')
                # Recheck before publication. Never redirect a checked write to a
                # replacement session. A later restart can only cause uncertainty
                # in this pinned old session, not a write into the new one.
                try:
                    latest = read_json(self.root / 'session.json')
                except FileNotFoundError as exc:
                    raise BridgeError('HOST_SESSION_CHANGED: host exited before publication') from exc
                if latest != session:
                    raise BridgeError('HOST_SESSION_CHANGED: rediscover the host before writing')
            folder = self.root / sid
            rid = uuid.uuid4().hex
            request = folder / (rid + '.request.json')
            response = folder / (rid + '.response.json')
            deadline = time.monotonic() + self.timeout
            payload = {"version": 1, "id": rid, "session": sid, "token": token,
                       "expires_at": time.time() + self.timeout, "method": method, "params": params}
            if is_write:
                payload['write_contract'] = compatibility.describe()
            # Publication can succeed before write_json's temporary cleanup fails.
            phase = 'client_publish'
            write_json(request, payload)
            phase = 'client_response'
            while time.monotonic() < deadline:
                if response.exists():
                    data = read_json(response)
                    if data.get("id") != rid or data.get("session") != sid:
                        raise BridgeError("INVALID_RESPONSE: correlation does not match")
                    if type(data.get('ok')) is not bool:
                        raise BridgeError('INVALID_RESPONSE: status must be a boolean')
                    if data.get("ok") is not True:
                        details = validate_remote_error(data.get('error_details'), operation=operation, is_write=is_write)
                        if details is None:
                            code = 'INVALID_ERROR_DETAILS' if 'error_details' in data else 'HOST_ERROR'
                            details = describe_error(BridgeError(code), operation=operation,
                                is_write=is_write, phase=phase, legacy=True)
                        details.update(request_id=rid, session_id=sid)
                        raise BridgeError('HOST_ERROR: ' + details['code'], details=details)
                    if type(data.get("result")) is not dict:
                        raise BridgeError("INVALID_RESPONSE: result must be an object")
                    result = {**data['result'], 'request_id': rid, 'session': sid}
                    break
                time.sleep(0.05)
            else:
                if is_write:
                    raise BridgeError('WRITE_OUTCOME_UNKNOWN: read host state before retrying')
                raise BridgeError('BRIDGE_TIMEOUT: no live Cascadeur response before deadline')
        except Exception as exc:
            if isinstance(exc, BridgeError) and exc.details is not None:
                failure = exc
            else:
                details = describe_error(exc, operation=operation, is_write=is_write,
                                         phase=phase, request_id=rid, session_id=sid)
                failure = BridgeError(details['code'] + ': ' + details['message'], details=details)
        finally:
            cleanup_failed = False
            for path in (request, response):
                if path is not None:
                    try:
                        path.unlink(missing_ok=True)
                    except OSError:
                        cleanup_failed = True
            if cleanup_failed:
                if failure is not None:
                    failure.details['cleanup_failed'] = True
                elif result is not None:
                    result['transport_warnings'] = ['CLEANUP_FAILED']
        if failure is not None:
            raise failure
        return result
