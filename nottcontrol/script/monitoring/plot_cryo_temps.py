#!/usr/bin/env python3
"""Fetch cryostat temperature TimeSeries from NOTT Redis and plot them."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import redis

from nottcontrol import config

DEFAULT_KEYS = (
    "cryo.t_shield_1.lrTempK",
    "cryo.t_shield_2.lrTempK",
    "cryo.t_cabinet_vote.lrTempK",
)

_EPOCH = datetime.utcfromtimestamp(0)


def unix_time_ms(time: datetime) -> int:
    return round((time - _EPOCH).total_seconds() * 1000.0)


def fetch_timeseries(
    redis_url: str,
    key: str,
    start_ms: int,
    end_ms: int,
) -> tuple[np.ndarray, np.ndarray]:
    client = redis.from_url(redis_url)
    samples = client.ts().range(key, start_ms, end_ms)
    if not samples:
        return np.array([]), np.array([])
    data = np.array(samples, dtype=float)
    times = data[:, 0] / 1000.0
    values = data[:, 1]
    return times, values


def fit_polynomial(
    times: np.ndarray,
    values: np.ndarray,
    degree: int,
) -> tuple[np.ndarray, float]:
    """Fit temperature vs time (hours from first sample) and return coeffs and t0."""
    t0 = times[0]
    hours = (times - t0) / 3600.0
    coeffs = np.polyfit(hours, values, degree)
    return coeffs, t0


def predict_temperature(
    coeffs: np.ndarray,
    t0: float,
    unix_time: float,
) -> float:
    hours = (unix_time - t0) / 3600.0
    return float(np.polyval(coeffs, hours))


def plot_cryo_temps(
    redis_url: str,
    keys: tuple[str, ...],
    hours: float,
    output: str | None,
    show: bool,
    poly_degree: int,
    predict_hours: float,
) -> int:
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    start_ms = unix_time_ms(start)
    end_ms = unix_time_ms(end)
    predict_end_unix = end.timestamp() + predict_hours * 3600.0

    fig, ax = plt.subplots(figsize=(11, 5))
    any_data = False

    for key in keys:
        times, values = fetch_timeseries(redis_url, key, start_ms, end_ms)
        if times.size == 0:
            print(f"warning: no samples for {key}", file=sys.stderr)
            continue
        if times.size <= poly_degree:
            print(
                f"warning: not enough samples for degree-{poly_degree} fit on {key}",
                file=sys.stderr,
            )
            continue

        any_data = True
        label = key.removeprefix("cryo.").removesuffix(".lrTempK")
        coeffs, t0 = fit_polynomial(times, values, poly_degree)
        predicted_k = predict_temperature(coeffs, t0, predict_end_unix)

        ax.plot(
            [datetime.utcfromtimestamp(t) for t in times],
            values,
            linewidth=1.2,
            label=f"{label} (data)",
        )

        fit_start = times[0]
        fit_end = max(times[-1], predict_end_unix)
        fit_times = np.linspace(fit_start, fit_end, 200)
        fit_hours = (fit_times - t0) / 3600.0
        fit_values = np.polyval(coeffs, fit_hours)
        ax.plot(
            [datetime.utcfromtimestamp(t) for t in fit_times],
            fit_values,
            linewidth=1.5,
            linestyle="--",
            label=f"{label} fit → {predicted_k:.3f} K",
        )

        print(
            f"{label}: predicted temperature in {predict_hours:g} h "
            f"({datetime.utcfromtimestamp(predict_end_unix)} UTC) = {predicted_k:.4f} K"
        )

    if not any_data:
        print(
            f"error: no data found in the last {hours:g} h for keys: {', '.join(keys)}",
            file=sys.stderr,
        )
        return 1

    ax.set_title(
        f"Cryostat temperatures (last {hours:g} h, UTC) "
        f"with degree-{poly_degree} polynomial extrapolation"
    )
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Temperature (K)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best", fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()

    if output:
        fig.savefig(output, dpi=150)
        print(f"saved plot to {output}")

    if show:
        plt.show()
    elif not output:
        default_output = "cryo_temps.png"
        fig.savefig(default_output, dpi=150)
        print(f"saved plot to {default_output}")

    plt.close(fig)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Plot cryostat Redis TimeSeries from the NOTT server.",
    )
    parser.add_argument(
        "--redis-url",
        default=os.environ.get("NOTT_REDIS_URL", config["DEFAULT"]["databaseurl"]),
        help="Redis URL (default: config.ini databaseurl or NOTT_REDIS_URL)",
    )
    parser.add_argument(
        "--hours",
        type=float,
        default=12.0,
        help="Hours of history to fetch (default: 12)",
    )
    parser.add_argument(
        "--keys",
        nargs="+",
        default=list(DEFAULT_KEYS),
        help="Redis TimeSeries keys to plot",
    )
    parser.add_argument(
        "--poly-degree",
        type=int,
        default=3,
        help="Polynomial degree for the temperature fit (default: 3)",
    )
    parser.add_argument(
        "--predict-hours",
        type=float,
        default=24.0,
        help="Hours ahead from now to predict final temperature (default: 24)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output image path (default: cryo_temps.png when not showing interactively)",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Open an interactive plot window",
    )
    args = parser.parse_args()

    if args.poly_degree < 1:
        print("error: --poly-degree must be at least 1", file=sys.stderr)
        return 1

    return plot_cryo_temps(
        redis_url=args.redis_url,
        keys=tuple(args.keys),
        hours=args.hours,
        output=args.output,
        show=args.show,
        poly_degree=args.poly_degree,
        predict_hours=args.predict_hours,
    )


if __name__ == "__main__":
    raise SystemExit(main())
