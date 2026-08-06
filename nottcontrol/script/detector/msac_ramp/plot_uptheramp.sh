#!/usr/bin/env bash
# Plot illuminated-region ADU along MSAC UpTheRamp FITS cubes.
#
# Default root: ~/frames/H2RG_ASIC/UpTheRamp/
# The script uses the latest subdirectory under that root (session folder).
#
# Usage (on the acquisition machine):
#   ./nottcontrol/script/detector/msac_ramp/plot_uptheramp.sh
#   ./nottcontrol/script/detector/msac_ramp/plot_uptheramp.sh --latest 3
#   ./nottcontrol/script/detector/msac_ramp/plot_uptheramp.sh --all --show-pixels
#   ./nottcontrol/script/detector/msac_ramp/plot_uptheramp.sh --file myramp.fits --show
#
# Environment:
#   MSAC_RAMP_DIR   override UpTheRamp root (or a specific session folder)

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

EXTRA=()
if [[ -n "${MSAC_RAMP_DIR:-}" ]]; then
  EXTRA+=(--ramp-dir "${MSAC_RAMP_DIR}")
fi

exec "${PYTHON}" "${SCRIPT_DIR}/plot_uptheramp.py" "${EXTRA[@]}" "$@"
