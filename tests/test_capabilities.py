"""Offline manifest contracts only; these tests do not exercise Cascadeur."""

import importlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

import pytest


def describe():
    spec = importlib.util.find_spec('cascadeur_mcp.bridge.capabilities')
    assert spec is not None, 'The loaded-host capability manifest is not implemented'
    return importlib.import_module('cascadeur_mcp.bridge.capabilities').describe()


def test_manifest_reports_package_version_without_claiming_application_version():
    manifest = describe()
    project = Path(__file__).resolve().parents[1] / 'pyproject.toml'
    package_version = re.search(r'^version = "([^"]+)"$', project.read_text(), re.M).group(1)
    assert manifest['schema_version'] == 1
    assert manifest['protocol_version'] == 1
    assert manifest['host'] == {
        'name': 'Cascadeur',
        'pid': os.getpid(),
        'python_version': sys.version.split()[0],
        'bridge_package_version': package_version,
        'application_version': None,
        'application_version_status': 'NOT_REPORTED',
    }


def test_every_protocol_operation_has_a_conservative_read_write_classification():
    from cascadeur_mcp.bridge.protocol import METHODS
    from cascadeur_mcp.tools.animation_schema import WRITE_METHODS

    operations = describe()['operations']
    assert set(operations) == METHODS
    assert {name for name, entry in operations.items() if entry['classification'] == 'write'} == WRITE_METHODS
    assert operations['save_pose_snapshot']['classification'] == 'write'
    assert operations['play_animation']['classification'] == 'write'
    assert operations['get_fbx_export_status']['classification'] == 'read'
    assert operations['ping_cascadeur']['requires_scene'] is False
    assert operations['get_scene_info']['requires_scene'] is True
    assert all(entry['runtime_preconditions'] == 'NOT_EVALUATED' for entry in operations.values())


def test_reported_request_bounds_match_enforced_schema_bounds():
    from cascadeur_mcp.bridge.protocol import BridgeError, MAX_BYTES, validate_params
    from cascadeur_mcp.tools.animation_schema import SCHEMAS

    limits = describe()['limits']
    assert limits['transport']['message_bytes_max'] == MAX_BYTES
    validate_params('get_objects', {'limit': limits['object_page_size_max']})
    with pytest.raises(BridgeError):
        validate_params('get_objects', {'limit': limits['object_page_size_max'] + 1})
    assert limits['pose_sequence_frames_max'] == SCHEMAS['set_pose_sequence']['properties']['poses']['maxItems']
    assert limits['hand_sequence_frames_max'] == SCHEMAS['set_hand_pose_sequence']['properties']['poses']['maxItems']
    assert limits['character_frame_index_max'] == SCHEMAS['get_character_pose']['properties']['frame']['maximum']
    assert limits['character_stored_frames_max'] == limits['character_frame_index_max'] + 1
    assert limits['joint_snapshots'] == {'normal_slots': 31, 'restore_reserved_slots': 1}


def test_manifest_does_not_turn_unexamined_runtime_conditions_into_availability(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setitem(sys.modules, 'csc', None)
    monkeypatch.setitem(sys.modules, 'PySide6', None)
    manifest = describe()
    assert manifest['runtime_checks'] == {
        'scene': 'NOT_EVALUATED',
        'rig_compatibility': 'NOT_EVALUATED',
        'track_write_safety': 'NOT_EVALUATED',
        'export_entitlement': 'NOT_EVALUATED',
        'native_operation_success': 'NOT_EVALUATED',
    }
    assert 'available' not in manifest
    assert 'writable' not in manifest
    assert 'live_application' not in manifest['host']
    assert json.loads(json.dumps(manifest, allow_nan=False)) == manifest
    assert len(json.dumps(manifest).encode()) < 262144
    assert list(tmp_path.iterdir()) == []


def test_callers_cannot_mutate_the_next_capability_response():
    first = describe()
    first['operations']['ping_cascadeur']['classification'] = 'write'
    first['limits']['joint_snapshots']['normal_slots'] = 0
    second = describe()
    assert second['operations']['ping_cascadeur']['classification'] == 'read'
    assert second['limits']['joint_snapshots']['normal_slots'] == 31
