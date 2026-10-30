# GAIA v0.3 verification

2026-10-31, macOS ARM64. Runtime tests use real native QGIS 3.44.14-Solothurn, not mocks.

- 88 standard tests pass, one native integration test intentionally skipped in the portable run (`GEOAGENT_DISABLE_QGIS=1`).
- Native suite: 8 tests pass including one combined real integration test. QGIS metre-projected 100 m buffer area agrees with πr² to 0.2%; output retains native provenance. Python sandbox denies reads of an existing canary, external writes and a socket connection, and does not inherit a dummy API key. Native layout numerical edits are reflected in scene geometry; PDF, project reopen and saved-QPT rendering pass.
- Real public Census SHP and USGS DEM generate native PNG/PDF/SVG and complete QGIS project ZIPs. Additional native JPEG and TIFF smoke checks open with the expected format and A4 dimensions. PDF exports were independently rasterized with Poppler and visually checked. The USGS request is AOI resampled (~33.84 m), not a native-resolution survey product; source stitching/banding is retained rather than silently altering elevation data.
- Actual Chrome UI test: independently persistent assistant, native centroid form produces a new layer, theme/accent survives reload, native legend has nonzero bounds, element drag/text/position save, native dialog Escape works, 390px layout/tool/assistant navigation has no document overflow or JS exceptions.
- Design detector returned no findings before the user-directed GAIA identity revision. A fresh independent design review matched the revised GAIA direction; two form grouping fixes and dark-theme error contrast were scored resolved with a ship verdict. See `.impeccable/review/` for evidence.

Commands:

```bash
PYTHONPATH=backend GEOAGENT_DISABLE_QGIS=1 .venv/bin/python -m pytest -q
PYTHONPATH=backend GEOAGENT_NATIVE_TESTS=1 .venv/bin/python -m pytest -q backend/tests/test_plugins.py
npm run build --prefix frontend
PLAYWRIGHT_MODULE=/path/to/playwright CHROME_PATH=/path/to/Chrome BASE_URL=http://127.0.0.1:8767 node scripts/gaia-ui-test.cjs
```

No paid model request was made for this UI iteration. Earlier Responses adapter tests cover reasoning-item and function-output round trips; this does not measure an online model's GIS task success rate. The catalog count describes discovered algorithms, not comprehensive correctness evaluation. No QGIS/ArcGIS parity or advantage over other agents is established.
