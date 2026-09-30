"""Bounded semantic batch regressions; synthetic data is not host acceptance.

These tests check the public validation boundary and transaction delegation.
Real Cascadeur MCP measurements remain a separate acceptance requirement.
"""

import copy
from types import SimpleNamespace

import pytest

from cascadeur_mcp.bridge import semantics
from cascadeur_mcp.bridge.protocol import BridgeError, validate_params
from cascadeur_mcp.tools import animation_schema, semantic_schema


CID = "7db06f9b-ac9f-4086-8ebb-e62608f5bad9"
SCENE = "a" * 32
READ = {"character_id": CID, "frames": [0, 5, 10]}
OFFSET = {"scene_id": SCENE, **READ, "offsets": {"right_hand": [0.25, 0.0, -0.1]}}


@pytest.mark.parametrize('method,params', [
    ('offset_semantic_pose_sequence', {**OFFSET, 'offsets': {'right_hand': [10**400, 0, 0]}}),
    ('set_semantic_pose', {'scene_id': SCENE, 'character_id': CID, 'frame': 0,
                         'pose': {'right_hand': {'center': [10**400, 0, 0]}}}),
    ('set_character_pose', {'scene_id': SCENE, 'character_id': CID, 'frame': 0,
                          'pose': {CID: {'position': [10**400, 0, 0]}}}),
])
def test_huge_integer_targets_are_invalid_input(method, params):
    with pytest.raises(BridgeError, match='INVALID_PARAMS'):
        validate_params(method, params)


@pytest.mark.parametrize("method,params", [
    ("get_semantic_pose_sequence", READ),
    ("offset_semantic_pose_sequence", OFFSET),
])
def test_sequence_tools_accept_minimal_bounded_inputs(method, params):
    before = copy.deepcopy(params)
    assert validate_params(method, params) == params
    assert params == before


@pytest.mark.parametrize("frames", [
    [], [0, 0], list(range(9)), [False], [True], [0.0], [-1], [121],
    [float("nan")], [float("inf")], ["10"], [None], None, "0,5,10", (0, 5),
])
@pytest.mark.parametrize("method,params", [
    ("get_semantic_pose_sequence", READ),
    ("offset_semantic_pose_sequence", OFFSET),
])
def test_sequence_tools_reject_invalid_frame_lists(method, params, frames):
    with pytest.raises(BridgeError, match="INVALID_PARAMS"):
        validate_params(method, {**params, "frames": frames})


@pytest.mark.parametrize("extra", [
    {"roles": []}, {"roles": ["right_hand", "right_hand"]},
    {"roles": ["arm_r"]}, {"roles": [True]}, {"roles": "right_hand"},
    {"include_joint_state": 0}, {"include_joint_state": "false"},
    {"frame": 10}, {"code": "arbitrary code"}, {"character_id": "Cascy"},
])
def test_sequence_read_reuses_strict_selection_validation(extra):
    with pytest.raises(BridgeError, match="INVALID_PARAMS"):
        validate_params("get_semantic_pose_sequence", {**READ, **extra})


def test_sequence_read_accepts_projection_without_changing_frame_order():
    params = {**READ, "frames": [10, 0, 5], "roles": ["right_hand", "pelvis"],
              "include_joint_state": False}
    assert validate_params("get_semantic_pose_sequence", params) == params


@pytest.mark.parametrize("method,params", [
    ("get_semantic_pose_sequence", READ),
    ("offset_semantic_pose_sequence", OFFSET),
])
def test_sequence_validation_accepts_eight_unique_frames_and_boundary_values(method, params):
    bounded = {**params, "frames": [120, 0, 1, 2, 3, 4, 5, 6]}
    if method == "offset_semantic_pose_sequence":
        bounded["offsets"] = {"right_hand": [-10000, 10000, 0]}
    assert validate_params(method, bounded) == bounded


@pytest.mark.parametrize("method,params", [
    ("get_semantic_pose_sequence", READ),
    ("offset_semantic_pose_sequence", OFFSET),
])
def test_sequence_tools_reject_missing_required_identity_and_frame_fields(method, params):
    for required in params:
        missing = {key: value for key, value in params.items() if key != required}
        with pytest.raises(BridgeError, match="INVALID_PARAMS"):
            validate_params(method, missing)


@pytest.mark.parametrize("offsets", [
    {}, None, [], {"arm_r": [0, 0, 0]}, {"RIGHT_HAND": [0, 0, 0]},
    {"right_hand": {"center": [0, 0, 0]}}, {"right_hand": [True, 0, 0]},
    {"right_hand": [0, float("nan"), 0]}, {"right_hand": [0, float("inf"), 0]},
    {"right_hand": [10001, 0, 0]}, {"right_hand": [0, 0]},
    {"right_hand": (0, 0, 0)}, {"right_hand": [0, 0, 0, 0]},
])
def test_offset_rejects_unsupported_roles_or_nonfinite_vectors(offsets):
    with pytest.raises(BridgeError, match="INVALID_PARAMS"):
        validate_params("offset_semantic_pose_sequence", {**OFFSET, "offsets": offsets})


@pytest.mark.parametrize("extra", [
    {"rotation": [1, 0, 0, 0]}, {"scale": [1, 1, 1]},
    {"roles": ["right_hand"]}, {"include_joint_state": False},
    {"pose": {"right_hand": {"center": [0, 0, 0]}}}, {"scene_id": "../scene"},
])
def test_offset_has_no_rotation_scaling_or_arbitrary_pose_escape(extra):
    with pytest.raises(BridgeError, match="INVALID_PARAMS"):
        validate_params("offset_semantic_pose_sequence", {**OFFSET, **extra})


def test_batch_write_is_in_compatibility_guard_and_schemas_are_closed():
    assert "offset_semantic_pose_sequence" in animation_schema.WRITE_METHODS
    assert "get_semantic_pose_sequence" not in animation_schema.WRITE_METHODS
    read = semantic_schema.SCHEMAS["get_semantic_pose_sequence"]
    write = semantic_schema.SCHEMAS["offset_semantic_pose_sequence"]
    assert read["additionalProperties"] is False
    assert write["additionalProperties"] is False
    assert set(read["required"]) == {"character_id", "frames"}
    assert set(write["required"]) == {"scene_id", "character_id", "frames", "offsets"}
    for spec in (read, write):
        frames = spec["properties"]["frames"]
        assert frames["type"] == "array"
        assert (frames["minItems"], frames["maxItems"], frames["uniqueItems"]) == (1, 8, True)
        assert frames["items"]["minimum"] == 0
        assert frames["items"]["maximum"] == 120


@pytest.fixture
def adapter(monkeypatch):
    """Hand-authored topology plus synthetic frame-specific Point targets."""
    from semantic_fixture import synthetic_skeleton

    rig = semantics.build_map(synthetic_skeleton())
    ids = [item["control_id"] for role in rig["roles"].values()
           for item in role["controls"].values()]
    joint_ids = [role["joint_state"]["joint_id"] for role in rig["roles"].values()]
    state = {
        frame: {oid: {"position": [float(frame + i), float(i + 1), float(frame - i)]}
                for i, oid in enumerate(ids)}
        for frame in range(23)
    }
    native_calls, transactions, mapping_calls = [], [], []
    size = SimpleNamespace(get_animation_size=lambda: 23)
    scene = SimpleNamespace(data_viewer=lambda: size,
                            model_viewer=lambda: SimpleNamespace(data_viewer=lambda: size))
    view = object()

    def mapping(actual_view, actual_scene, cid):
        mapping_calls.append((actual_view, actual_scene, cid))
        return rig

    def get_pose(actual_view, actual_scene, cid, frame, *, joint_ids=None, control_ids=None):
        native_calls.append({"frame": frame, "joint_ids": joint_ids,
                             "control_ids": control_ids, "after_write": bool(transactions)})
        if frame not in state:
            raise BridgeError("FRAME_OUT_OF_RANGE: synthetic frame is not stored")
        controls = set(ids) if control_ids is None else set(control_ids)
        joints = set(adapter_joint_ids) if joint_ids is None else set(joint_ids)
        return {"scene_id": rig["scene_id"], "character_id": cid, "frame": frame,
                "pose": {oid: copy.deepcopy(state[frame][oid]) for oid in controls},
                "joints": {oid: {"global": {"position": [frame, 0, 0]}} for oid in joints}}

    adapter_joint_ids = joint_ids

    def set_sequence(actual_view, actual_scene, cid, entries):
        assert actual_view is view and actual_scene is scene and cid == rig["character_id"]
        transactions.append(copy.deepcopy(entries))
        for entry in entries:
            state[entry["frame"]] = copy.deepcopy(entry["pose"])
        return {"scene_id": rig["scene_id"], "character_id": cid,
                "native_poses": [get_pose(view, scene, cid, e["frame"]) for e in entries],
                "snapshot_id": "c" * 32, "frames_written": [e["frame"] for e in entries],
                "transaction_count": 1, "mcp_calls_for_sequence_write": 1,
                "max_target_adjustment": 0.0}

    monkeypatch.setattr(semantics, "mapping", mapping)
    monkeypatch.setattr(semantics.character, "scene_id", lambda actual_view: rig["scene_id"])
    monkeypatch.setattr(semantics.character, "get_pose", get_pose)
    monkeypatch.setattr(semantics.character, "set_sequence", set_sequence)
    return SimpleNamespace(rig=rig, state=state, view=view, scene=scene,
                           native_calls=native_calls, transactions=transactions,
                           mapping_calls=mapping_calls, control_ids=set(ids))


def dispatch(adapter, method, **params):
    return semantics.dispatch(adapter.view, adapter.scene, method,
                              {"character_id": adapter.rig["character_id"], **params})


def test_sequence_read_returns_actual_frame_values_in_request_order(adapter):
    before = copy.deepcopy(adapter.state)
    result = dispatch(adapter, "get_semantic_pose_sequence", frames=[10, 0, 5],
                      roles=["right_hand"], include_joint_state=False)
    assert [pose["frame"] for pose in result["poses"]] == [10, 0, 5]
    assert len(adapter.mapping_calls) == 1
    hand_ids = {item["control_id"] for item in adapter.rig["roles"]["right_hand"]["controls"].values()}
    assert len(adapter.native_calls) == 3
    for call, pose in zip(adapter.native_calls, result["poses"]):
        assert call["joint_ids"] == set()
        assert set(call["control_ids"]) == hand_ids
        assert list(pose["pose"]) == ["right_hand"]
        assert "joint_state" not in pose
        assert pose["joint_state_writable"] is False
        for slot, control in adapter.rig["roles"]["right_hand"]["controls"].items():
            assert pose["pose"]["right_hand"][slot] == before[pose["frame"]][control["control_id"]]["position"]
    for key in ("scene_id", "character_id", "profile", "fingerprint"):
        assert result[key] == adapter.rig[key]
    assert adapter.transactions == []
    assert adapter.state == before


def test_sequence_read_defaults_keep_all_roles_and_readonly_joint_states(adapter):
    result = dispatch(adapter, "get_semantic_pose_sequence", frames=[0])
    assert set(result["poses"][0]["pose"]) == set(semantic_schema.SLOTS)
    assert set(result["poses"][0]["joint_state"]) == set(semantic_schema.SLOTS)
    assert result["poses"][0]["joint_state_writable"] is False
    assert adapter.transactions == []


def test_offset_moves_every_selected_slot_from_each_frames_own_baseline(adapter):
    before = copy.deepcopy(adapter.state)
    offsets = {"right_hand": [0.25, -0.1, 0.2], "pelvis": [-0.2, 0.0, 0.1]}
    original_offsets = copy.deepcopy(offsets)
    result = dispatch(adapter, "offset_semantic_pose_sequence", scene_id=SCENE,
                      frames=[10, 0, 5], offsets=offsets)
    assert offsets == original_offsets
    assert len(adapter.mapping_calls) == 1
    assert len(adapter.transactions) == 1
    entries = adapter.transactions[0]
    assert [entry["frame"] for entry in entries] == [10, 0, 5]
    selected_ids = {control["control_id"]: offsets[role]
                    for role in offsets for control in adapter.rig["roles"][role]["controls"].values()}
    for entry in entries:
        assert set(entry["pose"]) == adapter.control_ids
        for oid, point in entry["pose"].items():
            delta = selected_ids.get(oid, [0, 0, 0])
            expected = [n + d for n, d in zip(before[entry["frame"]][oid]["position"], delta)]
            assert point["position"] == pytest.approx(expected)
    before_calls = [call for call in adapter.native_calls if not call["after_write"]]
    assert [call["frame"] for call in before_calls] == [10, 0, 5]
    assert all(call["joint_ids"] == set() and call["control_ids"] is None for call in before_calls)
    assert result["transaction_count"] == 1
    assert result["mcp_calls_for_sequence_write"] == 1
    assert result["snapshot_id"] == "c" * 32
    assert result["offsets"] == offsets
    assert result["coordinate_space"] == "world positions in native scene units"
    assert "native_poses" not in result
    for pose in result["poses"]:
        assert set(pose["pose"]) == set(offsets)
        assert "joint_state" not in pose
        assert pose["joint_state_writable"] is False


def test_offset_response_reports_solver_adjusted_state_not_requested_targets(adapter, monkeypatch):
    oid = adapter.rig["roles"]["right_hand"]["controls"]["center"]["control_id"]
    original_x = adapter.state[5][oid]["position"][0]
    native_set = semantics.character.set_sequence

    def solve(view, scene, cid, entries):
        adjusted = copy.deepcopy(entries)
        adjusted[0]["pose"][oid]["position"][0] += 0.04
        result = native_set(view, scene, cid, adjusted)
        result["max_target_adjustment"] = 0.04
        return result

    monkeypatch.setattr(semantics.character, "set_sequence", solve)
    result = dispatch(adapter, "offset_semantic_pose_sequence", scene_id=SCENE,
                      frames=[5], offsets={"right_hand": [0.2, 0, 0]})
    center = result["poses"][0]["pose"]["right_hand"]["center"]
    assert center == adapter.state[5][oid]["position"]
    assert center[0] == pytest.approx(original_x + 0.2 + 0.04)
    assert result["max_target_adjustment"] == 0.04


@pytest.mark.parametrize("method", ["get_semantic_pose_sequence", "offset_semantic_pose_sequence"])
def test_frame_absent_from_stored_clip_rejects_before_transaction(adapter, method):
    before = copy.deepcopy(adapter.state)
    params = {"frames": [0, 23]}
    if method == "offset_semantic_pose_sequence":
        params.update(scene_id=SCENE, offsets={"right_hand": [0.1, 0, 0]})
    with pytest.raises(BridgeError, match="FRAME_OUT_OF_RANGE") as caught:
        dispatch(adapter, method, **params)
    if method == "offset_semantic_pose_sequence":
        assert caught.value.execution_state == "not_started"
    assert adapter.transactions == []
    assert adapter.state == before


@pytest.mark.parametrize("initial", [9999.9, float("nan"), float("inf")])
def test_offset_validates_computed_targets_before_any_transaction(adapter, initial):
    oid = adapter.rig["roles"]["right_hand"]["controls"]["center"]["control_id"]
    adapter.state[10][oid]["position"][0] = initial
    before_frame_zero = copy.deepcopy(adapter.state[0])
    with pytest.raises(BridgeError) as caught:
        dispatch(adapter, "offset_semantic_pose_sequence", scene_id=SCENE,
                 frames=[0, 10], offsets={"right_hand": [0.2, 0, 0]})
    assert caught.value.execution_state == "not_started"
    assert adapter.transactions == []
    assert adapter.state[0] == before_frame_zero


def test_offset_validates_complete_final_point_set_including_unedited_roles(adapter):
    oid = adapter.rig["roles"]["left_foot"]["controls"]["heel"]["control_id"]
    adapter.state[5][oid]["position"][0] = 10001.0
    before = copy.deepcopy(adapter.state)
    with pytest.raises(BridgeError) as caught:
        dispatch(adapter, "offset_semantic_pose_sequence", scene_id=SCENE,
                 frames=[0, 5], offsets={"right_hand": [0.2, 0, 0]})
    assert caught.value.execution_state == "not_started"
    assert adapter.transactions == []
    assert adapter.state == before


def test_scene_mismatch_rejects_before_mapping_or_transaction(adapter):
    with pytest.raises(BridgeError, match="SCENE_MISMATCH"):
        dispatch(adapter, "offset_semantic_pose_sequence", scene_id="b" * 32,
                 frames=[0], offsets={"right_hand": [0.2, 0, 0]})
    assert adapter.mapping_calls == []
    assert adapter.native_calls == []
    assert adapter.transactions == []


@pytest.mark.parametrize("failure", [
    BridgeError("NONFINITE_HOST_DATA: synthetic data not finite"),
    RuntimeError("synthetic native read failed"),
])
def test_native_baseline_read_failure_has_preflight_evidence(adapter, monkeypatch, failure):
    before = copy.deepcopy(adapter.state)

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(semantics.character, "get_pose", fail)
    with pytest.raises(BridgeError) as caught:
        dispatch(adapter, "offset_semantic_pose_sequence", scene_id=SCENE,
                 frames=[0, 5], offsets={"right_hand": [0.2, 0, 0]})
    expected_code = "NONFINITE_HOST_DATA" if isinstance(failure, BridgeError) else "PREFLIGHT_FAILED"
    assert str(caught.value).startswith(expected_code + ":")
    assert caught.value.execution_state == "not_started"
    assert adapter.transactions == []
    assert adapter.state == before


@pytest.mark.parametrize("state,verified", [("rolled_back", True), ("recovery_required", False)])
def test_offset_does_not_downgrade_transaction_failure_evidence(adapter, monkeypatch, state, verified):
    original = BridgeError("CHARACTER_POSE_FAILED: synthetic transaction failed",
                           execution_state=state, rollback_verified=verified,
                           recovery_snapshot_id="d" * 32)

    def fail(*args, **kwargs):
        raise original

    monkeypatch.setattr(semantics.character, "set_sequence", fail)
    with pytest.raises(BridgeError) as caught:
        dispatch(adapter, "offset_semantic_pose_sequence", scene_id=SCENE,
                 frames=[0, 5], offsets={"right_hand": [0.2, 0, 0]})
    assert caught.value is original
    assert caught.value.execution_state == state
    assert caught.value.rollback_verified is verified
    assert caught.value.recovery_snapshot_id == "d" * 32
