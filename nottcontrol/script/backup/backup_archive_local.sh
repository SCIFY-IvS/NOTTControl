#!/usr/bin/env bash
# Pull nott-server /archive/nott onto a local computer.
#
# Default local destination: /Volumes/T7 Data/Data/nott
# Override with --dest or NOTT_BACKUP_DEST.
#
# Usage:
#   ./nottcontrol/script/backup/backup_archive_local.sh
#   ./nottcontrol/script/backup/backup_archive_local.sh --dry-run
#   ./nottcontrol/script/backup/backup_archive_local.sh --dest ~/Data/nott
#   ./nottcontrol/script/backup/backup_archive_local.sh --mode day
#   ./nottcontrol/script/backup/backup_archive_local.sh --mode day --day 20260805
#
# Requires GNU rsync (macOS openrsync is incompatible with nott-server):
#   brew install rsync
#
# Environment overrides:
#   NOTT_BACKUP_DEST    local folder (default: /Volumes/T7 Data/Data/nott)
#   NOTT_BACKUP_HOST    remote host (default: nott-server)
#   NOTT_BACKUP_USER    SSH user (default: labo)
#   NOTT_BACKUP_REMOTE  remote path (default: /archive/nott)
#   NOTT_BACKUP_RSYNC   path to GNU rsync binary

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

exec "${PYTHON}" "${SCRIPT_DIR}/backup_archive_local.py" "$@"
