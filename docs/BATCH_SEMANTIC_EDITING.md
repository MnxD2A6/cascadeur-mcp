# Batch semantic reads and relative editing

The batch features introduced in `0.5.0a5` and included in `0.5.0a6`
add two bounded tools to the existing Cascy
semantic workflow. It does not generate motions or improve animation quality.

## Read several frames once

Discover the current `character_id` with `list_characters`, then call:

```json
{
  "character_id": "<discovered character UUID>",
  "frames": [0, 3, 5, 8, 10, 13, 17, 22],
  "roles": ["right_hand"],
  "include_joint_state": false
}
```

Use `get_semantic_pose_sequence` for these arguments. `frames` contains 1–8
unique existing indices, each 0–120. Results follow requested frame order;
role order remains canonical. Omitting the selection options returns all eleven
roles with read-only joint states, just like `get_semantic_pose`.

The full hierarchy, bindings and Point membership are validated once inside the
synchronous native request. Each frame still reads actual native data and checks
character membership. There is no cross-request cache, playhead movement or
resampling. A partial read does not establish whole-body motion quality.

## Translate named control groups once

Use `offset_semantic_pose_sequence` with the discovered saved scene identity:

```json
{
  "scene_id": "<discovered saved scene ID>",
  "character_id": "<discovered character UUID>",
  "frames": [0, 3, 5, 8, 10, 13, 17, 22],
  "offsets": {"right_hand": [-0.05, 0, 0]}
}
```

The delta uses native **world scene units**, not meters or local coordinates.
Every Point slot of a role receives the same translation, including its
direction and orientation targets. Each frame starts from its own current
stored pose. Multiple named roles can share one request; offsets can differ by
role. This moves palm controls; it does not curl fingers, rotate the body,
extend the timeline or change IK/FK mode.

**This is a key-pose authoring operation.** It reuses `set_pose_sequence`, which
inserts complete character keys at the supplied frames and sets character
intervals to LINEAR (terminal STEP remains). It does not preserve authored
easing curves. Unselected controls retain their input targets at the requested
frames; interpolation and rig solving can still affect other values. Preserve
the native scene before editing a polished clip, and inspect full playback.

All frames and all computed absolute Point targets are checked before mutation,
including unedited targets. A failure here reports `not_started`. The operation
then enters the existing full-scene snapshot and checked native transaction
once. Capture, geometry, topology, track, static constraint, post-commit and
rollback checks are unchanged. A failure inside the transaction retains its
verified `rolled_back` or `recovery_required` evidence.

Success returns `snapshot_id`, transaction and solver evidence, and the actual
solved Point poses of the edited roles. The smaller response is projected only
after full internal verification. Requested offsets are not a guarantee of exact
IK displacement. Use `restore_pose_snapshot` with `scene_id` and that
`snapshot_id` to undo; the existing session/history limits still apply.

**Do not automatically retry.** This tool is not idempotent: a repeated call
adds the delta again. After timeout or unknown outcome, read the current state
before any retry. It has no arbitrary expression, script, rotation or scale
escape hatch.

## Compatibility and evidence

Restart both Cascadeur host and external MCP server with matching source.
The added write schema changes the bilateral write-contract hash; mismatched
peers refuse writes. Check the actual loaded host's `operations` and
`read_features`, rather than trusting the external tool list alone.

Efficiency comparisons should report the measured task: eight single-frame
reads versus one batch read, or eight reads plus one absolute sequence write
versus one relative sequence write. Include exact native data equivalence and
verified restoration. SDK timings and UTF-8 byte counts are not LLM Token
measurements, visual-quality scores or cross-machine guarantees.
