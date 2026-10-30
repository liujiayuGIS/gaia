#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  printf '%s\n' 'This installer currently targets macOS ARM64. Configure GIS_QGIS_PYTHON and an equivalent restricted runner on other hosts.'
  exit 1
fi
mkdir -p .runtime/bin
if [[ ! -x .runtime/bin/micromamba ]]; then
  curl --fail --location --retry 2 https://micro.mamba.pm/api/micromamba/osx-arm64/latest -o .runtime/micromamba.tar.bz2
  tar -xjf .runtime/micromamba.tar.bz2 -C .runtime bin/micromamba
fi
export MAMBA_ROOT_PREFIX="$PWD/.runtime/mamba"
.runtime/bin/micromamba create --no-rc --prefix "$PWD/.runtime/qgis" --channel conda-forge --strict-channel-priority --yes 'qgis=3.44.14' 'python=3.12' numpy scipy geopandas matplotlib
printf '%s\n' 'QGIS installed locally. Restart GAIA to discover the native Processing catalog.'
