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
from nottcontrol.script.lib.nott_time import unix_time_ms

DEFAULT_KEYS = (
    "cryo.t_shield_1.lrTempK",
    "cryo.t_shield_2.lrTempK",
    "cryo.t_cabinet_vote.lrTempK",
)


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


def plot_cryo_temps(
    redis_url: str,
    keys: tuple[str, ...],
    hours: float,
    output: str | None,
    show: bool,
) -> int:
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    start_ms = unix_time_ms(start)
    end_ms = unix_time_ms(end)

    fig, ax = plt.subplots(figsize=(11, 5))
    any_data = False

    for key in keys:
        times, values = fetch_timeseries(redis_url, key, start_ms, end_ms)
        if times.size == 0:
            print(f"warning: no samples for {key}", file=sys.stderr)
            continue
        any_data = True
        label = key.removeprefix("cryo.").removesuffix(".lrTempK")
        ax.plot(
            [datetime.utcfromtimestamp(t) for t in times],
            values,
            linewidth=1.2,
            label=label,
        )

    if not any_data:
        print(
            f"error: no data found in the last {hours:g} h for keys: {', '.join(keys)}",
            file=sys.stderr,
        )
        return 1

    ax.set_title(f"Cryostat temperatures (last {hours:g} h, UTC)")
    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Temperature (K)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
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

    return plot_cryo_temps(
        redis_url=args.redis_url,
        keys=tuple(args.keys),
        hours=args.hours,
        output=args.output,
        show=args.show,
    )


if __name__ == "__main__":
    raise SystemExit(main())
