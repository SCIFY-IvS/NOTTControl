#!/usr/bin/env bash
# Scan MSAC UpTheRamp session folders for valid ramp acquisitions.
#
# Ranks each session subdirectory by whether illuminated flux (photonic chip,
# same logic as plot_uptheramp.sh) increases with ramp file index.
#
# Default root: /data/bench_data/H2RG_ASIC/UpTheRamp/
#
# Usage:
#   ./nottcontrol/script/detector/msac_ramp/scan_uptheramp_sessions.sh
#   ./nottcontrol/script/detector/msac_ramp/scan_uptheramp_sessions.sh --good-only
#   ./nottcontrol/script/detector/msac_ramp/scan_uptheramp_sessions.sh --top 5
#   ./nottcontrol/script/detector/msac_ramp/scan_uptheramp_sessions.sh \\
#       --root ~/frames/H2RG_ASIC/UpTheRamp --csv /tmp/ramp_scan.csv
#
# Environment:
#   MSAC_RAMP_ROOT   override UpTheRamp root (same as --root)

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
if [[ -n "${MSAC_RAMP_ROOT:-}" ]]; then
  EXTRA+=(--root "${MSAC_RAMP_ROOT}")
fi

exec "${PYTHON}" "${SCRIPT_DIR}/scan_uptheramp_sessions.py" "${EXTRA[@]}" "$@"
