#!/usr/bin/env python3
"""Monitor base plate and shield cryostat temperatures from Redis TimeSeries.

Uses OPC UA node id keys from sensors.ini (see cursor/sensor-readout-redis-keys).
Fits a sum-of-exponentials model to the last 12 hours of base plate and shield
data. Detector temperature is plotted as raw data only (no fit).
"""

from __future__ import annotations

import argparse
import os
import sys

from nottcontrol import config, sensor_config_path

from plot_cryo_temps import (
    DEFAULT_FIT_MAX_POINTS,
    DEFAULT_MONITOR_TARGET_K,
    DEFAULT_PLOT_MAX_POINTS,
    MONITOR_SENSOR_GROUPS,
    plot_cryo_monitor,
)

DEFAULT_HOURS = 12.0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Monitor base plate, shield, and detector cryostat temperatures "
            "(OPC UA TimeSeries keys)."
        ),
    )
    parser.add_argument(
        "--redis-url",
        default=os.environ.get("NOTT_REDIS_URL", config["DEFAULT"]["databaseurl"]),
        help="Redis URL (default: config.ini databaseurl or NOTT_REDIS_URL)",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=DEFAULT_HOURS,
        help="Hours of history to fetch and fit (default: 12)",
    )
    parser.add_argument(
        "--sensors-ini",
        default=sensor_config_path,
        help="Path to sensors.ini used to resolve Redis keys",
    )
    parser.add_argument(
        "--n-exp",
        type=int,
        default=2,
        help="Number of exponential terms in the fit (default: 2)",
    )
    parser.add_argument(
        "--predict-hours",
        type=float,
        default=24.0,
        help="Hours ahead from now to evaluate the fitted model (default: 24)",
    )
    parser.add_argument(
        "--target-k",
        type=float,
        default=DEFAULT_MONITOR_TARGET_K,
        help=(
            "Base plate target temperature (K) for time-to-reach legend "
            f"(default: {DEFAULT_MONITOR_TARGET_K:g})"
        ),
    )
    parser.add_argument(
        "--fit-max-points",
        type=int,
        default=DEFAULT_FIT_MAX_POINTS,
        help="Max samples used for curve fitting (default: 300)",
    )
    parser.add_argument(
        "--plot-max-points",
        type=int,
        default=DEFAULT_PLOT_MAX_POINTS,
        help="Max samples drawn for the data trace (default: 2000)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output image path (default: cryo_monitor.png when not showing)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open an interactive plot window",
    )
    args = parser.parse_args()

    if args.n_exp < 1:
        print("error: --n-exp must be at least 1", file=sys.stderr)
        return 1
    if args.fit_max_points < 10:
        print("error: --fit-max-points must be at least 10", file=sys.stderr)
        return 1

    return plot_cryo_monitor(
        redis_url=args.redis_url,
        sensor_groups=MONITOR_SENSOR_GROUPS,
        sensors_ini=args.sensors_ini,
        hours=args.hours,
        output=args.output,
        show=args.show,
        n_exp_terms=args.n_exp,
        predict_hours=args.predict_hours,
        fit_max_points=args.fit_max_points,
        plot_max_points=args.plot_max_points,
        target_temp_k=args.target_k,
    )


if __name__ == "__main__":
    raise SystemExit(main())
