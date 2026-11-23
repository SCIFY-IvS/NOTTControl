#!/usr/bin/env bash
# Trigger one acquire via the open H2RG GUI (preferred) or zmq_server.
# Stop Live in the GUI first.
#
#   ./nottcontrol/camera/macie/acquire_once.sh
#   ./nottcontrol/camera/macie/acquire_once.sh --gui-only
#   ./nottcontrol/camera/macie/acquire_once.sh --zmq-only

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

exec "${PYTHON}" "${SCRIPT_DIR}/acquire_once.py" "$@"
