# Selective semantic pose reads

The selection options introduced in `0.5.0a4` and included in `0.5.0a6`
extend the existing `get_semantic_pose` tool;
it does not add an animation generator or a new write operation.

## Arguments

Discover `character_id` using `list_characters`, then send the normal tool
arguments with optional selection fields:

```json
{
  "character_id": "<discovered character UUID>",
  "frame": 10,
  "roles": ["right_hand"],
  "include_joint_state": false
}
```

Replace the placeholder with the current character UUID. `frame` must be an
existing frame of the bounded character clip.

- `roles` must contain 1–11 unique semantic names. Omitting it reads all roles.
  The vocabulary is pelvis, chest, head, left_hand, right_hand, left_elbow,
  right_elbow, left_foot, right_foot, left_knee and right_knee.
- `include_joint_state` is a strict boolean, defaulting to `true`. `false`
  omits the `joint_state` field and skips Joint Transform value reads.
- Role output follows the profile's canonical order, not the request order.
  Each selected role includes all its Point target slots. There is no slot
  selection or precision rounding.

The response retains scene/character identity, frame, profile, the complete-rig
fingerprint, `joint_state_writable: false` and transport correlation fields.
Positions keep their original native world-space values. Palm `direction` and
`orientation` are Point positions, not Euler angles or finger articulation.

## Compatibility and safety

With both options omitted, the response keys and values remain compatible with
the previous full semantic read. All native rig names, hierarchy, bindings and
Point membership are still validated, including roles that were not requested.
An unsupported rig does not become supported by asking for one hand.

Check `get_bridge_capabilities().read_features.get_semantic_pose` on the live
host. MCP `tools/list` describes the external server's schema; it cannot prove
that an older host supports the options. Save and close Cascadeur before
upgrading, then restart both the host and the MCP server. An older host may
explicitly reject the new fields. Never silently treat a failed selection as a
successful full or empty result.

This is a backwards-compatible read extension. The write contract, transaction
capture, post-commit checks, rollback and snapshot bounds are unchanged. A
matching write contract alone does not certify read-option compatibility.
`set_pose_sequence` still returns its complete solved semantic poses and
transaction/snapshot evidence; these read options are not accepted by writes.

## Choose the scope deliberately

Use a targeted read to inspect a known control or verify a small local change.
Use full reads and real playback when assessing whole-body motion, support,
contact, constraints or animation quality. A right-hand-only result does not
establish that the rest of the character stayed correct.

A successful sequence write already returns solved poses. An immediate repeat
read of the same data is often unnecessary. After a timeout or other unknown
write outcome, independent readback is still required before deciding whether
to retry. No automated write retry is introduced.

Response bytes and adapter Transform read counts can be measured directly.
They are not Token counts, task speed guarantees or animation-quality scores.
Validation remains limited to the developer's local machine.
