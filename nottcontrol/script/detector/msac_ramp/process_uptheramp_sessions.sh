#!/usr/bin/env bash
# Cron wrapper: run UpTheRamp flux + QA plots for every pending session folder.
#
# Default root: /data/bench_data/H2RG_ASIC/UpTheRamp/
# Skips sessions that already have up-to-date
#   {session}_msac_uptheramp_illum_vs_file.png
#   {session}_msac_qa_ramp.png
# (re-runs if source FITS are newer).
#
# Usage:
#   ./nottcontrol/script/detector/msac_ramp/process_uptheramp_sessions.sh
#   ./nottcontrol/script/detector/msac_ramp/process_uptheramp_sessions.sh --dry-run
#   ./nottcontrol/script/detector/msac_ramp/process_uptheramp_sessions.sh --force
#   ./nottcontrol/script/detector/msac_ramp/process_uptheramp_sessions.sh --limit 5
#
# Environment:
#   MSAC_RAMP_ROOT   override session parent (same as --root)
#
# Cron example (every 30 minutes):
#   */30 * * * * /home/labo/src/NOTTControl/nottcontrol/script/detector/msac_ramp/process_uptheramp_sessions.sh >> /archive/bench_data/uptheramp_qa_cron.log 2>&1
#
# Cron does not load conda. This wrapper prefers ~/miniconda3 (or
# ~/anaconda3 / REPO/.venv), same as the Hawaii backup scripts.

if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

cd "${REPO_ROOT}"
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
# Headless matplotlib (cron has no display).
export MPLBACKEND=Agg

if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  PYTHON="${VIRTUAL_ENV}/bin/python"
elif [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/bin/python" ]]; then
  PYTHON="${CONDA_PREFIX}/bin/python"
elif [[ -x "${HOME}/miniconda3/bin/python" ]]; then
  PYTHON="${HOME}/miniconda3/bin/python"
elif [[ -x "${HOME}/anaconda3/bin/python" ]]; then
  PYTHON="${HOME}/anaconda3/bin/python"
elif [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
  PYTHON="${REPO_ROOT}/.venv/bin/python"
elif [[ -x "${REPO_ROOT}/venv/bin/python" ]]; then
  PYTHON="${REPO_ROOT}/venv/bin/python"
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

exec "${PYTHON}" "${SCRIPT_DIR}/process_uptheramp_sessions.py" "${EXTRA[@]}" "$@"
