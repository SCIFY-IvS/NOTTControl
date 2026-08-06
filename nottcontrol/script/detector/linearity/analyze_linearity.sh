#!/usr/bin/env bash
# H2RG detector linearity: dark-subtracted flux vs DIT.
#
# Default: frames 301–340 (shutter open) plus 341–350 (beamsplitter in)
# under today's UTC day folder.
# Data root resolution:
#   1) NOTT_DATA_ROOT, if set
#   2) /data/nott                       (nott-server)
#   3) /Volumes/T7 Data/Data/nott       (local backup mirror)
#
# Usage:
#   ./nottcontrol/script/detector/linearity/analyze_linearity.sh
#   ./nottcontrol/script/detector/linearity/analyze_linearity.sh --day 20260806
#   ./nottcontrol/script/detector/linearity/analyze_linearity.sh --data-dir "/Volumes/T7 Data/Data/nott/20260806"
#   ./nottcontrol/script/detector/linearity/analyze_linearity.sh --show
#
# Environment:
#   NOTT_DATA_ROOT   parent of YYYYMMDD folders (optional override)

if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

cd "${REPO_ROOT}"
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  PYTHON="${VIRTUAL_ENV}/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  echo "error: python3 not found" >&2
  exit 1
fi

exec "${PYTHON}" "${SCRIPT_DIR}/analyze_linearity.py" "$@"
