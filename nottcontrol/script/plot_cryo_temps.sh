#!/usr/bin/env bash
# Fetch cryostat temperature TimeSeries from NOTT Redis and plot them.
#
# Usage:
#   ./nottcontrol/script/plot_cryo_temps.sh
#   ./nottcontrol/script/plot_cryo_temps.sh --show
#   ./nottcontrol/script/plot_cryo_temps.sh -o /tmp/cryo.png
#
# Environment:
#   NOTT_REDIS_URL  override Redis URL (default: nottcontrol/config.ini)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${REPO_ROOT}"

if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  PYTHON="${VIRTUAL_ENV}/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  echo "error: python3 not found" >&2
  exit 1
fi

exec "${PYTHON}" -m nottcontrol.script.plot_cryo_temps "$@"
