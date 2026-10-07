# API provenance and verification scope

## Semantic edit-impact reports (local verification, 2026-10-01)

Version `0.5.0a7` introduces no Cascadeur API. It derives Point movements
from the pre-edit targets already read by semantic offsets and native poses
already collected by `character.set_sequence` verification. RigInfo-validated
role/slot mapping supplies labels; no list index or guessed relationship is used.
Reports are built during both transaction checks; only the post-commit report is
returned. Existing whole-scene capture, curve checks and checked Undo remain.

Actual official-SDK calls on the local 23-frame Polished Cascy clip edited three
right-hand keys. Independent native reads checked all eleven semantic roles and
43 Point slots per requested frame. The report identified the unselected
right-elbow/forearm Point coupling. A private test observer deliberately failed
report generation on the second check, after native commit; checked native
rollback restored the entire captured clip and structure. A subsequent real
edit, continuous playback and restoration also succeeded. No vendor scene or
observer is included here. Unit tests alone do not establish these results.

This scope covers native Point world positions at edited frames, not Joint
rotations, every trajectory, visual quality, other machines or additional curve
modes. The report grouping threshold does not change existing safety tolerances.

The original adapters were developed against the official Cascadeur Python API,
the locally installed 2026.2.2 interfaces, and separate live tests. Installed
vendor modules/stubs and native character resources are not redistributed.
This document summarizes those development records; it is not a claim that
every current Cascadeur version has been tested.

| Adapter | Native interfaces / verified development scope |
|---|---|
| `host.py` | `csc.app.get_application`, current scene, model viewers; main-thread Qt timer |
| `animation.py` | Transform behavior data, Scene `modify_update`, data viewer/editor; existing-frame Joint edits |
| `skeleton.py` | Parent hierarchy, local/global Transform data and layer key guards; isolated FK subtree |
| `character.py`, `semantics.py` | RigInfo/RigAdditionalInfo relationships, Point global-position targets, native solve/readback; Cascy profile |
| `durable.py` | Original JSON format with integrity/identity guards; one-pose restore |
| `hands.py` | Validated finger parent chains and animated Transform.local_rotation, native data editor and updater; Cascy only |
| `playback.py` | Native `Timeline.Play` action, bounded frame observation and explicit stop verification |
| `polish.py` | Native layer keys/interpolation weights, scene-copy saving and bounded retiming; no arbitrary action execution |
| `fbx_export.py` | Application export entitlement and installed FbxLoader methods, scene-copy guard, full-range export |

Official references recorded during development:

- [Python API reference](https://cascadeur.com/python-api/)
- [Application](https://cascadeur.com/python-api/_generate/csc.app.Application.html)
- [Domain Scene](https://cascadeur.com/python-api/_generate/csc.domain.Scene.html)
- [Layers Editor](https://cascadeur.com/python-api/_generate/csc.layers.Editor.html)
- [Rotation](https://cascadeur.com/python-api/_generate/csc.math.Rotation.html)
- [Official joint editing example](https://cascadeur.com/help/category/215)

Source docstrings also retain the names of the original local phase discovery
reports. Those workstation reports and their raw scene evidence are deliberately
not included here. No vendor code is copied into this source distribution.

The automated suite checks input handling and adapter contracts, including an
explicitly synthetic semantic topology fixture. A passing suite does not certify
native solver behavior, licensing, visual fidelity, or production suitability.

## Hand channels and commit ordering (local verification, 2026-09-30)

The installed `ml/editable_animation.py` example's `SetPositions` path writes a
Local Rotation data node and runs the scene updater. The adapter uses the
existing `Rotation.from_quaternion`, data-editor writes and `run_update` APIs.
Actual Cascy tests established independent finger writes, both-hand batching,
body-state preservation, native Undo and save/reload. No installed vendor file
or character preset is copied here.

Actual full-state captures also showed that LayersEditor section edits can
finalize after a `Scene.modify_update` callback returns. The old journal captured
the pre-commit interpolation value. The adapter now repeats validation after
commit before recording history. Durable restore no longer resets all intervals
to Linear. Real restoration returned all 23 tested frames and tracks to their
recorded state; no tolerance or external-edit guard was relaxed.

## Selective semantic reads (local verification, 2026-09-30)

`get_semantic_pose` role selection reuses the verified RigInfo profile,
Transform behavior-data lookup and data-viewer reads above; no new vendor API
is assumed. The complete hierarchy, bindings and 43 Point controls remain
validated before selected Transform values are read. `character.get_pose`
defaults to full character reads for transaction and recovery callers.

Real official-SDK calls against Cascadeur 2026.2.2 checked all 23 stored frames:
default semantic values exactly matched the previous full-character projection,
and right-hand-only values exactly matched the corresponding full result.
A private delegating observer counted 11 Joint plus 43 Point Transform reads
for a full semantic request, and zero Joint plus three Point reads for
right-hand-only requests without joint state. One actual sequence write and
native Undo restored all 23 frames, with unchanged skeleton, tracks and
constraints. Original native scene files and the original startup hook were
restored/checked by SHA-256; no Computer Use was used.

These are local API and data-consistency checks. Reduced response bytes are
not measured Token savings or improved animation quality, and the observed MCP
latency did not materially change. The private native observer, scenes and logs
are not included in the source release.

## Batch semantic workflows (local verification, 2026-09-30)

The new batch read and relative edit introduce no new Cascadeur API assumptions.
They compose the same verified model/data-viewer frame reads, RigInfo profile,
Point global targets and checked `Scene.modify_update` sequence adapter above.
Mapping is reused only within a synchronous main-thread request. External
offsets and every computed absolute target are checked before native mutation.

Final real official-SDK acceptance on the local 23-frame Cascy scene established
exact batch/single read equality and three old/new edit comparisons under the
unchanged `character.equivalent` tolerance. Maximum observed raw edit/restore
difference was 0.0000610352; Undo is not claimed bit-exact. Six successful writes
restored all stored frames, tracks, topology and static constraints; an actual
unachievable target produced verified native rollback. Missing-frame and
computed-overflow preflight cases were independently checked across all frames.
All 447 final calls kept the user's foreground unchanged; original hook and
scene hashes were restored/checked after normal exit. No Computer Use was used.

Relative editing inherits complete character keys and LINEAR intervals from
the existing sequence engine, so it does not preserve authored easing curves.
Native solving can adjust targets. Smaller edited-role responses are projected
after full native verification, not substituted for it. Measured SDK workflow
time and bytes do not establish Token savings or better-looking animation.
Raw scenes, logs and the delegating observer remain private, excluded resources.

## Existing-key curve preservation (local verification, 2026-10-01)

The separate curve-preserving offset composes the previously verified Point
write/rig-update/transaction/interpolator APIs. It does not call a curve-authoring
API or create keys. The following additional reads have explicit installed sources:

| Read | Cascadeur 2026.2.2 installed declaration | Evidence |
|---|---|---|
| `csc.additive_layers.get_manager(scene).get_stacked_layers_count()` | `resources/scripts/stubs/csc/additive_layers.pyi`, Manager and get_manager | Actual tested scene reported zero; any stack is rejected, not serialized |
| `csc.layers.CyclesViewer(layer).any_cycles_exist_in_frames(0, count-1)` | `resources/scripts/stubs/csc/layers/__init__.pyi`, CyclesViewer | Actual complete-clip checks found no cycles; cycle writing is unsupported |
| interval interpolation/common/AI description, key label/common/tangent mode/weights | `resources/scripts/stubs/csc/layers/layer.pyi`, Interval, Key, Tangents | Actual full track metadata was identical before and after commit |

[Official Easing](https://cascadeur.com/help/category/317) separates temporal
spacing from path shape and includes Linear interpolation. Changing interpolation
to LINEAR does not itself prove all easing weights were cleared. The new operation
keeps those weights and the interpolation type exactly.
[Trajectory Tangents](https://cascadeur.com/help/category/287) has specific rig
and interpolation limits; no complete spatial tangent-vector recovery interface
was established. UserDefined tangents are therefore rejected throughout the scene.
[Additive Layers](https://cascadeur.com/help/category/318) are distinct from
animation tracks; this bridge does not claim its old capture stores their stack.

Local real official-MCP-SDK validation used an independent copy of the accepted
Polished Cascy clip with 23 stored frames and 13 tracks, including two FIXED baked
foot tracks. The same three-key hand correction changed two tracks with the
ordinary tool and zero with the preserving tool. Native write counts were 129
versus nine; maximum foot deviation from the source was 0.271669 versus 0.000643
scene units. Key/non-key and FIXED-track rejections were checked against actual
scene data. An unreachable native target produced verified full-state rollback.
Continuous native playback and native save were checked separately from tests.
The saved copy was opened in a fresh Cascadeur session: all 23 actual poses and
the complete skeleton/track metadata were equivalent, with another successful
native continuous playback. Original scene and hook hashes were unchanged after
normal closure. Validation used a non-active Windows desktop without Computer Use.

Actual solver coupling moved a forearm AdditionalPoint at an edited frame; its
Transform global_position shares the native ConnectionPointTwoBody target data
ID. This is why the tool protects authored Point keys outside requested frames
and allows checked solver adjustments inside them. No numeric tolerance was widened.
Local transforms, hidden velocity caches and driven Joint data are not falsely
classified as immutable authored input. Raw scenes, snapshots, local paths and
observer code remain excluded private validation resources.

## CLAMPED_BEZIER recovery restriction (0.5.0a8)

The `0.5.0a8` safety guard uses the same installed Interval interpolation read
above. `csc.layers.InterpolationType.CLAMPED_BEZIER` is enum value 6 in
`resources/scripts/stubs/csc/layers/layer.pyi`; no new Cascadeur call is added.
Local real BEZIER and LOW_AMPLITUDE_BEZIER fixtures passed edit/metadata/whole-clip
recovery checks. A CLAMPED_BEZIER fixture passed its write but failed checked
Undo recovery and correctly locked the journal. Its independent saved failure
copy was retained; the original scene was unchanged. The native cause is not
yet established. The guard refuses character Point/finger writes before capture
or mutation if any track contains that mode; it does not claim repaired Undo.
See [curve evidence and limits](docs/CURVE_PRESERVING_EDITING.md).

## Advisory preflight and checkpoint workflow (a11 candidate)

The a11 advisory preflight reuses the existing verified saved-scene identity,
Cascy semantic mapping, native track/section/IK-FK reads, curve preflight and
full-state capture listed above. It introduces no Cascadeur API call. Remaining
capacity comes from this host process's existing private snapshot/journal maps;
these are MCP bookkeeping, not a native Undo-capacity query. The checkpoint
workflow reuses the existing `view.save(path)` adapter and normal application startup; no restart,
open-scene, journal reset or license bypass API is exposed.

## Third-party code and attribution

The separate `ThatGuyTHD/animation-mcp` repository was reviewed locally for
animation workflow ideas. The reviewed checkout had no declared LICENSE, so its
source, assets and derived director skill are not included in this release.
Cascadeur MCP is not a repackaging of that repository.

The official MCP Python SDK and pytest are installed as dependencies through
`pyproject.toml`, not vendored into this repository. Their installed distributions
retain their own license notices. Python and Cascadeur must be installed
separately; this project's MIT license does not relicense them or their assets.

## Sampled motion and native boundaries (a12)

The sequence extension reuses the previously verified Point/data writes,
`scene.modify_update`, rig updater, interpolation, capture and guarded native
Undo APIs. It adds no executable input or body-Joint write API. All points and
frames are validated before mutation; the complete list is submitted to one
existing native transaction and its actual Point hashes are returned.

Newly exercised native properties are `csc.view.AnimationBoundary.first_frame`,
`last_frame`, `first_visible_frame`, `last_visible_frame`, obtained from
`csc.view.Scene.animation_boundary()`. Source: official installed Cascadeur
2026.2.2 stubs, `resources/scripts/stubs/csc/view/__init__.pyi`, AnimationBoundary
property declarations. Both setters and measured native playback were exercised
locally. Changing only the playback end left a 64-frame scene playing/updating
within its old 0–55 visible range; setting all four properties yielded measured
0–63 playback and checked full-state Undo restoration. This is local evidence,
not a guarantee for other Cascadeur versions or machines.

`get_character_skeleton(include_track_sections=false)` uses the same verified
hierarchy/binding/constraint/layer reads and removes only per-key section details
from its response. Track membership, key indices and the full skeleton remain.

## Persistent explicit recovery fence (a13)

`get_recovery_status` reuses the existing verified `character.capture` model/data,
setting, topology and captured track/section reads. It introduces no new Cascadeur
API call. Disk checksums, bounded JSON, request-scoped fencing and successful-write
acknowledgement are our own Python bookkeeping, not vendor API or native UI locks.

Local 2026-10-07 SDK/native tests injected one post-commit verification and Undo
failure after a real Point change. A new native process reopening the changed
quarantine rejected both a semantic offset and legacy timeline write; all 23
frames remained unchanged. A third process opened the verified pre-failure
checkpoint, matched complete recorded state, performed a normal offset and checked
snapshot restore. One of three native closes still crashed; this is not a shutdown
fix, automatic scene-opening API or coverage of all mid-write failures.
