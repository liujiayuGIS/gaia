# GAIA v0.4 verification

2026-10-31 · macOS ARM64 · Python 3.12 · native QGIS 3.44.14-Solothurn.

## Results

- Portable suite: **102 passed, 2 native tests skipped**. The existing 88 tests remain covered. New cases cover session isolation/context, explicit preferences, checkpoint secrets, approval acceptance/refusal/restart, stale approval IDs, changed input files, unmet output requirements, missing exports, empty layers, Chinese knowledge retrieval/invalidation, recipe verification/review and workflow recovery.
- A real child process is killed with `os._exit(23)` after a GIS tool receipt and before the graph node commits. A second Python process resumes the same task: the completed buffer is reused and the layer count stays at two (one input, one result).
- A separate fault injects a crash after publication but before the tool receipt. Recovery pauses for explicit review; rejecting the retry produces no duplicate layer.
- A two-node workflow fails at the second node, then resumes. The first algorithm executes once; the failed second node retries, and there remains one workflow receipt.
- Native plugin suite: **8 passed**, including real Seatbelt isolation, projected buffer geometry, native layout/PDF, QGZ reopen and QPT rendering.
- New native durable-harness test: **passed**. A real QGIS 100 m buffer is published through the new runner, checks EPSG:32610, fields and feature count, and independently agrees with πr² within 0.1%.
- Browser checks: session persistence after reload, new-session isolation, switching history, preference and knowledge writes, approval after a page reload, exactly one real Python output after authorization, executable recipe verification/promotion and 390 px no-overflow. No page JavaScript exceptions.
- Production frontend build and `pip check` pass. Vite retains the existing large bundle warning; no layout redesign was made.

The browser's model provider is deterministic and isolated in `scripts/qa_harness_server.py`; GIS and sandbox code execution are real. No paid provider request was made. Tests do not establish an online model's GIS success rate, universal research correctness, automatic visual review, or parity with all desktop GIS functionality.

## Reproduce

```bash
GEOAGENT_DISABLE_QGIS=1 GEOAGENT_WORKSPACE=/tmp/gaia-test-default .venv/bin/python -m pytest -q
GEOAGENT_NATIVE_TESTS=1 .venv/bin/python -m pytest backend/tests/test_plugins.py -q
GEOAGENT_NATIVE_TESTS=1 .venv/bin/python -m pytest backend/tests/test_durable.py::test_native_qgis_through_durable_harness_and_acceptance -q
npm run build --prefix frontend
.venv/bin/python scripts/qa_harness_server.py
# In another terminal, with Playwright and Chrome available:
PLAYWRIGHT_MODULE=/path/to/playwright CHROME_PATH=/path/to/Chrome node scripts/harness-ui-test.cjs
```

Browser evidence is generated under ignored `outputs/harness-v04/`. QA uses a separate `/private/tmp/gaia-v04-browser-workspace`, never the user's default workspace. Native Seatbelt tests must run outside an enclosing sandbox that prohibits creating another OS sandbox; GAIA's own code restrictions remain enabled.

## Acceptance boundaries

Restore means resuming at model/tool/workflow boundaries, not restoring the middle of a native raster process. The crash window around non-transactional plugin outputs is surfaced for review, not claimed to be exactly-once. Old v0.3 runs are viewable but lack recoverable checkpoints. Knowledge retrieval currently uses SQLite FTS5; no embedding service is enabled. Map/scientific correctness beyond the declared checks still requires domain and visual review.
