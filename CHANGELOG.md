# Changelog

## 0.5.0a11 — Unreleased candidate

- Add read-only `get_character_edit_readiness` for three existing semantic Point
  write policies. It reports actual scene/rig/track blockers and remaining
  session snapshot / per-scene transaction capacity without allocating history.
- Reuse the real writer's native track guards; every write still checks current
  state. Advisory preflight does not validate future targets or authorize writes.
- Document whole-clip checkpoints, fresh-session identity discovery and readback.
  No automatic restart, retry, journal unlock or snapshot deletion is added.
- Retain write-contract revision 2 and all existing capacity/recovery bounds.

## 0.5.0a10 — 2026-10-04 (Alpha trial prerelease)

- Extend the read-only doctor with loaded-host version and write-contract
  verification plus optional FBX entitlement discovery through existing tools.
  Matching contracts do not establish native rig write readiness.
- Add fixed explanations and next steps, and `doctor --format text`. Export
  unavailability is a warning; write-contract mismatches require action even
  when scene reads succeed. No scene mutation or automatic repair is added.
- When `--live --cascadeur-home` is supplied on Windows, read native process
  metadata to distinguish a stopped selected installation from an undiscovered
  bridge. Restricted observations remain unknown; no shell or process control.
- Add a Windows trial checklist and clarify install, upgrade, uninstall and
  shareable feedback. Cross-machine host validation remains unverified.
- Keep write-contract revision 2; tool schemas and native adapters are unchanged.

## 0.5.0a9 — 2026-10-02 (Alpha source published)

- Check an existing failed-character-recovery journal before dispatching any
  scene write, including legacy transforms, key creation, frame changes,
  playback start and export. Previously only character adapters consulted it.
- Keep reads, stopping bridge-owned playback and saving a new `.casc` copy
  available. Save-as does not clear the lock; no automatic retry or unlock is
  added. The lock remains session-local and cannot restrict native manual edits.
- Increment write contract revision to 2 because refusal behavior changed while
  schemas stayed the same. Matching upgraded client and host are required.
- Add dispatch regression coverage for all write routes, the two escape routes,
  readback and scene isolation. Native shutdown stability is not fixed here.
- Local native fault injection reproduced the old frame-write bypass and verified
  all 17 candidate refusals, unchanged 23-frame readback and the two exceptions.
  Both stock and candidate processes still had abnormal native shutdown exits;
  this is not a claim of complete native stability or another-machine support.

## 0.5.0a8 — 2026-10-01 (Alpha)

- Recorded one native shutdown access violation after successful local
  edit/play/restore/save checks. Two isolated follow-up checks exited normally;
  the cause remains unestablished and is not reported as fixed.

- Native curve coverage found checked recovery failure on a CLAMPED_BEZIER
  Cascy fixture. Character Point and finger writes now reject that mode anywhere
  in the scene before snapshot/mutation; retiming no longer accepts it. This
  is a safety restriction, not a fix for the unresolved native recovery failure.
- Additional BEZIER and LOW_AMPLITUDE_BEZIER fixtures passed real SDK edits,
  metadata checks and full-clip recovery on the same local machine.
- Added Python installation, contract/stdio, dependency and wheel checks in a
  GitHub Actions Windows/Linux, Python 3.10/3.12 matrix. Hosted CI does not run
  Cascadeur; its workflow has not yet been executed on GitHub at preparation time.

## 0.5.0a7 — 2026-10-01 (Alpha)

- Add `edit_impact` to successful curve-preserving offsets. Group actual Point
  displacement and error against requested targets by semantic role/slot.
- Separate directly written groups, unselected solver-coupled groups and small
  changes below an explicit reporting threshold. Small does not mean unchanged.
- Build the report inside transaction verification and replace it after native
  commit. Reporting failures follow existing checked recovery, not late errors
  after an unverified write. No additional native reads are added for reporting.
- Advertise report support in the responding host's existing write feature.
  Write schemas/revision and ordinary writing behavior are unchanged; capability
  discovery, not the matching write hash, establishes optional report support.

Local Polished-Cascy acceptance independently checked eleven roles and 43 Point
slots at each of three edited keys, including unselected right-forearm coupling.
A reporting fault after native commit verified full-scene rollback; a later edit,
continuous playback and restoration passed. Regression: 455 passed, one Windows
symlink-permission skip. These results do not certify animation visual quality,
other curve modes or a second machine's host connection.

## 0.5.0a6 — 2026-10-01 (Alpha)

- Add `offset_semantic_pose_sequence_preserving_curves`, a separate existing-key
  operation. It writes selected Point channels without creating keys or changing
  interpolation; ordinary writers retain their earlier behavior.
- Verify complete track/key/easing/tangent metadata after native commit, protect
  unedited FIXED/baked tracks, external animated data, settings and Point keys
  outside the requested frames, and check the complete stored clip's geometry.
- Refuse additive stacks, cycles, custom spatial tangents and unavailable state.
  Extra metadata participates in failed-transaction recovery evidence.
- Treat local transforms, caches and rig-coupled Points at edited frames as
  solver state; report actual adjustments without weakening existing tolerances.
- New schema changes the bilateral write fingerprint; restart matching processes.

Actual local Polished-Cascy A/B (23 frames, three edited keys) retained all 13
tracks' metadata; ordinary writing changed two baked-foot tracks. Maximum foot
deviation from the source clip was 0.271669 versus 0.000643 scene units. Direct
Point writes were 129 versus 9, with one MCP transaction in either case.
These figures establish preservation, not better animation direction or Token
savings. Additional complete-clip checks add execution cost.

## 0.5.0a5 — local native-verified changes, included in 0.5.0a6

- Add `get_semantic_pose_sequence`: 1–8 unique existing frames in one request,
  preserving requested frame order and actual values. Full rig mapping is
  validated once per synchronous request; no persistent identity cache.
- Add `offset_semantic_pose_sequence`: translate every Point slot of named
  roles from each frame's own current targets in one checked transaction.
  Preflight all frames and computed absolute targets, including untouched Points.
  Keep full capture, post-commit verification, native rollback and snapshot bounds.
- Return actual solved edited roles after full verification. Relative edits are
  not idempotent and must never automatically retry. The existing write engine
  adds complete character keys and LINEAR intervals; authored easing is not preserved.
- Add the write to bilateral compatibility checks; its schema changes the write
  hash. Restart matching host and external server together.
- Reject huge integer targets as `INVALID_PARAMS` before float conversion.
- Fix the stdio regression test to launch the checkout under test rather than
  accidentally reading an installed older server.

Final local real-Cascy acceptance measured eight-frame reads at median 1.486 s
(eight calls) versus 0.214 s (one call), 6.94 times faster. The same eight-frame
right-hand translation took 4.516 s (eight reads plus one absolute write) versus
3.156 s (one relative write), 30.12% less SDK call time. Read modes ran 20 times
each; write modes ran three times each, alternating. Timings sum actual SDK call
elapsed and exclude evidence persistence, arithmetic, diagnostics and Undo.
Input method/params bytes decreased from 3,358 to 225; these are not Token counts.

Batch reads were exactly equal; three old/new edit comparisons were equivalent
under unchanged native tolerances (maximum raw difference 0.0000610352).
Six writes restored all 23 frames; a real unachievable edit verified rollback.
Preflight failures for a missing frame and computed target overflow did not start
the transaction. All 447 final calls kept the user's foreground unchanged on an
isolated desktop; normal exit restored original hook and scene hashes. This is
not a headless product capability. Regression: 411 passed, one Windows symlink
permission skip; no LLM Token, visual-quality or second-machine certification.

## 0.5.0a4 — local native-verified changes, included in 0.5.0a6

- Extend `get_semantic_pose` with bounded, unique `roles` and a strict
  `include_joint_state` boolean. Omitted options retain the full 11-role response.
- Read only selected Point and Joint Transform values after validating the
  complete semantic rig. The default semantic read no longer reads 55 Joint
  states that were previously discarded from its result.
- Declare optional read support in the actual loaded host's `read_features`.
  Older-host support cannot be inferred from the external MCP schema or the
  unchanged write contract.
- Keep full character capture, transaction verification, recovery, write schemas
  and snapshot limits unchanged. No new animation, write tool or arbitrary
  execution interface is added.

Offline regression and real native acceptance are recorded separately; response
size and read counts are not a claim of Token savings or improved motion quality.
Local native checks verified exact default/selected values across 23 frames and
a real write/Undo recovery. Twenty alternating reads per mode measured median
structured JSON sizes of 7,821 bytes (full) and 578 bytes (right-hand Points);
MCP call latency remained approximately 115 ms in the foreground trial and
214 ms on an isolated Windows desktop; neither mode showed a material selective
read speedup. The initial Hidden request did not prevent foreground activation;
the isolated-desktop retry kept the user's foreground unchanged. This private
test arrangement is not a headless feature of the product. Regression: 326 passed,
1 skipped for Windows symlink permissions.

## 0.5.0a3 — 2026-09-30 (Alpha)

- Require matching write contracts in both the client and host before dispatch.
  Contracts include protocol version, an explicit semantic revision and a
  canonical SHA-256 of write schemas; package labels are diagnostic only.
- Reject missing or incompatible host contracts before publishing a write.
  Reject legacy/incompatible client envelopes before native dispatch. Older
  protocol-1 read requests remain supported; no force or bypass option is added.
- Pin writes to the checked session and recheck its descriptor before publication.
  A later restart cannot redirect an old request into the new host session.
- Add descriptor compatibility diagnostics without conflating a local metadata
  match, a live connection, and scene/rig/license readiness.
- Keep one MCP call and one host request per batch write; no negotiation round-trip
  is required. Maintainers must bump the semantic revision for incompatible
  behavior or validation changes not expressed in schemas.

Local native acceptance: the published old client read the new host but its write
was refused; independent readback found no frame change. The candidate changed
and restored the frame, then wrote/restored a semantic pose across 23 verified
frames. This is not another-machine validation or native coverage of every
incompatibility case. Automated regression: 284 passed, 1 skipped for symlink
permissions.

## 0.5.0a2 — local release candidate, not published

- Add read-only `get_bridge_capabilities` from the actual responding host's
  loaded bridge package and allowlist. Report limits and read/write contracts;
  leave scene, rig, track and license readiness `NOT_EVALUATED`, and the
  Cascadeur application version `NOT_REPORTED`.
- Add versioned `structuredContent.error` while retaining text errors,
  `isError`, and wire protocol 1. Treat legacy string-only errors and invalid
  metadata conservatively; never infer successful rollback from error text.
- Distinguish verified `rolled_back`, `recovery_required`, unknown write
  outcomes and completed handlers whose result delivery failed. Disable
  automatic retries and retain the primary outcome when cleanup fails.
- Reject contradictory remote execution evidence and keep rejected write
  replays uncertain; preserve recovery-required status on a locked journal.
- Add validated Cascy finger-local `get_hand_pose` and `set_hand_pose_sequence`.
- Restore durable single-pose finger state as well as body Point targets.
- Preserve existing interpolation during durable pose restoration.
- Revalidate character transactions after native commit before journaling them;
  keep guarded native recovery and external-edit detection.
- Document palm targets versus finger articulation and host troubleshooting.
- Forward the explicitly configured instance to the smoke client's server child;
  do not silently fall back to another host or forward unrelated environment secrets.
- Add a separate local maintenance CLI: preview-first host install/uninstall,
  conflict protection and token-redacted static or read-only live diagnostics.

Validation remains local Windows/Cascadeur 2026.2.2. A clean Python environment
does not establish a host connection on another machine. No native assets,
universal fist presets or animation-design service are included.
Local native checks exercised the capability manifest, invalid-input and
scene-mismatch rejection, verified rollback with independent pose/joint readback,
and a subsequent semantic write/restore. This limited acceptance is separate
from offline boundary tests and does not establish recovery for every adapter
or connection on another machine.
