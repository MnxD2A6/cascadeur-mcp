# Upgrading the Alpha bridge

The a9 source was published on main on 2026-10-02. The a10 Alpha trial is available
as a GitHub prerelease. Obtain its source or supplied
wheel first; do not assume a package index provides it. The following source
checkout steps target a10. For wheel installation, use the matching wheel path
in place of the editable-install command.

The a8-to-a9 write contract changed from revision **1** to **2**, while tool
schemas stayed the same. a10 retains revision 2 and changes only the external
diagnostic CLI and trial documentation. Upgrade **both** the external MCP server and Cascadeur's bridge source,
then restart both processes. Matching version labels alone are insufficient.
This adds a recovery write gate; it does not fix native shutdown crashes.

## Keep the current checkout and environment paths

1. Save your scenes and a separate known-good `.casc` checkpoint. Normally close
   Cascadeur and stop the MCP server through your client's MCP connection controls.
   Do not overwrite source files while either process still uses the old modules.
2. Preserve any local source changes and your existing MCP configuration. Obtain
   the reviewed release in the same checkout; do not use a destructive Git reset.
3. In PowerShell at that checkout root, update its external virtual environment:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install --upgrade -e ".[test]"
   .\.venv\Scripts\python.exe -m pip check
   .\.venv\Scripts\python.exe -c "import cascadeur_mcp; from cascadeur_mcp.bridge.compatibility import describe; print(cascadeur_mcp.__version__); print(describe())"
   ```

   Expected a10 trial version: `0.5.0a10`; write-contract revision: `2`.
   These are local package checks, not a connection test.
4. A managed hook already pointing to this same `src` path does not need to be
   overwritten. Use `install-host` **without** `--apply` to inspect it, following
   [installation instructions](INSTALL_AND_DOCTOR.md). Preserve an unexpected or
   modified hook; `HOOK_CONFLICT` is not permission to force replacement.
5. Start Cascadeur normally with a disposable compatible scene, and reconnect the
   MCP server. The client must still launch this environment's Python executable.

## Verify the responding host before editing

Run `python -m cascadeur_mcp.manage doctor --live` with the configured environment
and instance. A successful read connection alone does not establish write readiness.

Through the MCP client, call `get_bridge_capabilities()` with `{}`. The responding
after a full matched a10 installation the host should report
`host.bridge_package_version: 0.5.0a10` and
`write_contract.revision: 2`; the full write contract must match the local one,
including its schema hash. Then use `get_scene_info()` and `list_characters()` to
rediscover current scene and character IDs. Do not reuse a previous session's
scene ID or in-memory snapshot ID.

`INCOMPATIBLE_HOST` or `INCOMPATIBLE_CLIENT` means one side still uses the wrong
contract. Check both configured source paths and restart both processes. Never
edit session descriptors or retry a failed write to bypass compatibility checks.

## Moving to another checkout or Python environment

Keep the old environment available. With Cascadeur closed, use that environment
and its original source path to preview and uninstall its exact managed hook.
Then use the new environment to preview and install the new hook. Update only the
relevant MCP configuration entry's Python path. The installer will not overwrite
another hook; see the exact-match commands in
[installation and diagnostics](INSTALL_AND_DOCTOR.md).

A wheel install places the package in that environment's `site-packages`; an
editable install points to checkout `src`. Do not remove or move the selected
directory while its hook is installed. Neither method requires installing the
external MCP SDK or a different Qt runtime inside Cascadeur.

## Recovery and reverting the package

On `outcome_unknown`, read back before any deliberate retry. On
`recovery_required`, stop editing. Reads, owned playback stop and a new quarantine
scene copy remain available; save-as does not clear the lock. A single-pose JSON
snapshot is not a whole-clip checkpoint. See
[recovery protection](CAPABILITIES_AND_ERRORS.md#scene-recovery-write-gate).

If reverting a package, normally stop both processes first and restore matching
client/host code and paths. Reverting to a8 also removes this new protection; it
does not repair an uncertain scene. Recover animation from a separately verified
checkpoint and read it back before editing.

Validation is limited to one developer machine. A fresh local Python environment
is not second-machine Cascadeur host validation. Native shutdown access violations
remain unresolved; this prerelease is not a production-stability guarantee.
