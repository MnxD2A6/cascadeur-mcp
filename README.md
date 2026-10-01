# Cascadeur MCP

Version `0.5.0a8` adds a fail-closed safety restriction after native
CLAMPED_BEZIER recovery failed: character Point and finger writes reject scenes
containing that mode before editing. Retiming no longer accepts it. This does
not repair Cascadeur Undo. Reads and the verified curve modes remain available.

Version `0.5.0a7` adds a semantic `edit_impact` report to
curve-preserving offsets: direct edits and solver-coupled Points are grouped by
body role and slot, using actual verified native targets. See
[edit-impact reports](docs/EDIT_IMPACT.md).

Version `0.5.0a6` adds
`offset_semantic_pose_sequence_preserving_curves`: a separate existing-key edit
that keeps track/key/interpolation/easing metadata and protects unedited baked
tracks. See [curve-preserving editing](docs/CURVE_PRESERVING_EDITING.md) for its
strict supported scope. Existing writing tools keep their previous behavior.

An experimental Python bridge that lets MCP clients inspect and edit animation
inside a running Cascadeur instance, without Computer Use.

```text
MCP client → official MCP Python SDK (stdio)
           → private local JSON queue
           → Cascadeur main-thread bridge → native scene APIs
```

## Features

- `get_bridge_capabilities`: read the responding host's loaded bridge version,
  operation classifications, limits and restrictions without probing a rig or license.
- Structured execution errors alongside the existing text and MCP error flag,
  including unknown write outcomes and explicitly verified recovery states.
- Bilateral write-contract checks: outdated or incompatible peers cannot write;
  existing read-only diagnostics remain usable with older protocol-1 hosts.
- Scene/object inspection, frame access, and bounded Joint transform operations.
- Character skeleton inspection and a validated Cascy semantic rig profile.
- Named pelvis, chest, head, hand, elbow, foot and knee controls. Rig Point
  targets are writable; driven Joint transforms remain read-only in this profile.
- Optional role selection and joint-state omission in `get_semantic_pose` reduce
  unnecessary Transform reads and response data while retaining full rig validation.
- `get_semantic_pose_sequence`: read up to eight existing frames once, with the
  same optional selection and actual native values.
- `offset_semantic_pose_sequence`: translate whole named Point groups across
  up to eight frames once, from each frame's real current targets. Full capture,
  checked commit and rollback remain; this key-authoring operation uses LINEAR
  intervals and does not preserve authored easing. See
  [batch workflow and limits](docs/BATCH_SEMANTIC_EDITING.md).
- `set_pose_sequence`: up to eight existing frames in one checked transaction,
  with guarded rollback attempts and explicit recovery-required errors.
- Session snapshots and a durable, single-pose JSON snapshot format.
- Validated Cascy finger-local read/write channels through `get_hand_pose` and
  `set_hand_pose_sequence`; hand Point targets alone do not make a fist.
- Native playback observation, bounded retiming, scene-copy saving and FBX
  export with a native license-entitlement check.

## Status and requirements

**Alpha research prototype, not a general production animation SDK.** Local
development validation used Windows, Cascadeur 2026.2.2 and Python 3.12.
Current source version: `0.5.0a8` (Alpha).
**Validation has only been performed on the developer's local machine.
Cascadeur host connection on other machines has NOT been verified.** A clean
virtual-environment installation test on that same machine does not establish
cross-machine host compatibility.

Native shutdown stability remains under investigation. One local session
completed edit/play/restore/save checks but exited with `0xC0000005` in
`Qt6Core.dll` after a normal close request. Two isolated follow-up checks
exited normally; they do not establish a fix or the native cause. Original
source scenes remained unchanged. This alpha does not claim production-safe
native shutdown across every workflow.

The GitHub workflow in `.github/workflows/python-tests.yml` is configured to run installation,
Python contract/stdio tests, dependency checks and wheel-import checks on Windows
and Linux with Python 3.10 and 3.12. Hosted CI does not install Cascadeur and does
not establish native rig editing or another machine's host connection. Native
curve validation is documented separately in [curve-preserving editing](docs/CURVE_PRESERVING_EDITING.md).

The external package requires Python 3.10+ and the official MCP Python SDK v1.
Other operating systems, Cascadeur releases and arbitrary character rigs have
not been validated. MCP protocol compatibility is not client acceptance testing.

Cascadeur must be installed and running. Scene-dependent tools require a
compatible open scene; ping and capability discovery do not. FBX export requires
an eligible license. This repository contains no Cascadeur
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

Install the host hook separately. Save scenes and close Cascadeur normally.
Replace the example installation path, preview, then apply:

```powershell
$cascadeurHome = 'D:\Apps\Cascadeur' # your actual Cascadeur installation
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage install-host --cascadeur-home $cascadeurHome
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage install-host --cascadeur-home $cascadeurHome --apply
```

This generates the source path safely and creates only the documented startup
hook. An existing different hook returns `HOOK_CONFLICT` and remains untouched;
there is no force overwrite. Write access may require administrator permissions.
Then start Cascadeur and open a scene. The hook schedules the bridge on
Cascadeur's Qt main thread. Check the connection:

```powershell
.\.venv\Scripts\python.exe -m cascadeur_mcp.manage doctor --live
```

See [installation and diagnostics](docs/INSTALL_AND_DOCTOR.md) for instances,
error codes, static checks, and exact-match uninstall. Without `--apply`, hook
maintenance commands only preview. Without `--live`, doctor sends no requests.

Do not install the external MCP SDK or a replacement Qt runtime into Cascadeur.
When upgrading, save scenes and exit Cascadeur normally, update the package, then
restart both Cascadeur and the external MCP server. A cached old host or client
will be refused for writes. The write contract compares protocol, semantic
revision and write schemas; matching package version strings alone are not proof
of compatibility. See [capabilities and errors](docs/CAPABILITIES_AND_ERRORS.md).
Keep the checkout at the configured path. An application update may require
reinstalling the hook. Close Cascadeur before using `uninstall-host --apply`.

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

1. `get_bridge_capabilities()` to read the loaded host contract, then
   `ping_cascadeur()` and `get_scene_info()` to check the host and active scene.
2. `list_characters()` to discover current scene and character IDs.
3. `get_rig_semantics(character_id)` and `get_semantic_pose(character_id, frame)`.
4. Save a native scene copy and rediscover its scene ID, then submit the named
   Point targets through `set_pose_sequence(scene_id, character_id, poses)`.
5. Read the solved results and inspect real playback before accepting changes.

Discover full signatures with MCP `tools/list`; do not reuse stale IDs or assume
that every tool accepts the same arguments. A semantic `direction`, `orientation`
or `bend` value is a world-position Point target, not an Euler rotation.

Capability `read`/`write` classifications describe supported operation contracts,
not current execution readiness. Scene, rig, track and license checks remain
`NOT_EVALUATED`; the Cascadeur application version is `NOT_REPORTED`. See
[capabilities and structured errors](docs/CAPABILITIES_AND_ERRORS.md) for the
loaded-host contract, error fields and conservative handling of older hosts.

Finger input uses local unit quaternions `[w,x,y,z]` and named finger segments,
not those world-position targets. Read [hand controls](docs/HAND_CONTROLS.md)
before editing. There is no universal `fist` preset or automatic motion generator.
For connection failures, use [troubleshooting](docs/TROUBLESHOOTING.md).

For focused inspection, `get_semantic_pose` accepts `roles`, such as
`["right_hand"]`, and `include_joint_state: false`. Omitted options keep the full
11-role result and read-only joint states. Discover support in the responding
host's `read_features`; update and restart both processes before using these
options. A matching write contract does not establish read-option support on an
older host. See [selective reads](docs/SELECTIVE_READS.md) for examples and limits.

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
- A write timeout is an unknown outcome. Read back before retrying; structured
  errors never authorize automatic retries.
- `rolled_back` requires explicit verified restoration. `recovery_required`
  means stop writes and inspect or recover the preserved scene. Not every
  adapter proves rollback, and error text alone is not recovery evidence.
- Character transaction journals are checked after native commit. Durable pose
  restoration preserves existing interpolation settings; it is still a single
  pose operation and can recompute adjacent interpolation.
- FBX export currently accepts the full stored range of one supported character.
  It saves a new native copy first. Replacing an existing FBX requires its SHA-256.
- AutoPhysics/AutoPosing automation, arbitrary rigs, headless Cascadeur and a
  bundled Unity/game pipeline are not provided.

## Development and verification

`src/cascadeur_mcp` contains the server, schemas and host adapters. `tests` covers
protocol, validation and recovery-related guards. Its semantic fixture uses
invented IDs and no geometry or vendor scene data. These tests are **not** a
substitute for real Cascadeur playback, export or visual animation validation.
A local native acceptance check exercised capability discovery, preflight
rejection, a verified rollback after an unachievable hand target, and a later
semantic write/restore. See the [recorded scope](docs/CAPABILITIES_AND_ERRORS.md#verification-status);
this does not establish recovery for every adapter or connection on another machine.

Local development experiments have exercised real character editing, playback
and FBX/Unity round trips. Private captures, scene dumps and game/reference
assets are intentionally excluded from this source release. See
[API provenance](API_PROVENANCE.md) for adapter scope and source references.

## License

[MIT](LICENSE) applies to this project's original source. Cascadeur and any
third-party applications, assets or dependencies retain their own licenses.
This is an independent project, not an official Cascadeur integration.
