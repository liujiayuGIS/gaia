# Third-party components in GAIA desktop

GAIA desktop bundles unmodified third-party runtimes. The application's source
repository visibility and licensing do not replace the licenses of these components.

- Electron / Chromium / Node.js: license files are distributed in the application
  bundle by Electron and electron-builder. Sources: https://github.com/electron/electron
- QGIS: GPL-2.0-or-later (including applicable bundled components), source and release
  archives: https://qgis.org/download/ ; https://github.com/qgis/QGIS
- QGIS runtime packaging recipes: https://github.com/conda-forge/qgis-feedstock
- GDAL, PROJ, GEOS, Qt, Python, and the scientific stack retain their respective
  licenses; see the package-specific notices and source/recipe references bundled
  under resources/runtime/licenses.
- conda-pack: BSD-3-Clause, https://github.com/conda/conda-pack
- Electron desktop dependencies: MIT / ISC and their package-specific license files.

The build collects conda package names, versions, build identifiers, upstream package
URLs, license metadata, available license files and recipes. It also records pip
package versions and their distributed license texts. These files accompany the
runtime in each installer; no user data, API keys, or local project workspaces are
included. Redistributors should preserve these notices and supply corresponding
source as required by each component's license.
