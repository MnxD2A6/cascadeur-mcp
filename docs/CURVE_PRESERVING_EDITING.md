# Editing existing keys while preserving curve metadata

`offset_semantic_pose_sequence_preserving_curves` offsets every Point slot of
each selected semantic role at 1–8 existing keys in one MCP call / checked native
transaction. World positions use native scene units, as in the ordinary offset
tool. Discover scene/character identities and semantic mapping first.

```json
{
  "scene_id": "<discovered scene id>",
  "character_id": "<discovered character UUID>",
  "frames": [6, 10, 13],
  "offsets": {"right_hand": [-0.05, 0.0, 0.0]}
}
```

The placeholders above must be replaced with actual discovered identities.
Each frame uses its own current targets. Repeating the call accumulates the
offset; it is not idempotent. Never retry a timeout blindly: read back first.

## Which edit to choose

| Tool | Intended use | Key/interval behavior |
|---|---|---|
| `set_pose_sequence` / ordinary `offset_semantic_pose_sequence` | Author initial key poses | Creates full-character keys and uses LINEAR intervals |
| `offset_semantic_pose_sequence_preserving_curves` | Small corrections to an already authored clip | Existing edited-track keys only; no layer/key authoring |

The ordinary writer changes interpolation type; it does not explicitly erase
all easing weights. LINEAR can also use easing. The preserving writer checks
complete track layout and serialized curve metadata exactly, including easing
weights, tangent mode, IK/FK, fixation, labels and AI description strings.

Only selected Point global-position channels are written. Driven local
transforms, velocity caches and Joints can legitimately recompute. Moving a key
changes its trajectory and adjacent interpolation; this is metadata preservation,
not a promise that the original path shape stays identical.

## Safety and limits

- The verified Cascy semantic profile and saved-scene identity are required.
- Frames must already be keys on every edited track. Other tracks need not
  share those keys. No timeline extension or automatic key creation.
- Classic IK tracks only. STEP endpoints are retained. Editing FIXED/baked
  tracks or NONE/AI interpolation is refused.
- Since `0.5.0a8`, CLAMPED_BEZIER anywhere in the scene is refused before
  character Point or finger editing. A real Cascy fixture passed its offset
  write but failed checked snapshot recovery; the bridge locked further writes.
  This safeguard does not fix that unresolved native recovery failure. Retiming
  also rejects CLAMPED_BEZIER input. Read-only inspection remains available.
- Unedited FIXED tracks retain their data over the complete stored clip.
  All external animated data and all animated settings are protected. Authored
  Point targets at keys outside the requested frames are checked separately
  from solver-derived data. At requested frames, other Points in the same rig
  can follow through solver coupling, even though their channels were not
  directly written. Inspect the returned solver adjustments and actual poses.
- Any additive stack, cycle or custom spatial tangent in the scene is refused;
  their complete recovery state is not available to this bridge. A missing or
  unreadable required API is a rejection, never assumed to mean “none”.
- Full-scene snapshot, whole-clip connection checks, verification after native
  commit and checked native Undo are mandatory. Extra metadata is rechecked
  before reporting a verified rollback. Unverified recovery locks further writes.
- Existing snapshot/history limits and numeric tolerances are unchanged.
- Update and restart both host and MCP server together. The new write schema
  changes the compatibility fingerprint. No hot reload or silent fallback.

`CURVE_KEY_REQUIRED`, `UNSUPPORTED_EDIT_TRACK`, `UNSUPPORTED_CUSTOM_TANGENTS`,
`UNSUPPORTED_ADDITIVE_LAYERS`, `UNSUPPORTED_CYCLES`, `UNSUPPORTED_CLAMPED_RECOVERY` and
`CURVE_STATE_UNAVAILABLE` identify preflight failures. Transaction failures
retain explicit `execution_state`, `rollback_verified` and recovery snapshot.

## Additional local curve evidence

On Cascadeur 2026.2.2, real BEZIER and LOW_AMPLITUDE_BEZIER fixtures with
two unedited FIXED foot tracks each passed a three-frame semantic offset,
exact track/curve metadata checks, 23-frame readback and checked restoration
of all 66 Joints and 43 Points. The tested synchronized key layout was
`0, 6, 8, 10, 11, 13, 16, 22`. Native readback kept STEP at the adjacent
10→11 interval and the terminal endpoint. This observation is specific to
these fixtures, not a promise about every Cascadeur clip.

CLAMPED_BEZIER was tested and failed recovery; it is not counted as supported.
The original source animation remained unchanged and the failed test scene was
saved independently. Numeric tolerances and recovery locks were not weakened.

This remains a locally validated alpha. Other machines' Cascadeur host
connections and arbitrary rigs are not established by these tests. Smaller data
or faster SDK calls do not establish LLM Token savings or animation quality.
