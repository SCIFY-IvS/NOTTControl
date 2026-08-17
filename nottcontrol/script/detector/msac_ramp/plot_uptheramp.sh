#!/usr/bin/env bash
# Plot illuminated-region ADU along MSAC UpTheRamp FITS cubes.
#
# Default root: ~/frames/H2RG_ASIC/UpTheRamp/
# The script uses the latest subdirectory under that root (session folder).
#
# Default illuminated region: Photonic chip WinMode (X=1024–1087, Y=928–959)
# Flux = mean of the 10 brightest pixels after outlier rejection.
# No background ROI is subtracted. Override the box with --illum-roi /
# --illum-center / --illum-size.
#
# Builds reduced cubes next to the PNG plot:
#   frame − reset  when a _R0001 (or _R######) FITS is in the session folder
#   frame − first  otherwise (zero self-subtraction plane omitted)
#   msac_uptheramp_frame_minus_first.fits       — full frame
#   msac_uptheramp_frame_minus_first_illum.fits — illuminated-box crop
#
# Usage (on the acquisition machine):
#   ./nottcontrol/script/detector/msac_ramp/plot_uptheramp.sh
#   ./nottcontrol/script/detector/msac_ramp/plot_uptheramp.sh --latest 10
#   ./nottcontrol/script/detector/msac_ramp/plot_uptheramp.sh --show-pixels
#   ./nottcontrol/script/detector/msac_ramp/plot_uptheramp.sh --no-reset
#
# Default: all science FITS in the latest UpTheRamp session folder
# (reset frames _R###### are used as the subtraction reference, not as
# ramp points).
# X = file index from the name (_M###### or _N######);
# Y = mean of 10 photonic-chip pixels chosen on the last CDS plane
#     (outliers rejected), then tracked on every sample.
#
# PNG (flux plot + detector QA of reset and ramp) and FITS cubes
# are written into the session data folder:
#   msac_qa_reset.png / msac_qa_ramp.png
#   msac_qa_slope.fits / msac_qa_resid_rms.fits
# Skip QA with --no-qa.
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
