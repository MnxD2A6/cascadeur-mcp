# Cascadeur MCP

An experimental Python bridge that lets MCP clients inspect and edit animation
inside a running Cascadeur instance, without Computer Use.

```text
MCP client → official MCP Python SDK (stdio)
           → private local JSON queue
           → Cascadeur main-thread bridge → native scene APIs
```

## Features

- Scene/object inspection, frame access, and bounded Joint transform operations.
- Character skeleton inspection and a validated Cascy semantic rig profile.
- Named pelvis, chest, head, hand, elbow, foot and knee controls. Rig Point
  targets are writable; driven Joint transforms remain read-only in this profile.
- `set_pose_sequence`: up to eight existing frames in one checked transaction,
  with automatic rollback on failure.
- Session snapshots and a durable, single-pose JSON snapshot format.
- Native playback observation, bounded retiming, scene-copy saving and FBX
  export with a native license-entitlement check.

## Status and requirements

**Alpha research prototype, not a general production animation SDK.** Local
development validation used Windows, Cascadeur 2026.2.2 and Python 3.12.
**Validation has only been performed on the developer's local machine.
Cascadeur host connection on other machines has NOT been verified.** A clean
virtual-environment installation test on that same machine does not establish
cross-machine host compatibility.
The external package requires Python 3.10+ and the official MCP Python SDK v1.
Other operating systems, Cascadeur releases and arbitrary character rigs have
not been validated. MCP protocol compatibility is not client acceptance testing.

Cascadeur must be installed and running, with a compatible scene open. FBX
export requires an eligible license. This repository contains no Cascadeur
binaries, API stubs, character assets, game files, reference videos or audio.
Obtain any required assets directly from their owners under their own terms.

## Installation

On a new Windows machine, install Python 3.12 (including the Python launcher),
Git, and Cascadeur separately. Download or clone this repository and open
PowerShell in the extracted repository root (the directory containing
`pyproject.toml`). Internet access is needed to obtain Python dependencies.
No files from the original developer's machine are required.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
```

Install the host hook separately:

1. Close Cascadeur normally after saving your scenes.
2. Copy `cascadeur_scripts/c01_startup.py` to
   `<Cascadeur>/resources/scripts/python/events/application_started/c01_startup.py`.
   Do not overwrite an unrelated existing script.
3. In that installed copy, replace `"__C01_PROJECT_SOURCE__"` with a Python
   string literal for this checkout's absolute `src` directory. Generate the
   correctly escaped value from the checkout root with:

   ```powershell
   .\.venv\Scripts\python.exe -c "from pathlib import Path; print(repr(str(Path('src').resolve())))"
   ```

   Paste the entire printed quoted value after `PROJECT_SOURCE =`. The
   Cascadeur installation directory may require administrator write access.
4. Start Cascadeur and wait for startup to complete. The hook schedules the
   bridge on Cascadeur's Qt main thread.

Do not install the external MCP SDK or a replacement Qt runtime into Cascadeur.
Keep the checkout at the configured path. An application update may require
reinstalling the hook. To uninstall, close Cascadeur and remove only this hook.

## Usage

Start with the read-only Codex configuration in `examples/codex.toml`. Replace
its Python path with your virtual environment's absolute path. Obtain that path
with `(Resolve-Path .\.venv\Scripts\python.exe).Path`, keeping the TOML single
quotes around it. Add the sample table to your client's MCP configuration;
do not overwrite unrelated existing settings. It launches:

```text
<checkout>/.venv/Scripts/python.exe -m cascadeur_mcp.server
```

Other MCP clients can launch the same stdio command; their configuration syntax
and end-to-end behavior have not been validated here. For advanced editing,
deliberately enable the relevant tools in your client and use disposable scenes.

Run the read-only smoke client against the running host:

```powershell
.\.venv\Scripts\python.exe examples\smoke_client.py --output evidence\local\smoke.json
```

Success requires `all_tools_succeeded: true` and real scene information in the
response. The smoke output contains local runtime information and stays ignored.
If the host is unavailable, check the hook's source path, restart Cascadeur,
open a scene and confirm matching instance names. An installed Python package
alone does not provide a running Cascadeur host.

A typical editing sequence is:

1. `ping_cascadeur()` and `get_scene_info()` to verify the live host.
2. `list_characters()` to discover current scene and character IDs.
3. `get_rig_semantics(character_id)` and `get_semantic_pose(character_id, frame)`.
4. Save a native scene copy, then submit the named Point targets through
   `set_pose_sequence(scene_id, character_id, poses)`.
5. Read the solved results and inspect real playback before accepting changes.

Discover full signatures with MCP `tools/list`; do not reuse stale IDs or assume
that every tool accepts the same arguments. A semantic `direction`, `orientation`
or `bend` value is a world-position Point target, not an Euler rotation.

## Safety and limitations

- Fixed operation allowlist, strict finite-value validation and bounded payloads.
  No arbitrary shell, Python execution or generic menu-action tool is exposed.
- The private queue defaults to `%LOCALAPPDATA%\cascadeur-mcp\c01` on Windows.
  Windows ACLs restrict it to the owner and SYSTEM. Authentication does not
  protect against malicious code running as the same OS user.
- Host and client must use the same `CASCADEUR_MCP_INSTANCE` if changed from `c01`.
- Character operations address existing frames in a bounded clip (at most 121
  stored frames). Sequence writes do not extend the timeline.
- Snapshots and native Undo history are bounded. At the 16-character-snapshot
  session limit, save and restart; do not bypass the guard.
- Durable JSON snapshots restore one pose, not an entire animation. Use native
  `.casc` copies for full-scene recovery. Avoid concurrent manual/agent editing.
- A write timeout is an unknown outcome. Read back before retrying.
- FBX export currently accepts the full stored range of one supported character.
  It saves a new native copy first. Replacing an existing FBX requires its SHA-256.
- AutoPhysics/AutoPosing automation, arbitrary rigs, headless Cascadeur and a
  bundled Unity/game pipeline are not provided.

## Development and verification

`src/cascadeur_mcp` contains the server, schemas and host adapters. `tests` covers
protocol, validation and recovery-related guards. Its semantic fixture uses
invented IDs and no geometry or vendor scene data. These tests are **not** a
substitute for real Cascadeur playback, export or visual animation validation.

Local development experiments have exercised real character editing, playback
and FBX/Unity round trips. Private captures, scene dumps and game/reference
assets are intentionally excluded from this source release. See
[API provenance](API_PROVENANCE.md) for adapter scope and source references.

## License

[MIT](LICENSE) applies to this project's original source. Cascadeur and any
third-party applications, assets or dependencies retain their own licenses.
This is an independent project, not an official Cascadeur integration.
