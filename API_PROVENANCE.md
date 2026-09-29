# API provenance and verification scope

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

## Third-party code and attribution

The separate `ThatGuyTHD/animation-mcp` repository was reviewed locally for
animation workflow ideas. The reviewed checkout had no declared LICENSE, so its
source, assets and derived director skill are not included in this release.
Cascadeur MCP is not a repackaging of that repository.

The official MCP Python SDK and pytest are installed as dependencies through
`pyproject.toml`, not vendored into this repository. Their installed distributions
retain their own license notices. Python and Cascadeur must be installed
separately; this project's MIT license does not relicense them or their assets.
