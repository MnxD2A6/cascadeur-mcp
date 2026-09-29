# Hand controls

Supported profile: the locally validated Cascy rig in Cascadeur 2026.2.2.
Other rigs and host machines have not been validated. Discover the current
character with `list_characters`; never persist a display name or list offset
as the identity. Finger bindings check RigInfo membership, unique native names,
real parents, animated local-rotation channels and exclusive unlocked tracks.

## Two different controls

| Interface | Input | Effect |
| --- | --- | --- |
| `set_semantic_pose` / `set_pose_sequence` | Hand Point targets in world scene units | Move and orient the palm through the rig |
| `get_hand_pose` / `set_hand_pose_sequence` | Finger-local quaternion `[w,x,y,z]` | Read/write finger articulation |

Moving a hand Point does not close its fingers. A unit quaternion is not an
Euler angle, curl percentage, or guaranteed fist. No calibrated character
assets, animation presets, or universal hand-shape values are shipped.

## Contract

- Read: `get_hand_pose(character_id, frame)`. Result includes `hands`, bindings,
  `scene_id`, `character_id`, frame and coordinate-space description.
- Write: `set_hand_pose_sequence(scene_id, character_id, poses)`.
- Each entry is `{"frame": frame, "hands": {"right": finger_patch}}` or uses
  `left`, or both hands together.
- Each finger patch maps names to four finite unit quaternion components.
  Names are `thumb1..3`, `index1..3`, `middle1..3`, `ring1..3`, `pinky1..3`.
  Terminal segment 4 and arbitrary Joint IDs are deliberately not writable.
- A sequence contains 1–8 distinct existing frames, each within 0–120 and the
  actual stored timeline. It cannot extend the clip.
- The two hands and all requested frames are written in one MCP call and one
  native transaction. Unspecified finger channels are not directly assigned;
  native interpolation may change their surrounding evaluated results.
- The adapter verifies non-finger joint and body Point state at every stored
  frame and rejects body-track changes. Constraint/rig checks remain enabled.

## Safe first test

Use a disposable saved scene copy. Read a hand pose at an existing frame,
construct a single sequence entry with exactly that returned `hands` map,
and write it back using the currently discovered IDs. Verify the readback and
snapshot restore before authoring a new shape. Even same-value writes can
create keys, so they are not read-only operations.

Capture a native scene copy for whole-animation recovery. Session snapshot IDs
expire on restart. Durable JSON snapshots can restore a single pose including
validated finger channels across sessions of the same compatible saved rig;
they are not portable across arbitrary characters or a whole-clip backup.

On a write timeout, inspect the actual scene before deciding whether to retry.
An unverified recovery locks the journal. Do not reset tolerances or bypass
track/identity guards to make a request succeed.

## Evidence boundary

Local testing exercised finger rotation, both-hand batch writing, whole-body
preservation, native Undo, persistence/reload, durable restoration and real
FBX/Unity playback. These results do not establish cross-machine connection,
arbitrary-rig support, automatic fist quality, or production certification.
