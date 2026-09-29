# Changelog

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
