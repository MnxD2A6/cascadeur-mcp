"""Loaded write-contract identity, independent of package marketing versions.

Increment WRITE_REVISION for incompatible semantics, validation or error evidence
changes even when JSON schemas are unchanged. Restart both processes after source
updates; hot reload is unsupported. This is not rig or license validation.
"""
import hashlib
import json
import re

from ..tools.animation_schema import SCHEMAS, WRITE_METHODS

PROTOCOL_VERSION = 1
WRITE_REVISION = 2


def schema_fingerprint(schemas):
    raw = json.dumps(schemas, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=True, allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


# Capture this process's imported schema, never read mutable source files.
_SCHEMA_SHA256 = schema_fingerprint({name: SCHEMAS[name] for name in sorted(WRITE_METHODS)})


def describe():
    return {'protocol_version': PROTOCOL_VERSION, 'revision': WRITE_REVISION,
            'schema_sha256': _SCHEMA_SHA256}


def status(remote):
    if remote is None:
        return 'HOST_UPGRADE_REQUIRED'
    if (type(remote) is not dict or set(remote) != {'protocol_version', 'revision', 'schema_sha256'}
            or type(remote.get('protocol_version')) is not int or remote['protocol_version'] < 1
            or type(remote.get('revision')) is not int or remote['revision'] < 1
            or type(remote.get('schema_sha256')) is not str
            or re.fullmatch(r'[0-9a-f]{64}', remote['schema_sha256']) is None):
        return 'INVALID_HOST_CONTRACT'
    return 'COMPATIBLE' if remote == describe() else 'INCOMPATIBLE_HOST'
