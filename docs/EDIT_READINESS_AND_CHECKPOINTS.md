# Advisory edit readiness and long-session checkpoints

The unpublished `0.5.0a11` candidate adds one read-only tool. It does not add
automatic recovery, checkpoint loading, restart, history deletion or new native
APIs. Install/restart matching client and host sources and discover the loaded
host manifest before using a new read feature. Write-contract revision 2 remains.

## Inspect before a semantic Point edit

Call `get_character_edit_readiness` with discovered active saved-scene identity:

```json
{
  "scene_id": "<discovered scene ID>",
  "character_id": "<discovered character UUID>",
  "operation": "offset_semantic_pose_sequence_preserving_curves",
  "frames": [6, 10],
  "roles": ["right_hand"]
}
```

`operation` is one of `set_pose_sequence`, `offset_semantic_pose_sequence`,
`offset_semantic_pose_sequence_preserving_curves`. Supply 1–8 unique existing
frames (0–120) and 1–11 unique semantic roles. The selected roles determine which
tracks need existing keys for a preserving edit. Full rig validation and recovery
track checks still run, including unselected baked tracks.

- `PREFLIGHT_PASSED`: observed prerequisites passed **at this read**.
- `BLOCKED`: a known blocker is present; failed checks provide a code and next step.
- `UNKNOWN`: required native state could not be established; do not assume ready.

This read never allocates snapshots/journals, writes targets, inserts keys,
moves the playhead, saves a file or invokes Undo. It reports remaining slots:
snapshots are **global to the host session** (16 maximum), while outstanding
character transactions are **per live scene** (8 maximum). A Point edit consumes
one of each, so `edits_before_capacity_limit` is the smaller remaining count.
`checkpoint_recommended` becomes true with at most one Point edit remaining.
Nothing is reserved: another request can consume capacity immediately afterwards.
This estimate is not a budget for hand, legacy Joint or other write adapters.

New target feasibility, solver outcomes, external playback, license and visual
animation quality are **not evaluated**. Bridge-owned playback is checked.
Actual writes retain their full input, native state, post-commit and rollback
checks; preflight is not a permission token or guarantee of success. No automatic
retry is allowed, even after a passed preflight. Read actual state after timeout.

## Preserve work before capacity is exhausted

1. Stop bridge-owned playback and complete/inspect the current transaction.
2. Read all required stored frames and skeleton/track metadata as the recovery
   reference. For an entire supported clip, batch reads cover at most eight
   frames each. Native full-scene capture is an internal recovery guard, not a
   new public scene-dump interface.
3. Call the existing `save_scene_copy(scene_id, destination)` to a **new** absolute
   `.casc` destination. Preserve its returned SHA-256. A nonempty saved file is
   not proof of recoverability; fresh-session readback is the stronger gate.
4. Save-as can change active scene identity. Rediscover the active scene and
   character IDs before any further operation. Never reuse old `scene_id`.
5. Normally close Cascadeur, then open the preserved checkpoint with the normal
   supported startup workflow. There is no MCP exit/restart/open-scene tool.
   Never force terminate a process that may hold unsaved work.
6. Rediscover loaded host capabilities, current `scene_id` and `character_id`.
   Prior session `snapshot_id` values have expired. Do not reuse session tokens.
7. Compare all required frames and skeleton/track metadata with the pre-close
   reference. Only then resume edits. Confirm fresh capacity with preflight.

Native identity may persist inside the saved rig, but the source path and host
session change. Identity discovery is required regardless. Durable JSON snapshots
restore **one Pose**, not a whole animation or a full native scene.

## Failed recovery is a different situation

`RECOVERY_REQUIRED`, unknown write outcome, external edits or failed restoration
are not repaired by a restart. Stop writes and keep a **new quarantine copy** of
the uncertain state. Recover from a **previously verified** checkpoint and
compare it with the corresponding reference. Saving the uncertain current scene
does not turn it into a verified checkpoint. No journal unlock or history reset
is exposed. Do not disable rig constraints to obtain a passing preflight.

## Evidence boundaries

Offline tests cover strict input, capacity accounting, conservative unknown
results, unchanged guard state and a real writer refusing a track changed after
preflight. These are not native acceptance. Local Cascadeur acceptance separately
checks genuine writes, remaining capacity, refusal at the existing limit, native
checkpoint reopen and entire-clip comparison. Other-machine host behavior and
intermittent native exit crashes remain unverified/unresolved respectively.

Local 2026-10-04 acceptance used the real saved Polished Cascy clip in isolated
copies with matching a11 client/host and the official MCP Python SDK. Eight real
curve-preserving transactions consumed eight automatic snapshots; eight further
explicit snapshots reached the unchanged 16-slot limit. The ninth transaction
and seventeenth snapshot were refused. A checkpoint hint appeared with one
transaction remaining. Preflight rejected a non-key hand frame and a baked foot
track, without modifying native full state, playhead or caches.

After native save and a fresh Cascadeur process, all 23 frames, complete skeleton
and track metadata, and the internal full-scene capture matched the checkpoint
reference. Fresh capacity was observed; old snapshot/scene identities were
rejected. A subsequent real edit and checked Undo restoration succeeded. This
used 160 actual MCP calls for the complete acceptance, not for one normal edit.
First normal-close request ended with the known `0xC0000005` native crash;
second exited normally. Functional recovery passed; native shutdown is not fixed.
