# Host connection and recovery

The stdio server and the Cascadeur host bridge are separate processes. A
successful Python install or `tools/list` does not prove a live host connection.

Start with one read-only check using your actual installation path:

```powershell
$cascadeurHome = Read-Host 'Enter your Cascadeur installation folder'
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage doctor --cascadeur-home $cascadeurHome --live --format text
```

Each observed problem has a reason and `Next:` action. On Windows, supplying
the installation path permits exact-path process observation. Without it, no
descriptor cannot distinguish a closed application from a missing startup hook.
`UNKNOWN` is not reported as a dead process. No automatic fix, session deletion
or restart is performed. See [trial setup](TRY_IT.md) for a complete checklist.

1. Install the host hook following the README. Its source path must point to
   this checkout's `src`, not another published/development copy.
2. Save scenes and exit Cascadeur normally before updating the hook or bridge
   Python modules. Launching another executable can forward to the old process;
   that does not reload its cached Python modules.
3. Open a saved disposable scene and wait for startup to finish. Host and client
   must use the same `CASCADEUR_MCP_INSTANCE` (default `c01`).
4. Run the read-only smoke client. Accept only actual successful tool responses
   with live scene information. Keep the report private: it contains local data.

| Symptom | Meaning / safe next step |
| --- | --- |
| `BRIDGE_UNAVAILABLE` | No usable session descriptor; check host startup, checkout path and instance configuration |
| `HOST_UPGRADE_REQUIRED` | Host predates the write contract; update the host source and restart Cascadeur normally |
| `INCOMPATIBLE_HOST` / `INCOMPATIBLE_CLIENT` | Write protocol, semantic revision or schemas differ; update and restart both processes; no write is dispatched |
| `INVALID_HOST_CONTRACT` | Malformed compatibility metadata; inspect installation and restart, without editing session files |
| `HOST_SESSION_CHANGED` | Session changed before publication; rediscover the active scene/host before deciding on another write |
| `BRIDGE_TIMEOUT` | No response within deadline; inspect host/session/process before retrying; writes may already have happened |
| `SESSION_EXISTS` in host startup | Existing descriptor prevents takeover; verify its process and ownership before any cleanup; do not blindly delete runtime folders |
| `SCENE_MISMATCH` | Wrong or changed saved-scene identity; rediscover after Save As/export |
| `SNAPSHOT_NOT_FOUND` / history changed | Snapshot is expired, belongs to another scene, or an abandoned branch; use the preserved native copy |
| `EXTERNAL_EDIT_DETECTED` | Current state differs from the recorded transaction; stop agent edits and inspect manual/other-agent changes |
| `RECOVERY_REQUIRED` | Rollback could not be verified; preserve evidence and recover from a known native copy |
| Snapshot/transaction limit | Save and restart through the normal host flow; do not bypass safety limits |
| Export unavailable | Check the official license in the current Cascadeur session; no license bypass is supported |
| `HOOK_REVIEW_REQUIRED` | Preserve the differing/legacy hook and review its source; live reads can succeed while template ownership remains unverified |
| `CAPABILITIES_UNAVAILABLE` | Reads worked but loaded contract is unverified; upgrade/restart the host before relying on write compatibility |
| `NATIVE_SAVE_FAILED` | A reserved output may still be zero bytes; do not treat it as a backup or overwrite it on retry. Read back scene identity and inspect the file first. Local testing observed failure in one Unicode, cloud-synced workspace path and success in a fresh ASCII local path; the specific cause is not yet isolated |

Do not install the external MCP SDK or another Qt runtime into Cascadeur.
Do not paste session tokens into bug reports. Include OS, Cascadeur/Python/MCP
versions, operation name, redacted error, startup method and whether a fresh
saved scene reproduces it. Exclude native scenes, model dumps and credentials
unless separately and deliberately shared under their applicable terms.

Use the [local maintenance CLI](INSTALL_AND_DOCTOR.md) for installation previews,
exact-match uninstall and read-only diagnostics. Cross-machine host acceptance
remains unverified; it is not a prerequisite for continued local development.
