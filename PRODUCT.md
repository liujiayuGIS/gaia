# GAIA — Geospatial Artificial Intelligence Assistant

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The user is building and personally evaluating a local GIS analysis and cartography workbench, with professional GIS workflows and a prominent persistent natural-language assistant.

## Product Purpose

Import real geographic data, analyze it with natural language or parameter forms, publish independent results as layers, edit print layouts, save reusable projects/templates and export actual data and maps.

## Operating Context

Local macOS application at 127.0.0.1:8765. React/MapLibre frontend and FastAPI backend. Real Census Washington county boundaries and USGS Mount Rainier elevation are available for acceptance.

## Capabilities and Constraints

The harness understands tasks, selects SKILL.md procedures, plans workflows and invokes execution plugins. QGIS is the first native GIS plugin; Python provides scientific and custom-code jobs. User-authored or generated code runs in separate managed processes. Input files, native projects, print layouts, templates, code recipes and execution records are reusable workspace resources.
QGIS runtime 3.44.14 and its actual Processing catalog have been installed locally. Full equivalence with ArcGIS Pro and all third-party applications has not been established. Cloud/multi-user deployment remains undecided.

## Brand Commitments

The user named the app GAIA, Geospatial Artificial Intelligence Assistant, 地理空间人工智能助手·盖亚, and supplied the unchanged orbital G icon. Latest steering supersedes the earlier ArcGIS Pro imitation: retain the concentrated data–map–assistant arrangement, give the assistant a permanent separate right column, express an original identity with rounded controls and borders, and selectively use iOS-like segmented controls. Familiar GIS parameter semantics matter; copying vendor ribbon placement and adding unnecessary commands does not. User asks to refer to open-source GIS workbench patterns such as Kepler.gl/OpenGIS without reproducing their identity.

## Product Principles

- Keep the map or document central; navigation and tools serve the current task.
- Skills describe methods; plugins execute capabilities; the harness orchestrates and validates.
- Manual editing and language commands update the same saved layout.
- Show real runtime capability and actual artifacts; never invent unavailable functions or results.
- Preserve source data and record inputs, parameters, code/version hashes and output provenance.
