#!/usr/bin/env bash
# Plot illuminated-region ADU along MSAC UpTheRamp FITS cubes.
#
# Default root: ~/frames/H2RG_ASIC/UpTheRamp/
# The script uses the latest subdirectory under that root (session folder).
#
# Default illuminated region: [H2RG DETECTOR] ROI 2
# Default background / reference: ROI 8 (pedestal subtracted per plane)
# Override with --illum-roi / --bg-roi / --illum-center / --illum-size;
# disable pedestal with --no-bg-roi.
#
# Builds CDS-relative cubes (each plane = frame - first; first zero plane
# omitted; optional ROI-8 pedestal) next to the PNG plot:
#   msac_uptheramp_frame_minus_first.fits       — full frame
#   msac_uptheramp_frame_minus_first_illum.fits — illuminated-box crop
#
# Usage (on the acquisition machine):
#   ./nottcontrol/script/detector/msac_ramp/plot_uptheramp.sh
#   ./nottcontrol/script/detector/msac_ramp/plot_uptheramp.sh --latest 10
#   ./nottcontrol/script/detector/msac_ramp/plot_uptheramp.sh --show-pixels
#
# Default: all FITS in the latest UpTheRamp session folder.
# X = file index from the name (_M###### or _N######);
# Y = illuminated mean − background ROI (frame − first).
#
# PNG (full frame + illuminated crop + flux vs frame) and FITS cubes
# are written into the session data folder.
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
