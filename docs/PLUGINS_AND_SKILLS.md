# GAIA harness / plugin / Skill architecture

The harness interprets language, loads relevant procedures, plans and invokes tools. It never fabricates plugin availability. Execution providers own analysis, printing, projects and custom code. The browser uses the same tools through parameter forms and a permanent assistant.

## Installed providers in this development environment

- QGIS 3.44.14-Solothurn: 440 algorithms discovered from the real Processing registry, native parameter definitions, GDAL/native tools, PyQGIS code, QgsPrintLayout export, QGZ/QPT/QML and data bundles.
- Python: 35 existing deterministic GIS operations plus GeoPandas/Rasterio/NumPy code and Python cartography.

These are available catalog entries, not 475 independently validated implementations. External executables and complex parameter types may require additional runtime support; optional PDAL dependencies in this environment are incomplete. Common native geometry and terrain operations have actual execution evidence. No ArcPy runtime, full ArcGIS parity, or benchmark superiority is claimed.

## Provider SDK

`backend/geoagent/plugins/base.py` defines contract version 1. A provider exposes `id`, `name`, `status()`, `algorithms()` and `execute(store, qualified_id, arguments, run_id, cancel)`. Optional operations implement `render`, `execute_code`, `save_project`, `open_project`, `save_template` and `scene`. Declare actual operations and health in `status()`.

Algorithms have qualified IDs such as `qgis:native:buffer`. Metadata supplies input names/types/defaults/choices; the host binds layer IDs to immutable native input snapshots. QGIS performs its own parameter validation. Distances in native QGIS tools follow the algorithm/input CRS: a geographic CRS can mean degrees. The harness must check and, when needed, explicitly reproject before a metre-distance analysis.

Host-owned extensions may call `plugins.manager.register(id, factory)`. Installed packages can declare a `geoagent.plugins` Python entry point. Discovery does not import arbitrary packages; activation is explicit. Providers are trusted installed host code, not untrusted user Skills. The bundled native runner isolates execution processes. New providers must uphold equivalent execution and provenance contracts.

## Skills

Built-in packages live in `skills/<name>/SKILL.md`. The UI installs Markdown or a ZIP containing one SKILL.md into workspace-local `skills/`. YAML metadata requires `name` and `description`, optionally `version` and `required_plugins`. The harness lists metadata, then reads a relevant procedure/resources as needed, recording its SHA256. Packages are capped at 5 MB, resource reads at 200 KB, and traversal/symlinks are rejected.

Skills are procedural context. They do not grant filesystem, network or host installation privileges. Required plugin metadata is advisory and the execution registry still validates every call.

## Custom algorithms

The code pane and `execute_code` accept `plugin_id=python|qgis`, code, and input alias→layer-ID bindings. Python inputs are GeoDataFrames/Rasterio datasets; PyQGIS inputs are QgsMapLayers with `processing`, `context` and `feedback`. Write actual files under `output_dir`; set `outputs={name: path}` and optional `metrics={...}`. Geodata outputs become new layers and artifacts; other files remain downloadable. Save a name to retain a draft recipe. In v0.4, verify it against executable acceptance conditions, review the code/artifacts, then explicitly promote it into a typed tool. See [durable harness and memory](HARNESS_V04.md).

Jobs copy declared inputs into an isolated directory, strip inherited API secrets, enforce time/log/file-size limits, kill the process group on cancellation and record code hashes/input hashes. The current restricted runner uses macOS Seatbelt: explicit runtime reads, job-only writes and denied network. Other operating systems require an equivalent restricted runner; they do not silently execute custom code without a sandbox.

## Native cartography

The editable scene exposes real QGIS items with millimetre geometry and per-item images. Edits update the same specification passed to the QGIS exporter and saved project. First-paint layout resolves legend/scale geometry before extracting the scene. PDF/SVG/PNG/JPEG/TIFF exports save artifacts; QGIS projects bundle relative paths and data. A standalone QGZ needs its accompanying data; use the ZIP to move to another computer.

Saved templates support bindings in the tool/API. The UI currently applies templates against existing workspace bindings. Imported arbitrary external QGZ/QPT, Atlas, 3D editing and full QGIS desktop interaction are future work. MapLibre is the interactive preview; QGIS is the canonical native print renderer.
