#!/usr/bin/env bash
# Daily backup of H2RG / Hawaii FITS frames: /data/nott -> /archive/hawaii
#
# Default behaviour: incremental rsync of the full FITS tree.
#
# Usage:
#   ./nottcontrol/script/backup/backup_hawaii_frames.sh
#   ./nottcontrol/script/backup/backup_hawaii_frames.sh --dry-run
#   ./nottcontrol/script/backup/backup_hawaii_frames.sh --mode day
#   ./nottcontrol/script/backup/backup_hawaii_frames.sh --mode day --day 20260805
#
# Cron example (daily at 03:15 UTC, previous UTC day only):
#   15 3 * * * /home/labo/src/NOTTControl/nottcontrol/script/backup/backup_hawaii_frames.sh --mode day >> /archive/hawaii/cron.log 2>&1
#
# Cron example (daily full incremental mirror at 04:15 UTC):
#   15 4 * * * /home/labo/src/NOTTControl/nottcontrol/script/backup/backup_hawaii_frames.sh >> /archive/hawaii/cron.log 2>&1

# Re-exec under bash when invoked as `sh script.sh` (dash has no pipefail).
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

exec "${PYTHON}" "${SCRIPT_DIR}/backup_hawaii_frames.py" "$@"
