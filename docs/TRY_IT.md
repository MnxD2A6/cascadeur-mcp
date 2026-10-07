# Windows Alpha trial guide

This guide targets the supplied 0.5.0a11 source/wheel prerelease. It is not a
stable release or a claim that PyPI contains this package. Cascadeur host
connection has only been validated on the developer's local Windows machine;
other machines remain unverified. Testing a fresh Python environment locally
does not replace another-machine testing.

## What you need

- Windows, Cascadeur installed separately, and external Python 3.12 with the
  `py` launcher. The package supports Python 3.10+, but 3.12 was locally tested.
- Internet access to install the official MCP Python SDK dependencies.
- An MCP client supporting stdio. Codex was locally tested; other clients
  require their own configuration and acceptance testing.
- Your own legally available saved scene copy. The validated semantic profile
  is Cascy; arbitrary rigs are unsupported. The trial package includes no scenes,
  models, animations, videos, audio, Unity projects or Cascadeur binaries.
- An eligible Cascadeur license only if you intend to export FBX. Read/edit
  connection diagnostics do not require that export entitlement.

## Install from the source archive

Extract the source ZIP into a permanent local directory. Open PowerShell in
the directory containing `pyproject.toml`; do not execute these steps from the
outer download folder. The checkout must stay at this path while the hook uses it.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import cascadeur_mcp; print(cascadeur_mcp.__version__)"
```

Expected trial version: `0.5.0a11`. No activation script is required.
Developers may instead install `".[test]"` and run `python -m pytest -q`.

Alternatively, create the external environment in a permanent directory and
install the supplied wheel with that environment's Python:

```powershell
.\.venv\Scripts\python.exe -m pip install 'C:\Downloads\cascadeur_mcp-0.5.0a11-py3-none-any.whl'
.\.venv\Scripts\python.exe -m pip check
```

Replace the wheel path. A wheel hook uses this environment's `site-packages`,
not checkout `src`; keep the environment in place. Use one installation route,
not both simultaneously. Dependencies are downloaded normally; this is not an
offline dependency bundle. Do not install the SDK or a replacement Qt into Cascadeur.

## Connect the host

Save your scenes and close Cascadeur normally. Replace the installation path:

```powershell
$cascadeurHome = Read-Host 'Enter your Cascadeur installation folder'
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage install-host --cascadeur-home $cascadeurHome
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage install-host --cascadeur-home $cascadeurHome --apply
```

The first command previews, the second creates only the bridge's managed
startup file. `HOOK_CONFLICT` preserves existing code; review it rather than
overwriting. Permissions may require installing into a writable location or
using your own administrator workflow. The tool never elevates automatically.

Start Cascadeur normally and open your disposable saved scene. Then run:

```powershell
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage doctor --cascadeur-home $cascadeurHome --live --format text
```

This reads the connection, loaded write contract and optional native FBX
entitlement. Each problem has a `Next:` instruction. It does not edit a scene
or export. `CONNECTED` means reads and matching contract, not that your rig,
tracks, rollback, motion quality or export output has been validated.
`CONNECTED_WITH_WARNINGS` can mean FBX entitlement is unavailable while the
read connection works. `ACTION_REQUIRED` means follow the listed next step.
An existing legacy hook can work but still require review.

## Connect Codex

Find your external Python path:

```powershell
(Resolve-Path .\.venv\Scripts\python.exe).Path
```

Copy the table from `examples/codex.toml` into your Codex MCP configuration,
replace its `command` with this exact path, and preserve unrelated entries.
The sample deliberately enables three read-only scene tools. Restart/reconnect
the MCP client after configuration changes. First ask it to call
`ping_cascadeur`, `get_scene_info`, and `get_objects` on the running host.
Real returned data is the first connection acceptance, not `tools/list` alone.
Keep host and client `CASCADEUR_MCP_INSTANCE` equal (default `c01`).

For editing, enable only the needed tools after reading their contracts. Keep
a separate native scene copy, discover current IDs, inspect rig semantics, and
read back results. A matching contract is not permission to ignore rig/track
restrictions. Stop on `recovery_required`; read back before deciding whether to
retry an unknown write outcome. Do not edit concurrently by hand and agent.

## Upgrade or uninstall

Follow [UPGRADING.md](UPGRADING.md). Save native checkpoints, normally close
Cascadeur and stop/reconnect the client, then update the selected package.
Both processes cache modules; source replacement is not hot reload.
Moving paths requires uninstalling the exact old managed hook before installing
the new one. Preserve the old environment until this step is verified.

To remove the host connection, close Cascadeur and run with the same environment
and source path that installed the hook:

```powershell
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage uninstall-host --cascadeur-home $cascadeurHome
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage uninstall-host --cascadeur-home $cascadeurHome --apply
```

Only the exact managed file is removed. Modified hooks return `HOOK_CONFLICT`
and remain intact. Remove only this MCP configuration table from your client,
then optionally uninstall the external package:

```powershell
.\.venv\Scripts\python.exe -m pip uninstall cascadeur-mcp
```

This does not uninstall Cascadeur, delete scenes or delete your environment.

## Known limits and useful feedback

This remains an Alpha: supported scene/frame bounds, Cascy profile, curve-mode
restrictions and bounded snapshots apply. AutoPhysics/AutoPosing automation,
universal rigging, automatic motion generation and bundled game integration
are not provided. Intermittent native shutdown access violations are unresolved;
successful edits and one normal exit do not establish a fix.

If reporting a trial result, include OS, Cascadeur version shown in the app,
external Python/package version, install route, diagnostic code and its next
step, whether the client could read real scene data, and whether normal exit
succeeded. Prefer the short text diagnostic. JSON includes local paths/PIDs;
redact these before sharing. Never include session tokens, credentials, native
scenes, model data, commercial media, raw dumps or full logs by default.
No command in this guide submits a report automatically.

See [troubleshooting](TROUBLESHOOTING.md), [API provenance](../API_PROVENANCE.md),
and [MIT license](../LICENSE). Cascadeur and dependencies retain their own licenses.
