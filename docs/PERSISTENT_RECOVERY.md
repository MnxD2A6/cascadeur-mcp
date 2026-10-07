# Persistent failed-recovery protection (a13 Alpha)

This protects the current MCP instance after an explicitly unverified character
rollback or snapshot restore. It does **not** repair Cascadeur's native shutdown
crash or detect every unexpected process/power failure during a write.

## Behavior

The bridge saves the complete bounded pre-failure model state in a private
`recovery-required.json` beside the instance's session descriptor. This is our
own JSON representation of data, settings, object relations and captured track
metadata. It includes no mesh files, textures, audio, or authentication token.
The directory retains the bridge's owner/SYSTEM access protection. Keep this
local record out of Git, support uploads and public examples.

After a failed recovery:

1. Writes remain blocked in the current session. Reads, stopping bridge-owned
   playback and saving a **new** quarantine `.casc` remain available.
2. A normal restart retains the fence. Reopening the changed quarantine does
   not make it safe; subsequent writes are rejected before native dispatch.
3. Open the latest verified pre-failure **whole-scene native checkpoint**.
   Rediscover host/session/scene/character IDs and call `get_recovery_status()`.
4. The new host compares the full recorded model state with the actual scene.
   Identity, settings, topology and captured track metadata must match exactly;
   regenerated animated outputs use existing native roundoff tolerances.
5. `VERIFIED_CHECKPOINT_READY` permits other write checks to proceed. The status
   call does not delete the record. A successful checked write acknowledges it.

There is no force-unlock or delete-record tool. Do not manually remove the record
as a workaround. A one-pose JSON snapshot cannot replace a whole-scene checkpoint.
An older checkpoint with different stored state is not automatically accepted.

## Read-only status

`get_recovery_status()` takes no arguments. Possible results:

| Status | Meaning |
|---|---|
| `NO_PERSISTENT_RECOVERY_LOCK` | No durable fence; ordinary write checks still apply |
| `RECOVERY_REQUIRED` | Current session has unverified recovery; stop writing |
| `CHECKPOINT_MISMATCH` | Reopened data differs from the recorded pre-failure state |
| `CHECKPOINT_VERIFICATION_UNAVAILABLE` | Native complete-state read could not finish; writes blocked |
| `INVALID_RECOVERY_RECORD` | Corrupt, unsupported or unsafe record; writes blocked |
| `VERIFIED_CHECKPOINT_READY` | Complete checkpoint matches in a new host session; other checks still apply |

Missing replies remain `outcome_unknown`; no automatic retries are added. Failed
record persistence reports that cross-restart safety is **not guaranteed**. The
current memory lock remains set. If a write succeeds but record acknowledgement
fails, its completed operation is not falsely reported as rolled back.

## Installation and upgrade

Use matching client and host source, write contract revision 3, and restart both
normally. Old revision-2 writes are rejected. Hook installation keeps its existing
preview/apply/conflict behavior; no force overwrite or auto-restart is added.

`doctor` inspects the local recovery record without sending scene writes. A
present record returns actionable advice to inspect `get_recovery_status`; doctor
does not certify checkpoint content. Corrupt records fail closed. No model data
or token is emitted in the diagnostic report.

## Limits

- Protection applies to this MCP instance, not arbitrary other instances or
  native UI edits. This is not a vendor application lock.
- Full-state capture keeps the existing 121-frame/1024-object bound. Persistent
  records are capped at 16 MiB and validated with a checksum and bounded JSON
  structure. Oversized/unavailable records are errors, not successful protection.
- This first version covers explicit character transaction/snapshot recovery
  failures. Arbitrary mid-write process death and other legacy adapter recovery
  guarantees are not claimed.
- Native shutdown remains unresolved: no-MCP background save/close controls have
  reproduced a Qt access violation. No vendor DLLs or Qt files are modified.
- Other-machine host connection remains unverified. Local fresh-environment
  installation is not a substitute for a second-machine native test.
