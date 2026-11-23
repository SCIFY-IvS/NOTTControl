#!/usr/bin/env bash
# Average H2RG snake FOV dwells.
#
# Default: day presets + FITS SH1POS…SH4POS; average in groups of 5 frames/dwell.
#   --day 20260806 → frames 301–889
#   --day 20260807 → frames 51–last on disk
# Positions cube is background-subtracted (closest closed mean) unless --no-bg-sub.
#
# Usage:
#   ./nottcontrol/script/acquisition/average_snake_positions.sh --day 20260807
#   ./nottcontrol/script/acquisition/average_snake_positions.sh \
#       --day 20260807 --data-root "/Volumes/T7 Data/Data/nott"
#   ./nottcontrol/script/acquisition/average_snake_positions.sh --log my_plan.log
#
# Environment:
#   NOTT_DATA_ROOT   parent of YYYYMMDD folders (optional)

if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

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

exec "${PYTHON}" "${SCRIPT_DIR}/average_snake_positions.py" "$@"
