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

## Leaflet 1.9.4

Source: https://github.com/Leaflet/Leaflet/tree/v1.9.4

BSD 2-Clause License

Copyright (c) 2010-2023, Volodymyr Agafonkin
Copyright (c) 2010-2011, CloudMade
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
