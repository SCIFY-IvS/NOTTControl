#!/usr/bin/env bash
# Average H2RG snake FOV dwells (5 frames/position).
#
# Default log: snake_20260806.log (301–889, alternating close/open).
# Positions cube is background-subtracted (closest closed mean) unless --no-bg-sub.
#
# Usage:
#   ./nottcontrol/script/acquisition/average_snake_positions.sh --day 20260806
#   ./nottcontrol/script/acquisition/average_snake_positions.sh \
#       --day 20260806 --data-root "/Volumes/T7 Data/Data/nott"
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

EXTRA=()
# Use bundled log unless the caller already passed --log.
has_log=0
for arg in "$@"; do
  if [[ "${arg}" == "--log" || "${arg}" == --log=* ]]; then
    has_log=1
    break
  fi
done
if [[ "${has_log}" -eq 0 && -f "${SCRIPT_DIR}/snake_20260806.log" ]]; then
  EXTRA+=(--log "${SCRIPT_DIR}/snake_20260806.log")
fi

exec "${PYTHON}" "${SCRIPT_DIR}/average_snake_positions.py" "${EXTRA[@]}" "$@"
