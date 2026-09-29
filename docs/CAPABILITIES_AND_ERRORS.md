# Capabilities and structured errors

Structured errors were added in `0.5.0a2`; the current Alpha source release
`0.5.0a3` additionally enforces write compatibility on both sides.
Development validation is limited to the developer's local
Windows machine; no connection on another machine is certified.

## Discover the loaded host contract

Call `get_bridge_capabilities()` with no arguments. The request goes through the
normal authenticated bridge transport. The host checks that its Cascadeur
application exists before returning the manifest; an open scene is not required.
An unavailable host, or one without this operation, returns an error rather than
a locally manufactured capability response.

The manifest has `schema_version: 1` and `protocol_version: 1`. Its `host` reports
the responding process ID, Python version and the version constant in that
process's loaded `cascadeur_mcp` package. It does not read the current checkout
or installed distribution metadata to guess which package the host loaded.
`application_version` is `null`, with
`application_version_status: "NOT_REPORTED"`; the historical Cascadeur version
in the project documentation is not a runtime version measurement.

`operations` comes from the host's protocol allowlist. Each entry has a `read` or
`write` classification, `requires_scene`, and
`runtime_preconditions: "NOT_EVALUATED"`. Classification describes the operation
contract, not whether the current scene permits it. Snapshot creation and
playback control count as writes even when they do not directly change a pose.

`runtime_checks` leaves scene state, rig compatibility, track write safety,
export entitlement and native operation success unevaluated. `limits` and
`restrictions` describe bounded inputs and implementation requirements, not
remaining session capacity or permission to write. A known tool, a writable
channel type or an export entitlement does not prove a successful native
operation. Use the existing scene, character, rig and export-status tools as
appropriate, and read back changes before accepting them.

MCP `tools/list` still supplies signatures from the external server process.
After replacing source or changing the host installation, restart the host and
rediscover its contract; do not assume that the server and host loaded the same
files.

## Write compatibility (0.5.0a3)

The host publishes `write_contract` in its private session descriptor and its
live capability manifest. It contains integer `protocol_version`, integer
`revision`, and `schema_sha256` for the canonical write schema map, including
the write-operation allowlist. These values come from the imported modules in
that process, not a source-file or installed-distribution lookup.

Before each write the client validates this contract, checks that it matches its
own, and rereads the descriptor to catch a changed session. No write is published
for a missing, malformed or incompatible contract. The request carries the local
contract and remains bound to the checked session/token; the host authenticates
and checks the contract before dispatching a scene operation. This uses one
request per write, including a batch pose sequence. No compatibility cache or
extra negotiation request is used.

An older host without metadata yields `HOST_UPGRADE_REQUIRED`. A mismatching
contract yields `INCOMPATIBLE_HOST`; invalid metadata yields
`INVALID_HOST_CONTRACT`. The new host rejects missing/mismatching client contracts
with `INCOMPATIBLE_CLIENT`. A descriptor change detected before publication gives
`HOST_SESSION_CHANGED`. These are pre-dispatch failures. If the host restarts
after the final check, the pinned old-session request can time out with
`outcome_unknown`; it is never redirected or automatically retried.

Matching version labels alone are insufficient. Differing package labels with
identical write contracts are allowed; the explicit contract, not version-string
ordering, determines compatibility. This is not a hash of implementation code or
a claim that the rig, scene or license is ready. Maintainers must increment
`WRITE_REVISION` for incompatible behavior, validation or error-evidence changes
that leave JSON schemas unchanged. Hot reload is unsupported; restart both
processes after upgrading.

Protocol-1 read requests retain their envelope and do not require this contract.
Older hosts may lack newer read tools; ordinary read errors remain possible.
Legacy writes are intentionally refused by the new host. There is no bypass flag;
update both sides instead of modifying session files. `doctor` reports descriptor
compatibility separately from its read-only connection check.

## Error response contract

Failed MCP calls retain `isError: true` and a human-readable text content item.
They additionally return `structuredContent.error` with these fields. Human
messages are sanitized; exact legacy exception wording is not a stable API.

| Field | Meaning |
|---|---|
| `schema_version` | Error contract version, currently integer `1`. |
| `code` | Bounded uppercase machine-readable error identifier. |
| `message` | Safe human-readable explanation; it may be generic. |
| `operation` | Recognized requested operation, or `"unknown"`. |
| `phase` | The validation, dispatch, result or transport boundary reporting failure. |
| `execution_state` | Execution evidence, as defined below. |
| `rollback_verified` | `true` only for explicit verified rollback; `false` for reported failed recovery; `null` when no such evidence exists. |
| `recovery_snapshot_id` | Nullable opaque snapshot ID, not a path or a guarantee that restoration will succeed. |
| `automatic_retry_allowed` | Always `false`. |
| `recommended_action` | Suggested next step; never permission for an automatic retry. |
| `request_id`, `session_id` | Nullable transport correlation IDs. |
| `evidence` | `phase_boundary`, `explicit_preflight`, `explicit_host_state`, or `legacy_host_no_state_evidence`. |
| `cleanup_failed` | Whether cleanup also failed after the primary error. |

Recognized phases are `client_validation`, `client_session`, `client_publish`,
`client_response`, `host_validation`, `host_dispatch`, `host_result` and
`client_cleanup`. A phase identifies where the problem was reported; it alone
does not prove whether a write occurred.

| Execution state | Interpretation and next step |
|---|---|
| `not_started` | Validation or explicit preflight rejected this attempt before mutation. Correct the input or prerequisites before another deliberate attempt. |
| `read_failed` | A read did not return a successful result. Inspect the connection or prerequisites. |
| `outcome_unknown` | A write may have executed. Read back the relevant scene state or output files before deciding whether to retry. |
| `rolled_back` | The adapter explicitly verified restoration; `rollback_verified` is `true`. Inspect the cause and correct it before retrying. |
| `recovery_required` | Recovery could not be established. Stop writes and inspect or recover the preserved scene. |
| `completed` | The handler returned successfully, but a later result/transport step failed. Read back; do not repeat the operation automatically. |

Snapshot IDs remain subject to the existing scene, history and lifetime guards.
Not every adapter proves rollback. An error name or text mentioning rollback,
a failed write, and even an available recovery snapshot are insufficient to
claim that the scene is unchanged. Only explicit typed evidence produces
`rolled_back` with `rollback_verified: true`.
A character journal locked after failed recovery continues to report
`recovery_required` when a later write reaches that guard.

Timeouts, uncertain request publication, invalid responses and rejected write
replays are conservative: a missing reply is not proof that the write never
ran. The `recommended_action` values direct callers to inspect prerequisites,
start the matching host, read back, correct the failed input, or stop writes and
recover. None enables automatic retries.

## Compatibility and cleanup

The base wire protocol remains version 1; writes now require `write_contract`.
New hosts retain the string `error` field
and add `error_details`. The client validates structured details and rebuilds
the public error instead of copying arbitrary host messages or extra fields.
Host metadata must also have a consistent execution state, phase and evidence
source. Contradictory combinations are rejected; a rejected write replay cannot
be reclassified as a write that never started.

For an older host that supplies only a string, writes become
`outcome_unknown`, reads become `read_failed`, and rollback/snapshot evidence
is `null`. Error text is never parsed into a claim that nothing happened or
that rollback succeeded. Invalid or unsupported error metadata is also treated
conservatively and reported as `INVALID_ERROR_DETAILS`.

Cleanup failure does not replace the primary failure: its error gains
`cleanup_failed: true`. If a successful response was already received, the
result remains successful and includes
`transport_warnings: ["CLEANUP_FAILED"]`; this warning is not a reason to replay
the operation.

## Verification status

For `0.5.0a3`, the existing published MCP client and the candidate MCP client were
both run through the official SDK's stdio transport against one real updated
Cascadeur 2026.2.2 host on this Windows machine. The published client could read
the scene, but a frame-write attempt was rejected with `INCOMPATIBLE_CLIENT`;
independent candidate readback confirmed the frame was unchanged. The candidate
then changed and restored the current frame successfully, and performed a
semantic pose transaction followed by verified native restore across 23 frames.
No Computer Use was used. This is an actual old-client/new-host check; the
new-client/old-host metadata rejection and restart race checks use simulated
transport fixtures and are not claimed as additional native acceptance.

On 2026-09-30, an independent Cascadeur process on the developer's local Windows
machine also exercised this limited `0.5.0a2` native acceptance scope:

- The manifest reported package `0.5.0a2`, embedded Python `3.11.0` and 34
  declared operations. This enumerated the contract; it did not execute all 34
  operations. The Cascadeur application version remained `NOT_REPORTED`.
- Invalid arguments returned `INVALID_PARAMS` with `not_started`. A scene
  mismatch returned `SCENE_MISMATCH` with `explicit_preflight` / `not_started`;
  independent frame readback confirmed the frame was unchanged.
- A valid numeric but unachievable hand target returned `CHARACTER_POSE_FAILED`
  with `rolled_back` and `rollback_verified: true`. Independent semantic pose
  and joint readback matched the state captured before the attempt.
- A subsequent normal semantic write and snapshot restore succeeded.

These observations do not establish native coverage for every adapter, every
failure state, export behavior or visual animation quality. Offline manifest,
protocol and simulated error-boundary tests remain separate evidence; in
particular, their recovery-required cases are not claims of native acceptance.
Host connection on another machine has not been verified.
