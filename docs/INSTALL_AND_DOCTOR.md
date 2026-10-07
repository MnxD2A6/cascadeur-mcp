# Local installation and diagnostics

These commands run with the external Python environment, separately from MCP
stdio. They do not add scene tools or change the bridge protocol. They never run
a shell, terminate Cascadeur, restart it, remove session descriptors or edit scenes.

## Host hook

Save scenes and close Cascadeur normally before applying an install or uninstall.
Set `$cascadeurHome` to your existing Windows Cascadeur installation directory.
The expected layout contains `cascadeur.exe` and
`resources/scripts/python/events/application_started/`.

```powershell
$cascadeurHome = Read-Host 'Enter your Cascadeur installation folder'
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage install-host --cascadeur-home $cascadeurHome
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage install-host --cascadeur-home $cascadeurHome --apply
```

Without `--apply`, install and uninstall are previews and do not create files.
The only installed file is `c01_startup.py` in that event directory. The generated
hook uses the existing documented application-started / scene-idle startup flow.
No proprietary files are copied or distributed. The source defaults to the
directory containing the installed `cascadeur_mcp` package; editable installs
point to the checkout's `src`. An explicit `--source` must be an absolute directory
containing that package. Spaces and Unicode are escaped as a Python string literal.
Keep that source directory in place while the hook is installed.

Installation publishes a complete file exclusively. Identical contents return
`ALREADY_INSTALLED`. Any different existing contents return `HOOK_CONFLICT`,
including a legacy manual hook or a hook pointing to another checkout. It is never
overwritten. Review existing scripts separately; this command deliberately offers
no force option. Administrator permissions may be required by the installation
directory; the tool does not elevate itself.

Uninstall uses the same `--source` (or the same installed package) as installation:

```powershell
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage uninstall-host --cascadeur-home $cascadeurHome
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage uninstall-host --cascadeur-home $cascadeurHome --apply
```

Only the exact generated hook can be removed. Edited scripts are preserved and
reported as conflicts. This is not a general rollback or backup utility. It does
not uninstall Cascadeur or Python. Do not run concurrent manual hook edits during
maintenance. Symlinks/junctions in managed paths are rejected. Installation needs
a filesystem supporting hard links for exclusive atomic publication; unsupported
filesystems fail rather than fall back to overwriting an existing file.

## Doctor

Version a13 also inspects persistent failed-recovery records locally.
`RECOVERY_FENCE_PRESENT` means call the read-only `get_recovery_status` after
opening the latest verified native checkpoint. Doctor does not compare complete
scene state and never clears the record. See [persistent recovery](PERSISTENT_RECOVERY.md).

```powershell
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage doctor --cascadeur-home $cascadeurHome
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage doctor --instance c01 --live
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage doctor --cascadeur-home $cascadeurHome --live --format text
```

Default mode reads package metadata, validates the source and session descriptor,
and optionally inspects the hook. It does not send requests. A valid descriptor
returns `DESCRIPTOR_VALID_NOT_CONNECTED`; its recorded PID is not proof of a live
process. No PID liveness probe or stale-session deletion is performed.

`--live` sends only existing read operations: `ping_cascadeur`, `get_scene_info`,
`get_bridge_capabilities`, and optionally `get_fbx_export_status` when advertised
as read-only. It checks actual host PID and pinned session identity, reports the
loaded host version/write contract, and checks native export entitlement without
exporting a file. It writes temporary protocol requests, not scene data.
`--timeout` is per request, greater than zero and at most 20 seconds; up to four
calls can take four times that time. There is no automatic retry.
The instance defaults to `CASCADEUR_MCP_INSTANCE`, or `c01` when unset.
The host must have started with the same instance configuration.

On Windows, `--live --cascadeur-home` also reads process metadata through Win32
APIs, matching the exact selected executable path. This distinguishes a stopped
selected installation from a running installation with no discovered session.
Permission-restricted results remain `UNKNOWN`; another installation is not
mistaken for this one. Static mode never probes processes. This is observation,
not process control or proof that the bridge loaded.

Output is JSON. Success is exit 0; a failed check is exit 1; CLI syntax errors are
exit 2. Optional hook inspection can fail even when the separate live connection
succeeds: a legacy script is reported as unmanaged, never silently certified by
its path alone. Installed scripts are parsed, never executed by the doctor.

| Status | Meaning |
| --- | --- |
| `CONNECTED` | Scene reads succeeded and the loaded write contract matches; rig/write success remains untested |
| `CONNECTED_WITH_WARNINGS` | Read connection succeeded but an optional check is unavailable or the scene is empty |
| `ACTION_REQUIRED` | A connection/configuration/compatibility check failed; see `diagnostics` |
| `STATIC_CHECK_ONLY` | Local checks passed; no live host connection was tested |
| `CASCADEUR_NOT_RUNNING` | No live process for the selected installation was observed; start it normally |
| `BRIDGE_NOT_DISCOVERED` | Selected installation is running, but no session for this instance was found; check startup hook/source/instance |
| `HOOK_NOT_INSTALLED` | Close Cascadeur, preview install-host, then apply the reviewed preview |
| `HOOK_REVIEW_REQUIRED` | Hook differs from the managed template; preserve and review it, even if a live legacy hook works |
| `INCOMPATIBLE_HOST` | Live reads worked, but loaded write contract differs; upgrade/restart both peers |
| `CAPABILITIES_UNAVAILABLE` | Reads worked but loaded contract was not checked; treat writes as unverified |
| `EXPORT_UNAVAILABLE` | Current native export entitlement is false; check official license/sync; other tools can still work |
| `EXPORT_STATUS_UNAVAILABLE` | Native export entitlement could not be checked; no export was attempted |
| `NO_DESCRIPTOR` | No session file for that instance; inspect normal host startup |
| `INVALID_DESCRIPTOR` | Malformed/unsupported descriptor; no token is echoed |
| `BRIDGE_TIMEOUT` | No response before deadline; liveness is unknown |
| `HOST_IDENTITY_MISMATCH` | Reply does not match the recorded host PID/application |
| `HOST_ERROR` | Host rejected the read; inspect Cascadeur locally for detail |
| `PERMISSION_DENIED` | A required filesystem operation was denied |
| `HOOK_CONFLICT` | Existing hook differs; leave it intact and review locally |
| `FILESYSTEM_ERROR` | Filesystem operation failed; no raw exception is disclosed |

Raw session data, tokens, scene names and arbitrary host errors are omitted.
Output still contains local source paths and PIDs: review/redact before sharing.
`descriptor_write_compatibility` compares the session descriptor's write contract
to this client (`COMPATIBLE`, `HOST_UPGRADE_REQUIRED`, `INCOMPATIBLE_HOST`, or
`INVALID_HOST_CONTRACT`). `descriptor_package_version` is a bounded version label
from that file. Neither proves a live process or a writable rig. In live mode,
`live_write_compatibility` comes from the responding host manifest, and
`host_package_version` is its bounded loaded version label; client metadata is
never substituted for host metadata. Missing manifests preserve read diagnostics
but leave write compatibility `NOT_EVALUATED`. A contract mismatch returns exit 1
even if the separate scene reads succeeded. Missing export entitlement is a
warning and does not fail an otherwise successful connection. `write_readiness`
always remains `NOT_EVALUATED`: no write, recovery, rig or track test was performed.

JSON is the default output and includes fixed `diagnostics` entries with `code`,
`severity`, `message`, and `next_step`. `--format text` prints a short explanation
and next step. Local paths and PIDs still appear in JSON; redact them before sharing.
Both formats omit tokens, scene names, arbitrary errors and host strings.

Upgrade both the external package and host source, then restart both processes.
Do not edit session descriptors to suppress a mismatch. Old protocol-1 clients
can still read, but the new host refuses their writes until the write contract is
provided. See [the compatibility contract](CAPABILITIES_AND_ERRORS.md).

## Validation boundary

Local isolated install/uninstall tests and native host tests are separate
evidence. On the developer's Windows machine, a newly generated hook was installed
into Cascadeur 2026.2.2 and loaded after a normal restart. Real MCP calls read a
disposable Cascy scene, changed one finger rotation, restored it with native Undo,
and independently read back the result. The bridge verified all 23 stored frames
on restore. Embedded Python was 3.11.0; external Python was 3.12.6 with MCP 1.30.0.
After normal exit, the generated hook was uninstalled and the backed-up original
hook restored with an identical SHA256. Normal shutdown removed the test session
descriptor without forced cleanup.
Synthetic installation layouts test file handling only and do not replace this
native test. Other machines remain unverified. Access to a second computer is not
required to continue local development; no cross-machine compatibility is claimed.
