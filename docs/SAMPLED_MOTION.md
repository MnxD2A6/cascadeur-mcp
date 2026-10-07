# Complete sampled Point motion (introduced in a12, included in a13)

Ordinary `set_pose_sequence` retains 1–8 entries. Explicit `sampled_motion=true`
accepts 1–64 **complete** Cascy-v1 semantic Point poses at strictly increasing,
existing frames, inside one checked native transaction. No body Joint rotations,
shell/Python execution, timeline extension or rig-constraint disabling is exposed.

## Prepare and apply

1. Preserve an independent native scene copy. Rediscover scene/character IDs after
   any Save As; opaque session snapshots belong to their original live scene.
2. Read the current frame count. Play `0..frame_count-1` through `play_animation`,
   then call `stop_animation` until measured stop and full range coverage are
   confirmed. Both native playback **and visible** boundaries must cover the clip.
   Without this, sampled writes fail before snapshot/mutation with
   `FULL_TIMELINE_RANGE_REQUIRED`.
3. Read rig semantics. Each sampled entry supplies every returned role and slot.
   Feet, hands, elbows and knees must preserve rigid control-group distances
   across samples within 0.05 scene units. This mode does not support independent
   toe articulation/variable control-group shapes; use ordinary supported edits.
4. Submit one `set_pose_sequence` call with `sampled_motion: true` and `poses`.
   Positions are finite world scene units, bounded by the advertised schemas.
5. The result returns frame indices, actual native Point SHA-256 hashes,
   rig connection checks and maximum solver adjustment; full poses are omitted
   to stay within the existing 256 KiB transport budget. Read actual poses using
   `get_semantic_pose_sequence`, up to eight frames per call. A write timeout has
   unknown outcome: read back and inspect recovery before any retry.
6. Save/export separate files; cold-reload readback is required when persistent
   output matters. A snapshot does not survive restart or a changed scene path.

For hierarchy reads on clips with many keys, use
`get_character_skeleton(character_id, include_track_sections=false)`. It retains
all joints/parents, controls, bindings, constraints, track membership and key
indices; only per-key section detail is omitted. Default behavior is unchanged.

## Local evidence and safety

Windows/Cascadeur 2026.2.2, Cascy: 66 joints, 43 Point controls, 64 stored frames.
The 64-target draft required eight ordinary writes; the explicit sampled path
needs one write call. The final installed a12 smoke measured about 10 seconds
for the single SDK tool call. This is one scene-specific observation, not a
controlled speed benchmark or token estimate.
Full 0–63 native playback, full-state snapshot restoration in one guarded Undo,
and a deliberately unreachable last-frame hand target were tested. The last
failure returned explicit `rolled_back/rollback_verified=true`, with full-clip
Point readback error below 0.00002 scene units and unchanged rig metadata.

The discovery matters: this 64-frame scene retained a 0–55 visible native range.
Undo restored topology/keys but left derived data at 56–63 inconsistent. Setting
all four documented `AnimationBoundary` properties fixed the observed playback
and recovery case; no message, solver, snapshot, transaction or Undo-action
limit was relaxed. Existing unsupported curve/rig modes remain rejected.

Native checks establish supported data/rig integrity. They do **not** establish
physical ground contact, balance, reference-video fidelity or artistic quality.
The video reconstruction experiment is separate, unpublished research; model
weights, source videos, Cascadeur assets and scenes are not bundled here.
**Only this local machine has been validated; other-machine host connections
remain unverified.** Restart host and MCP client together after upgrading so
write contracts match. These features are included in the a13 source update;
the earlier packaged a11 trial does not contain them.
