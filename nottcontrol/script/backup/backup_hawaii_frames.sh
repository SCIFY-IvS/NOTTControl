#!/usr/bin/env bash
# Backup live H2RG data to permanent archive, then apply 1-week retention on /data.
#
# Copies (archive is never deleted by this script):
#   /data/nott       → /archive/nott
#   /data/bench_data → /archive/bench_data
#
# After a successful copy, removes from /data only what is already in /archive
# and older than --retention-days (default: 7).
#
# Usage:
#   ./nottcontrol/script/backup/backup_hawaii_frames.sh
#   ./nottcontrol/script/backup/backup_hawaii_frames.sh --dry-run
#   ./nottcontrol/script/backup/backup_hawaii_frames.sh --no-purge
#   ./nottcontrol/script/backup/backup_hawaii_frames.sh --purge-only --dry-run
#   ./nottcontrol/script/backup/backup_hawaii_frames.sh --skip-bench
#   ./nottcontrol/script/backup/backup_hawaii_frames.sh --mode day --day 20260805
#
# Cron example (daily full incremental + retention at 04:15 UTC):
#   15 4 * * * /home/labo/src/NOTTControl/nottcontrol/script/backup/backup_hawaii_frames.sh >> /archive/nott/cron.log 2>&1
#
# Cron does not load conda. The wrapper prefers ~/miniconda3 (or
# ~/anaconda3 / REPO/.venv). Or pin it in crontab:
#   15 4 * * * /home/labo/miniconda3/bin/python /home/labo/src/NOTTControl/nottcontrol/script/backup/backup_hawaii_frames.py >> /archive/nott/cron.log 2>&1

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

exec "${PYTHON}" "${SCRIPT_DIR}/backup_hawaii_frames.py" "$@"
