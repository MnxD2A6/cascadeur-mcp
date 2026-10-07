"""Persistent explicit rollback-failure fence; no unchecked unlock operation.

Only an active authenticated HostBridge request binds the storage location.
The local file contains our own bounded model-state representation, not assets.
This does not detect every mid-write process/power failure.
"""
from contextlib import contextmanager
import hashlib
import json
import math
import os
import uuid

from .protocol import BridgeError, check_path, ID

MAX_BYTES = 16 * 1024 * 1024
_active = None


def _blocked(message):
    return BridgeError('RECOVERY_REQUIRED: '+message,
                       execution_state='recovery_required', rollback_verified=False)


@contextmanager
def host_context(root, session):
    global _active
    previous = _active
    _active = {'root': check_path(root), 'session': session, 'ticket': None}
    try:
        yield
    finally:
        _active = previous


def _raw(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def _state(value):
    if (type(value) is not dict or set(value) != {'count','objects','values','static','tracks'}
            or type(value['count']) is not int or not 1 <= value['count'] <= 121
            or any(type(value[k]) is not dict for k in ('objects','values','static','tracks'))
            or len(value['objects']) > 1024):
        raise ValueError('invalid bounded checkpoint state')
    budget = [1000000]
    def visit(item, depth=0):
        budget[0] -= 1
        if budget[0] < 0 or depth > 48: raise ValueError('checkpoint nesting/size limit')
        if type(item) is dict:
            if any(type(k) is not str for k in item): raise ValueError('invalid key')
            for v in item.values(): visit(v, depth+1)
        elif type(item) is list:
            for v in item: visit(v, depth+1)
        elif type(item) is float:
            if not math.isfinite(item): raise ValueError('nonfinite checkpoint')
        elif item is not None and type(item) not in (str,int,bool):
            raise ValueError('invalid checkpoint value')
    visit(value)


def read(root):
    """Static local inspection; malformed/existing unsafe files never mean clear."""
    path = check_path(root / 'recovery-required.json')
    try:
        with path.open('rb') as stream: raw = stream.read(MAX_BYTES+1)
    except FileNotFoundError:
        return None
    if len(raw) > MAX_BYTES: raise ValueError('recovery fence exceeds bound')
    value = json.loads(raw)
    fields = {'version','id','host_pid','host_session','checkpoint','checkpoint_sha256'}
    if (type(value) is not dict or set(value) != fields or type(value['version']) is not int
            or value['version'] != 1 or type(value['id']) is not str or not ID.fullmatch(value['id'])
            or type(value['host_pid']) is not int or value['host_pid'] <= 0
            or type(value['host_session']) is not str or not ID.fullmatch(value['host_session'])):
        raise ValueError('invalid recovery fence envelope')
    _state(value['checkpoint'])
    if value['checkpoint_sha256'] != hashlib.sha256(_raw(value['checkpoint'])).hexdigest():
        raise ValueError('recovery checkpoint checksum mismatch')
    return value


def persist(checkpoint):
    if _active is None: return  # Direct offline adapter tests do not install a host.
    _active['ticket'] = None
    try:
        _state(checkpoint)
        value = {'version':1, 'id':uuid.uuid4().hex, 'host_pid':os.getpid(),
                 'host_session':_active['session'], 'checkpoint':checkpoint,
                 'checkpoint_sha256':hashlib.sha256(_raw(checkpoint)).hexdigest()}
        raw = _raw(value)
        if len(raw) > MAX_BYTES: raise ValueError('recovery checkpoint exceeds bound')
        path = check_path(_active['root'] / 'recovery-required.json')
        tmp = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
        try:
            with tmp.open('xb') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            os.replace(tmp, path)
        finally:
            tmp.unlink(missing_ok=True)
    except Exception as exc:
        raise _blocked('session is locked, but durable fence could not be saved; '
                       'restart safety is NOT guaranteed ('+type(exc).__name__+').') from exc


def status(scene):
    base = {'scope':'MCP instance; explicit character recovery failures only',
            'persistent':_active is not None, 'automatic_retry_allowed':False,
            'whole_clip_checkpoint_required':True, 'read_only':True,
            'unexpected_mid_write_crash_covered':False}
    if _active is None:
        return {**base, 'status':'HOST_CONTEXT_UNAVAILABLE', 'writes_blocked':True,
                'next_step':'Inspect through the running authenticated Cascadeur bridge.'}
    try:
        record = read(_active['root'])
    except Exception:
        return {**base, 'status':'INVALID_RECOVERY_RECORD', 'writes_blocked':True,
                'next_step':'Stop editing. Preserve the recovery record for diagnosis; do not delete it to bypass protection.'}
    if record is None:
        return {**base, 'status':'NO_PERSISTENT_RECOVERY_LOCK', 'writes_blocked':False,
                'next_step':'Other native and session-local write checks still apply.'}
    if record['host_session'] == _active['session']:
        return {**base, 'status':'RECOVERY_REQUIRED', 'writes_blocked':True,
                'next_step':'Preserve a NEW quarantine copy; normally reopen the latest verified pre-failure native checkpoint in a new host session.'}
    try:
        from . import character
        matches = character.equivalent(record['checkpoint'], character.capture(scene))
    except Exception:
        return {**base, 'status':'CHECKPOINT_VERIFICATION_UNAVAILABLE', 'writes_blocked':True,
                'next_step':'The complete saved model state could not be checked. Stop writes and inspect the supported checkpoint.'}
    if not matches:
        return {**base, 'status':'CHECKPOINT_MISMATCH', 'writes_blocked':True,
                'next_step':'Restart did not restore the scene. Open the latest verified native checkpoint matching the recorded pre-failure state; a one-pose JSON is insufficient.'}
    return {**base, 'status':'VERIFIED_CHECKPOINT_READY', 'writes_blocked':False,
            'next_step':'Complete pre-failure state matches. Other write checks still apply; the fence is retained until a write succeeds.'}


def require_recovered(scene):
    if _active is None: return
    result = status(scene)
    if result['writes_blocked']:
        raise _blocked(result['status']+'; '+result['next_step'])
    if result['status'] == 'VERIFIED_CHECKPOINT_READY':
        # Verify record identity again; never delete a replacement failure record.
        _active['ticket'] = read(_active['root'])['id']


def complete_write():
    """Only a successful checked write can acknowledge a verified checkpoint."""
    if _active is None or _active['ticket'] is None: return
    try:
        record = read(_active['root'])
        if record is None or record['id'] != _active['ticket']:
            raise ValueError('recovery fence changed during request')
        check_path(_active['root'] / 'recovery-required.json').unlink()
        _active['ticket'] = None
    except Exception as exc:
        # The native operation already completed; do not claim it was undone.
        raise BridgeError('RECOVERY_ACK_FAILED: write completed but fence could not be '
                          'acknowledged; read back before further action',
                          execution_state='completed') from exc
