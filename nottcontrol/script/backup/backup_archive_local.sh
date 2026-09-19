#!/usr/bin/env bash
# Pull nott-server archives onto a local computer.
#
# By default syncs two trees (permanent archives on nott-server):
#   /archive/nott        → /Volumes/T7 Data/Data/nott
#   /archive/bench_data  → /Volumes/T7 Data/Data/bench_data   (MSAC / H2RG_ASIC)
#
# Override destinations with --dest / --bench-dest or env vars below.
#
# Usage:
#   ./nottcontrol/script/backup/backup_archive_local.sh
#   ./nottcontrol/script/backup/backup_archive_local.sh --dry-run
#   ./nottcontrol/script/backup/backup_archive_local.sh --dest ~/Data/nott
#   ./nottcontrol/script/backup/backup_archive_local.sh --skip-bench
#   ./nottcontrol/script/backup/backup_archive_local.sh --bench-only
#   ./nottcontrol/script/backup/backup_archive_local.sh --mode day
#   ./nottcontrol/script/backup/backup_archive_local.sh --mode day --day 20260805
#
# Requires GNU rsync (macOS openrsync is incompatible with nott-server):
#   brew install rsync
#
# Environment overrides:
#   NOTT_BACKUP_DEST          local /archive/nott folder
#   NOTT_BACKUP_BENCH_DEST    local /data/bench_data folder
#   NOTT_BACKUP_HOST          remote host (default: nott-server)
#   NOTT_BACKUP_USER          SSH user (default: labo)
#   NOTT_BACKUP_REMOTE        remote /archive/nott (default: /archive/nott)
#   NOTT_BACKUP_BENCH_REMOTE  remote bench archive (default: /archive/bench_data)
#   NOTT_BACKUP_RSYNC         path to GNU rsync binary

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
