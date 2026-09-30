"""Selective-read regressions; these do not replace native host acceptance."""

import copy

import pytest

from cascadeur_mcp.bridge import semantics
from cascadeur_mcp.bridge.protocol import BridgeError, validate_params
from cascadeur_mcp.tools.semantic_schema import SCHEMAS, SLOTS


CID = "7db06f9b-ac9f-4086-8ebb-e62608f5bad9"
READ = {"character_id": CID, "frame": 10}


def full_result():
    """Explicit synthetic data for projection tests only, never native evidence."""
    return {
        "scene_id": "a" * 32,
        "character_id": CID,
        "frame": 10,
        "profile": "cascy-points-v1",
        "fingerprint": "b" * 64,
        "pose": {
            role: {slot: [index, index + 1, index + 2] for slot in slots}
            for index, (role, slots) in enumerate(SLOTS.items())
        },
        "joint_state": {
            role: {"global": {"position": [index, 0, 0]}, "name": role}
            for index, role in enumerate(SLOTS)
        },
        "joint_state_writable": False,
    }


def test_default_read_params_preserve_legacy_call():
    assert validate_params("get_semantic_pose", READ) == READ


@pytest.mark.parametrize("roles", [["right_hand"], list(SLOTS), ["right_hand", "pelvis"]])
@pytest.mark.parametrize("include_joint_state", [True, False])
def test_valid_selection_params(roles, include_joint_state):
    params = {**READ, "roles": roles, "include_joint_state": include_joint_state}
    assert validate_params("get_semantic_pose", params) == params


@pytest.mark.parametrize("roles", [
    [],
    ["right_hand", "right_hand"],
    ["right_hand"] * 12,
    ["arm_r"],
    [" right_hand"],
    ["RIGHT_HAND"],
    [""],
    [None],
    [True],
    [1],
    [["right_hand"]],
    [{"role": "right_hand"}],
    None,
    "right_hand",
    ("right_hand",),
    {"right_hand"},
    {"right_hand": True},
    1,
    False,
])
def test_roles_reject_invalid_external_input(roles):
    with pytest.raises(BridgeError, match="INVALID_PARAMS"):
        validate_params("get_semantic_pose", {**READ, "roles": roles})


@pytest.mark.parametrize("include_joint_state", [None, 0, 1, "true", "false", [], {}])
def test_joint_state_flag_requires_actual_bool(include_joint_state):
    with pytest.raises(BridgeError, match="INVALID_PARAMS"):
        validate_params("get_semantic_pose", {**READ, "include_joint_state": include_joint_state})


def test_selection_schema_has_bounded_vocabulary_and_legacy_defaults():
    spec = SCHEMAS["get_semantic_pose"]
    assert set(spec["required"]) == {"character_id", "frame"}
    assert spec["additionalProperties"] is False
    roles = spec["properties"]["roles"]
    assert roles["type"] == "array"
    assert roles["minItems"] == 1 and roles["maxItems"] == len(SLOTS) == 11
    assert roles["uniqueItems"] is True
    assert roles["items"]["type"] == "string"
    assert set(roles["items"]["enum"]) == set(SLOTS)
    flag = spec["properties"]["include_joint_state"]
    assert flag["type"] == "boolean" and flag["default"] is True


def test_selection_fields_are_not_accepted_by_write_tools():
    write = {"scene_id": "a" * 32, **READ, "pose": {"right_hand": {"center": [1, 2, 3]}}}
    for extra in ({"roles": ["right_hand"]}, {"include_joint_state": False}):
        with pytest.raises(BridgeError, match="INVALID_PARAMS"):
            validate_params("set_semantic_pose", {**write, **extra})


def test_default_projection_is_identical_and_does_not_mutate_input():
    original = full_result()
    before = copy.deepcopy(original)
    selected = semantics.select_pose(original)
    assert selected == before
    assert selected is not original
    assert original == before


def test_projection_preserves_identity_safety_and_selected_numbers():
    original = full_result()
    before = copy.deepcopy(original)
    selected = semantics.select_pose(original, roles=["right_hand", "pelvis"])
    assert list(selected["pose"]) == ["pelvis", "right_hand"]
    assert list(selected["joint_state"]) == ["pelvis", "right_hand"]
    for role in selected["pose"]:
        assert selected["pose"][role] == before["pose"][role]
        assert selected["joint_state"][role] == before["joint_state"][role]
    for key in ("scene_id", "character_id", "frame", "profile", "fingerprint", "joint_state_writable"):
        assert selected[key] == before[key]
    assert selected["joint_state_writable"] is False
    assert original == before


@pytest.mark.parametrize("roles", [None, ["right_hand"], list(SLOTS)])
def test_projection_omits_joint_state_when_disabled(roles):
    original = full_result()
    before = copy.deepcopy(original)
    selected = semantics.select_pose(original, roles=roles, include_joint_state=False)
    assert "joint_state" not in selected
    assert selected["joint_state_writable"] is False
    expected_roles = list(SLOTS) if roles is None else [role for role in SLOTS if role in roles]
    assert list(selected["pose"]) == expected_roles
    assert original == before


def test_get_pose_filters_native_reads_after_full_rig_validation(monkeypatch):
    from semantic_fixture import synthetic_skeleton

    skeleton = synthetic_skeleton()
    rig = semantics.build_map(skeleton)
    native_calls = []

    def native_pose(view, scene, cid, frame, *, joint_ids=None, control_ids=None):
        native_calls.append((view, scene, cid, frame, joint_ids, control_ids))
        return {
            "scene_id": rig["scene_id"],
            "pose": {control_id: {"position": [1, 2, 3]} for control_id in control_ids},
            "joints": {joint_id: {"position": [4, 5, 6]} for joint_id in joint_ids},
        }

    monkeypatch.setattr(semantics.character, "get_pose", native_pose)
    view, scene = object(), object()
    selected = semantics.get_pose(view, scene, CID, 10, rig,
                                  roles=["right_hand"], include_joint_state=False)
    assert len(native_calls) == 1
    _, _, actual_cid, actual_frame, joint_ids, control_ids = native_calls[0]
    assert (actual_cid, actual_frame) == (CID, 10)
    assert set(joint_ids) == set()
    assert set(control_ids) == {control["control_id"] for control in rig["roles"]["right_hand"]["controls"].values()}
    assert list(selected["pose"]) == ["right_hand"]
    assert "joint_state" not in selected
    assert selected["fingerprint"] == rig["fingerprint"]
    assert selected["joint_state_writable"] is False


def test_dispatch_forwards_selection_but_keeps_mapping_validation(monkeypatch):
    rig = {"profile": "synthetic-unit-test-only"}
    mapping_calls, pose_calls = [], []

    def mapping(view, scene, cid):
        mapping_calls.append((view, scene, cid))
        return rig

    def get_pose(view, scene, cid, frame, rig_arg=None, roles=None, include_joint_state=True):
        pose_calls.append((cid, frame, rig_arg, roles, include_joint_state))
        return {"unit_test_only": True}

    monkeypatch.setattr(semantics, "mapping", mapping)
    monkeypatch.setattr(semantics, "get_pose", get_pose)
    view, scene = object(), object()
    result = semantics.dispatch(view, scene, "get_semantic_pose",
                                {**READ, "roles": ["right_hand"], "include_joint_state": False})
    assert result == {"unit_test_only": True}
    assert mapping_calls == [(view, scene, CID)]
    assert pose_calls == [(CID, 10, rig, ["right_hand"], False)]
