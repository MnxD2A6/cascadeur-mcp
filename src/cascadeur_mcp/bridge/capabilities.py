"""Describe this process's bridge contract without probing native runtime state.

The host dispatcher verifies its csc application before calling describe().
Calling this function from ordinary Python is only an offline contract check.
Neither package version nor a declared operation proves native API success.
"""

import os
import sys


def describe():
    """Return a fresh, bounded JSON manifest; never inspect a scene or license."""
    # Local imports avoid protocol/schema cycles. The package constant belongs
    # to the already imported package, not current disk or distribution metadata.
    from .. import __version__
    from ..tools.animation_schema import SCHEMAS, WRITE_METHODS
    from .protocol import MAX_BYTES, METHODS
    from . import compatibility

    return {
        'schema_version': 1,
        'protocol_version': 1,
        'write_contract': compatibility.describe(),
        'scope': 'Declared bridge contract; runtime preconditions are not evaluated.',
        'version_provenance': 'Version constant in this process\'s loaded cascadeur_mcp package.',
        'host': {
            'name': 'Cascadeur',
            'pid': os.getpid(),
            'python_version': sys.version.split()[0],
            'bridge_package_version': __version__,
            'application_version': None,
            'application_version_status': 'NOT_REPORTED',
        },
        'operations': {
            method: {
                'classification': 'write' if method in WRITE_METHODS else 'read',
                'requires_scene': method not in ('ping_cascadeur', 'get_bridge_capabilities'),
                'runtime_preconditions': 'NOT_EVALUATED',
            }
            for method in sorted(METHODS)
        },
        'read_features': {
            'get_recovery_status': {
                'read_only': True,
                'persistent_fence': 'explicit failed character rollback; survives host restart within this MCP instance',
                'checkpoint_verification': 'complete recorded model state, topology and captured track metadata; read does not clear fence',
                'not_covered': ['arbitrary unexpected mid-write crash', 'power loss', 'native manual editing', 'other MCP instances'],
            },
            'get_character_edit_readiness': {
                'advisory_only': True,
                'operations': list(SCHEMAS['get_character_edit_readiness']['properties']['operation']['enum']),
                'checks': 'saved identity, full semantic rig, stored frames, native tracks, recovery state and remaining capacity',
                'does_not_evaluate': ['new target feasibility', 'external playback', 'native write success'],
                'capacity_scope': 'session-wide snapshots and per-scene outstanding transactions; no reservations',
                'recheck': 'each actual write retains all native safety checks',
            },
            'get_semantic_pose': {
                'roles': list(SCHEMAS['get_semantic_pose']['properties']['roles']['items']['enum']),
                'roles_max': SCHEMAS['get_semantic_pose']['properties']['roles']['maxItems'],
                'include_joint_state': True,
                'default': 'all roles with read-only joint states',
                'rig_validation': 'complete profile, including unselected roles',
            },
            'get_semantic_pose_sequence': {
                'frames_max': SCHEMAS['get_semantic_pose_sequence']['properties']['frames']['maxItems'],
                'frame_order': 'request order; unique existing frames only',
                'selection': 'same roles and include_joint_state as get_semantic_pose',
                'rig_validation': 'complete profile once per synchronous request; no cross-request cache',
            },
        },
        'runtime_checks': {
            'scene': 'NOT_EVALUATED',
            'rig_compatibility': 'NOT_EVALUATED',
            'track_write_safety': 'NOT_EVALUATED',
            'export_entitlement': 'NOT_EVALUATED',
            'native_operation_success': 'NOT_EVALUATED',
        },
        'write_features': {
            'offset_semantic_pose_sequence_preserving_curves': {
                'frames_max': 8,
                'keys': 'existing keys on edited tracks; no added keys',
                'channels': 'selected native Point global positions only',
                'preserves': 'track/key metadata, interpolation, easing weights, supported tangent mode',
                'protects': 'unedited FIXED/baked tracks, external data, settings, Point keys outside requested frames',
                'solver_coupling': 'other rig Points can follow at edited frames; inspect actual adjustments',
                'edit_impact': {'schema_version': 1,
                                'grouping': 'semantic role and Point slot at requested frames',
                                'evidence': 'pre-edit targets and verified post-commit native Point targets',
                                'reporting_threshold': .001,
                                'scope': 'Point movement and target error; not Joint, trajectory or visual quality'},
                'rejects': 'CLAMPED_BEZIER anywhere, editing FIXED tracks, custom tangents, additive stacks, cycles, unavailable state',
                'trajectory_shape': 'edited trajectories may change',
                'runtime_preconditions': 'NOT_EVALUATED',
            },
        },
        'limits': {
            # protocol.py, client.py and host.py transport guards.
            'transport': {
                'message_bytes_max': MAX_BYTES,
                'request_deadline_seconds_max': 30,
                'client_timeout_seconds_max': 20,
                'requests_per_tick_max': 4,
                'requests_per_session_max': 10000,
            },
            'object_page_size_max': 200,
            'legacy_object_frame_index_max': SCHEMAS['set_current_frame']['properties']['frame']['maximum'],
            'pose_sequence_ordinary_frames_max': 8,
            'pose_sequence_sampled_frames_max': 64,
            'pose_sequence_frames_max': SCHEMAS['set_pose_sequence']['properties']['poses']['maxItems'],
            'semantic_read_sequence_frames_max': SCHEMAS['get_semantic_pose_sequence']['properties']['frames']['maxItems'],
            'semantic_offset_sequence_frames_max': SCHEMAS['offset_semantic_pose_sequence']['properties']['frames']['maxItems'],
            'curve_preserving_sequence_frames_max': SCHEMAS['offset_semantic_pose_sequence_preserving_curves']['properties']['frames']['maxItems'],
            'hand_sequence_frames_max': SCHEMAS['set_hand_pose_sequence']['properties']['poses']['maxItems'],
            'retime_keys_min': SCHEMAS['retime_character_motion']['properties']['keys']['minItems'],
            'retime_keys_max': SCHEMAS['retime_character_motion']['properties']['keys']['maxItems'],
            'character_frame_index_max': SCHEMAS['get_character_pose']['properties']['frame']['maximum'],
            # character.capture/identify, skeleton.guards/subtree/save_snapshot.
            'character_stored_frames_max': 121,
            'character_scene_objects_max': 1024,
            'character_joints_max': 128,
            'character_point_controls_max': 64,
            'character_snapshots_per_session_max': 16,
            'character_outstanding_transactions_max': 8,
            'character_restore_native_actions_max': 12,
            'joint_subtree_nodes_max': 32,
            'joint_hierarchy_scene_scan_objects_max': 10000,
            'joint_stored_frames_max': 121,
            'joint_snapshots': {'normal_slots': 31, 'restore_reserved_slots': 1},
            'durable_snapshot_bytes_max': 2 * 1024 * 1024,
        },
        'restrictions': {
            'clamped_recovery': 'Character Point and finger writes reject CLAMPED_BEZIER anywhere in the scene before snapshot/mutation. Checked native recovery failed local verification; this is a safety restriction, not an Undo repair. Reads remain available.',
            'runtime': 'Declared operations do not establish current scene, rig, license, or write readiness.',
            'scene_and_identity': 'Scene operations require an active scene. Character UUID tools require a saved scene; rediscover identity after saving a new native copy or regenerating a rig.',
            'frames': 'Frames must already exist. Sequence writes do not extend the timeline. Input frame-index bounds do not prove that a scene contains those frames.',
            'joint_writes': 'Named-object writes require unique names and isolated unlocked tracks. set_transform requires an existing key. Joint subtree writes require a pure topmost Joint tree, unit scale, two endpoint keys and linear FK sections (terminal STEP allowed).',
            'character_writes': 'set_character_pose requires every native Point control; semantic patches merge into that complete target set. Point writes require exclusive unlocked IK tracks and no AI interpolation. Semantic patches use validated cascy-points-v1 topology and native Point world positions; driven body Joint states are read-only.',
            'sampled_motion': 'Explicit sampled_motion=true accepts 1-64 increasing complete semantic Point poses with rigid limb-control geometry. Requires full stored visible timeline before snapshot/mutation. One native transaction; bounded summary hashes; read actual frames with get_semantic_pose_sequence. Ordinary default stays 1-8. No timeline extension.',
            'relative_edits': 'offset_semantic_pose_sequence translates every Point slot of each selected role in world scene units from each frame\'s current state. Final absolute targets are validated before a single checked transaction. Repeating a call accumulates the delta; no automatic retry is permitted.',
            'hand_writes': 'Finger local unit quaternions require validated Cascy names, parent chains, animated rotation data and unlocked finger-only tracks. Hand Point targets do not curl fingers.',
            'retiming': 'All character tracks must have exactly the supplied synchronized keys; endpoints stay fixed. Supported requested interpolation: LINEAR, BEZIER, LOW_AMPLITUDE_BEZIER. Optional contact stabilization requires the supported stationary left-foot/right-toe profile.',
            'snapshots': 'Session snapshots expire on restart and require original scene/history guards. Durable JSON restores one pose and can recompute adjacent interpolation; it is not a whole-scene backup.',
            'playback': 'Edits require no bridge-owned active playback. Native play/stop is bounded and owned by this bridge; external playback cannot be stopped by this tool. Absence of owned playback does not establish external playback state.',
            'file_output': 'Output paths must be absolute, bounded, outside the private runtime and free of links/reparse points. Parent directories must exist. Native scene copies and durable snapshot saves require new destinations.',
            'export': 'FBX requires native export entitlement, one supported character with no unrelated joints/meshes and the full stored frame range. It saves a new native scene copy first; replacing FBX requires matching SHA-256. Entitlement and loader presence do not prove successful export.',
            'timeouts': 'A write timeout has an unknown outcome. Read back before retrying.',
            'not_provided': ['arbitrary Python or shell execution', 'generic menu actions',
                             'AutoPhysics or AutoPosing automation', 'arbitrary rig support',
                             'headless Cascadeur', 'bundled Unity or game pipeline'],
        },
    }
