#!/usr/bin/env bash
# Fetch cryostat temperature TimeSeries from NOTT Redis and plot them.
#
# Usage:
#   ./nottcontrol/script/monitoring/plot_cryo_temps.sh
#   ./nottcontrol/script/monitoring/plot_cryo_temps.sh --sensor-names t_shield_1 t_shield_2
#   ./nottcontrol/script/monitoring/plot_cryo_temps.sh --keys "ns=4;s=MAIN.nott_cryo_ctrl.nott_temp.t_base_plate_1.stat.lrTempK"
#
# Environment:
#   NOTT_REDIS_URL  override Redis URL (default: nottcontrol/config.ini)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

cd "${REPO_ROOT}"

if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  PYTHON="${VIRTUAL_ENV}/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  echo "error: python3 not found" >&2
  exit 1
fi

exec "${PYTHON}" "${SCRIPT_DIR}/plot_cryo_temps.py" "$@"
