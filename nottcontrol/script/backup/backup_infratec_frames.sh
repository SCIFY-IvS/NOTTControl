#!/usr/bin/env bash
# Daily backup of SCIFY infratec frames: /frames -> /archive/infratec
#
# Default behaviour: incremental rsync of the full frame tree.
#
# Usage:
#   ./nottcontrol/script/backup/backup_infratec_frames.sh
#   ./nottcontrol/script/backup/backup_infratec_frames.sh --dry-run
#   ./nottcontrol/script/backup/backup_infratec_frames.sh --mode day
#   ./nottcontrol/script/backup/backup_infratec_frames.sh --mode day --day 20260715
#
# Cron example (daily at 03:00 UTC, previous UTC day only):
#   0 3 * * * /home/labo/src/NOTTControl/nottcontrol/script/backup/backup_infratec_frames.sh --mode day >> /archive/infratec/cron.log 2>&1
#
# Cron example (daily full incremental mirror at 04:00 UTC):
#   0 4 * * * /home/labo/src/NOTTControl/nottcontrol/script/backup/backup_infratec_frames.sh >> /archive/infratec/cron.log 2>&1
#
# Cron does not load conda. The wrapper prefers ~/miniconda3 (or
# ~/anaconda3 / REPO/.venv). Or pin it in crontab:
#   0 4 * * * /home/labo/miniconda3/bin/python /home/labo/src/NOTTControl/nottcontrol/script/backup/backup_infratec_frames.py >> /archive/infratec/cron.log 2>&1

# Re-exec under bash when invoked as `sh script.sh` (dash has no pipefail).
if [ -z "${BASH_VERSION:-}" ]; then
  exec bash "$0" "$@"
fi

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

cd "${REPO_ROOT}"
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"

# Cron has a minimal env (no conda/venv on PATH). Prefer the same
# interpreter interactive labo uses (conda base, then project venv).
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

exec "${PYTHON}" "${SCRIPT_DIR}/backup_infratec_frames.py" "$@"
