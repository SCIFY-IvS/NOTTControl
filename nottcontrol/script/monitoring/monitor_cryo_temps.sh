#!/usr/bin/env bash
# Monitor cryostat vote temperatures (three panels, 24 h default).
#
# Default output (UTC timestamp inserted before .png):
#   nottcontrol/script/monitoring/cryo_monitor_YYYYMMDD_HHMMSS.png
#
# Redis keys are OPC UA node ids from nottcontrol/sensors.ini.
#
# Usage:
#   ./nottcontrol/script/monitoring/monitor_cryo_temps.sh
#   ./nottcontrol/script/monitoring/monitor_cryo_temps.sh -o /tmp/cryo_monitor.png
#     → saves /tmp/cryo_monitor_YYYYMMDD_HHMMSS.png
#   ./nottcontrol/script/monitoring/monitor_cryo_temps.sh --hours 48
#   ./nottcontrol/script/monitoring/monitor_cryo_temps.sh --hours 12 --show
#
# Environment:
#   NOTT_REDIS_URL  override Redis URL (default: nottcontrol/config.ini)

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

exec "${PYTHON}" "${SCRIPT_DIR}/monitor_cryo_temps.py" "$@"
