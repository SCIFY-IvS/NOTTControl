#!/usr/bin/env python3
"""Fetch cryostat temperature TimeSeries from NOTT Redis and plot them."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import Callable

import matplotlib.pyplot as plt
import numpy as np
import redis
from scipy.optimize import brentq, curve_fit

from nottcontrol import config, sensor_config_path
from nottcontrol.sensors import (
    load_sensor_config,
    opc_node_path,
    opc_node_to_asyncua_id,
)

DEFAULT_SENSOR_NAMES = (
    "t_base_plate_1",
    "t_base_plate_2",
)

# Shield + base plate groups for monitor_cryo_temps.py (Redis keys via sensors.ini).
MONITOR_SENSOR_GROUPS: dict[str, tuple[str, ...]] = {
    "Base plate": ("t_base_plate_1", "t_base_plate_2"),
    "Shield": ("t_shield_1", "t_shield_2"),
}

DEFAULT_MONITOR_TARGET_K = 90.0
BASE_PLATE_GROUP = "Base plate"

_EPOCH = datetime.utcfromtimestamp(0)
DEFAULT_FIT_MAX_POINTS = 300
DEFAULT_PLOT_MAX_POINTS = 2_000


def redis_key_label(key: str) -> str:
    """Short legend label from a Redis key or OPC UA node id."""
    path = opc_node_path(key)
    if path.endswith(".stat.lrTempK"):
        path = path[: -len(".stat.lrTempK")]
    parts = path.split(".")
    if "nott_temp" in parts:
        return ".".join(parts[parts.index("nott_temp") + 1 :])
    return parts[-1] if parts else key


def build_sensor_key_map(path: str | os.PathLike[str]) -> dict[str, str]:
    """Map short sensor names to Redis TimeSeries keys from sensors.ini."""
    _, redis_keys = load_sensor_config(path)
    return {redis_key_label(key): key for key in redis_keys}


def normalize_redis_key(key: str, sensor_map: dict[str, str]) -> str:
    """Accept asyncua ids, sensors.ini lines, short names, or legacy cryo.* keys."""
    if key in sensor_map:
        return sensor_map[key]
    if key.startswith("cryo."):
        short_name = key.removeprefix("cryo.").removesuffix(".lrTempK")
        if short_name in sensor_map:
            return sensor_map[short_name]
    return opc_node_to_asyncua_id(key)


def resolve_redis_keys(
    keys: list[str] | None,
    sensor_names: list[str] | None,
    sensors_ini: str | os.PathLike[str],
) -> list[str]:
    sensor_map = build_sensor_key_map(sensors_ini)
    if keys:
        return [normalize_redis_key(key, sensor_map) for key in keys]
    names = sensor_names if sensor_names else list(DEFAULT_SENSOR_NAMES)
    missing = [name for name in names if name not in sensor_map]
    if missing:
        available = ", ".join(sorted(sensor_map))
        raise ValueError(
            f"unknown sensor name(s): {', '.join(missing)}. "
            f"Available short names: {available}"
        )
    return [sensor_map[name] for name in names]


def unix_time_ms(time: datetime) -> int:
    return round((time - _EPOCH).total_seconds() * 1000.0)


def fetch_timeseries(
    redis_client: redis.Redis,
    key: str,
    start_ms: int,
    end_ms: int,
) -> tuple[np.ndarray, np.ndarray]:
    samples = redis_client.ts().range(key, start_ms, end_ms)
    if not samples:
        return np.array([]), np.array([])
    data = np.array(samples, dtype=float)
    times = data[:, 0] / 1000.0
    values = data[:, 1]
    return times, values


def downsample_series(
    times: np.ndarray,
    values: np.ndarray,
    max_points: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Keep evenly spaced points, always including the first and last sample."""
    if times.size <= max_points:
        return times, values
    indices = np.linspace(0, times.size - 1, max_points, dtype=int)
    indices = np.unique(indices)
    return times[indices], values[indices]


def exponential_sum_model(t_hours: np.ndarray, t_asymp: float, *params: float) -> np.ndarray:
    """T(t) = T_asymp + sum_i A_i * exp(-t / tau_i)."""
    result = np.full_like(t_hours, t_asymp, dtype=float)
    for index in range(0, len(params), 2):
        amplitude, tau = params[index], max(params[index + 1], 1e-6)
        result += amplitude * np.exp(-t_hours / tau)
    return result


def build_exponential_model(n_terms: int) -> Callable[..., np.ndarray]:
    def model(t_hours: np.ndarray, t_asymp: float, *params: float) -> np.ndarray:
        return exponential_sum_model(t_hours, t_asymp, *params)

    model.__name__ = f"exp_sum_{n_terms}"
    return model


def initial_guess(times: np.ndarray, values: np.ndarray, n_terms: int) -> list[float]:
    t_hours = (times - times[0]) / 3600.0
    span = max(t_hours[-1], 0.1)
    t_asymp = float(values[-1])
    delta = float(values[0] - t_asymp)

    guess = [t_asymp]
    for index in range(n_terms):
        amplitude = delta / (index + 1)
        tau = span / (index + 1)
        guess.extend([amplitude, tau])
    return guess


def fit_exponential_sum(
    times: np.ndarray,
    values: np.ndarray,
    n_terms: int,
) -> tuple[np.ndarray, float]:
    t_hours = (times - times[0]) / 3600.0
    model = build_exponential_model(n_terms)
    p0 = initial_guess(times, values, n_terms)

    value_span = max(float(values.max() - values.min()), 1.0)
    max_tau = max(t_hours[-1], 0.1) * 20
    lower = [values.min() - value_span]
    upper = [values.max() + value_span]
    for _ in range(n_terms):
        lower.extend([-2 * value_span, 1e-3])
        upper.extend([2 * value_span, max(max_tau, 1.0)])

    params, _ = curve_fit(
        model,
        t_hours,
        values,
        p0=p0,
        bounds=(lower, upper),
        method="trf",
        maxfev=5_000,
    )
    return params, times[0]


def predict_temperature(
    params: np.ndarray,
    t0: float,
    unix_time: float,
    n_terms: int,
) -> float:
    t_hours = (unix_time - t0) / 3600.0
    model = build_exponential_model(n_terms)
    return float(model(np.array([t_hours]), *params)[0])


def asymptotic_temperature(params: np.ndarray) -> float:
    return float(params[0])


def temperature_at_fit_hours(
    params: np.ndarray,
    t_hours: float,
    n_terms: int,
) -> float:
    return float(exponential_sum_model(np.array([t_hours]), *params)[0])


def time_hours_to_reach_temperature(
    params: np.ndarray,
    n_terms: int,
    target_k: float,
    t_search_max: float = 10_000.0,
) -> float | None:
    """Hours from fit t=0 until the model reaches target_k, if it crosses."""
    t_start = temperature_at_fit_hours(params, 0.0, n_terms)
    t_asymp = asymptotic_temperature(params)

    if abs(t_start - target_k) < 1e-3:
        return 0.0

    if (t_start - target_k) * (t_asymp - target_k) > 0:
        return None

    def delta(t_hours: float) -> float:
        return temperature_at_fit_hours(params, t_hours, n_terms) - target_k

    hi = max(1.0, t_search_max / 100.0)
    while hi <= t_search_max:
        if delta(hi) * delta(0.0) <= 0:
            return float(brentq(delta, 0.0, hi))
        hi *= 2.0
    return None


def format_time_to_target_label(
    label: str,
    target_k: float,
    hours_from_fit_start: float | None,
    fit_start_unix: float,
) -> str:
    if hours_from_fit_start is None:
        return f"{label}: fit does not reach {target_k:g} K"
    if hours_from_fit_start <= 0:
        return f"{label}: at {target_k:g} K at window start"
    reach_time = datetime.utcfromtimestamp(fit_start_unix + hours_from_fit_start * 3600.0)
    return (
        f"{label}: {target_k:g} K in {hours_from_fit_start:.2f} h "
        f"({reach_time:%Y-%m-%d %H:%M} UTC)"
    )


def plot_sensors_on_axes(
    ax: plt.Axes,
    redis_client: redis.Redis,
    keys: tuple[str, ...],
    start_ms: int,
    end_ms: int,
    predict_end_unix: float,
    predict_hours: float,
    n_exp_terms: int,
    fit_max_points: int,
    plot_max_points: int,
    target_temp_k: float | None = None,
) -> int:
    """Plot data, exponential fits, and asymptotes for keys on one axes. Returns series count."""
    min_points = 2 * n_exp_terms + 2
    model = build_exponential_model(n_exp_terms)
    plotted = 0

    for key in keys:
        times, values = fetch_timeseries(redis_client, key, start_ms, end_ms)
        if times.size == 0:
            print(f"warning: no samples for {key}", file=sys.stderr)
            continue
        if times.size < min_points:
            print(
                f"warning: not enough samples for {n_exp_terms}-term exponential fit on {key}",
                file=sys.stderr,
            )
            continue

        label = redis_key_label(key)
        fit_times, fit_values = downsample_series(times, values, fit_max_points)
        if fit_times.size < times.size:
            print(
                f"{label}: fitting on {fit_times.size} of {times.size} samples "
                f"(max {fit_max_points})",
                file=sys.stderr,
            )

        try:
            params, t0 = fit_exponential_sum(fit_times, fit_values, n_exp_terms)
        except RuntimeError as exc:
            print(f"warning: fit failed for {key}: {exc}", file=sys.stderr)
            continue

        t_asymp = asymptotic_temperature(params)
        predicted_k = predict_temperature(params, t0, predict_end_unix, n_exp_terms)

        plot_times, plot_values = downsample_series(times, values, plot_max_points)
        (data_line,) = ax.plot(
            [datetime.utcfromtimestamp(t) for t in plot_times],
            plot_values,
            linewidth=1.2,
            label=f"{label} (data)",
        )

        curve_start = times[0]
        curve_end = max(times[-1], predict_end_unix)
        curve_times = np.linspace(curve_start, curve_end, 200)
        curve_hours = (curve_times - t0) / 3600.0
        curve_values = model(curve_hours, *params)
        ax.plot(
            [datetime.utcfromtimestamp(t) for t in curve_times],
            curve_values,
            linewidth=1.5,
            linestyle="--",
            label=f"{label} fit",
        )
        ax.axhline(
            t_asymp,
            linestyle=":",
            linewidth=1.2,
            label=f"{label} asymptote = {t_asymp:.3f} K",
        )

        print(f"{label}: asymptotic temperature = {t_asymp:.4f} K")
        print(
            f"{label}: model temperature in {predict_hours:g} h "
            f"({datetime.utcfromtimestamp(predict_end_unix)} UTC) = {predicted_k:.4f} K"
        )

        if target_temp_k is not None:
            hours_to_target = time_hours_to_reach_temperature(
                params,
                n_exp_terms,
                target_temp_k,
                t_search_max=max(predict_hours, 1.0) * 24.0,
            )
            target_label = format_time_to_target_label(
                label,
                target_temp_k,
                hours_to_target,
                t0,
            )
            print(target_label)
            ax.plot([], [], linestyle="", label=target_label)
            if hours_to_target is not None and hours_to_target > 0:
                reach_unix = t0 + hours_to_target * 3600.0
                ax.axvline(
                    datetime.utcfromtimestamp(reach_unix),
                    linestyle="-.",
                    linewidth=1.0,
                    alpha=0.7,
                    color=data_line.get_color(),
                )

        plotted += 1

    return plotted


def plot_cryo_monitor(
    redis_url: str,
    sensor_groups: dict[str, tuple[str, ...]],
    sensors_ini: str | os.PathLike[str],
    hours: float,
    output: str | None,
    show: bool,
    n_exp_terms: int,
    predict_hours: float,
    fit_max_points: int,
    plot_max_points: int,
    target_temp_k: float | None = DEFAULT_MONITOR_TARGET_K,
) -> int:
    """Plot shield and base plate groups with exponential fits (separate subplots)."""
    end = datetime.utcnow()
    start_ms = unix_time_ms(end - timedelta(hours=hours))
    end_ms = unix_time_ms(end)
    predict_end_unix = end.timestamp() + predict_hours * 3600.0

    sensor_map = build_sensor_key_map(sensors_ini)
    redis_client = redis.from_url(redis_url)

    fig, axes = plt.subplots(
        len(sensor_groups),
        1,
        figsize=(11, 4 * len(sensor_groups)),
        sharex=True,
        squeeze=False,
    )
    any_data = False

    for row, (group_title, sensor_names) in enumerate(sensor_groups.items()):
        ax = axes[row, 0]
        missing = [name for name in sensor_names if name not in sensor_map]
        if missing:
            print(
                f"error: unknown sensor name(s) in {group_title!r}: {', '.join(missing)}",
                file=sys.stderr,
            )
            return 1

        keys = tuple(sensor_map[name] for name in sensor_names)
        group_target_k = target_temp_k if group_title == BASE_PLATE_GROUP else None
        plotted = plot_sensors_on_axes(
            ax,
            redis_client,
            keys,
            start_ms,
            end_ms,
            predict_end_unix,
            predict_hours,
            n_exp_terms,
            fit_max_points,
            plot_max_points,
            target_temp_k=group_target_k,
        )
        if plotted:
            any_data = True
        ax.set_title(f"{group_title} (last {hours:g} h, UTC)")
        ax.set_ylabel("Temperature (K)")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best", fontsize=8)

    if not any_data:
        print(
            f"error: no data found in the last {hours:g} h for monitor groups",
            file=sys.stderr,
        )
        plt.close(fig)
        return 1

    fig.suptitle(
        f"Cryostat monitor — exponential fit ({n_exp_terms} terms)",
        y=1.01,
    )
    axes[-1, 0].set_xlabel("Time (UTC)")
    fig.autofmt_xdate()
    fig.tight_layout()

    if output:
        fig.savefig(output, dpi=150, bbox_inches="tight")
        print(f"saved plot to {output}")
    elif show:
        plt.show()
    else:
        default_output = "cryo_monitor.png"
        fig.savefig(default_output, dpi=150, bbox_inches="tight")
        print(f"saved plot to {default_output}")

    plt.close(fig)
    return 0


def plot_cryo_temps(
    redis_url: str,
    keys: tuple[str, ...],
    hours: float,
    output: str | None,
    show: bool,
    n_exp_terms: int,
    predict_hours: float,
    fit_max_points: int,
    plot_max_points: int,
) -> int:
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    start_ms = unix_time_ms(start)
    end_ms = unix_time_ms(end)
    predict_end_unix = end.timestamp() + predict_hours * 3600.0

    fig, ax = plt.subplots(figsize=(11, 5))
    redis_client = redis.from_url(redis_url)
    plotted = plot_sensors_on_axes(
        ax,
        redis_client,
        keys,
        start_ms,
        end_ms,
        predict_end_unix,
        predict_hours,
        n_exp_terms,
        fit_max_points,
        plot_max_points,
    )

    if plotted == 0:
        print(
            f"error: no data found in the last {hours:g} h for keys: {', '.join(keys)}",
            file=sys.stderr,
        )
        return 1

    ax.set_title(
        f"Cryostat temperatures (last {hours:g} h, UTC) "
        f"with {n_exp_terms}-term exponential fit"
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
        help=(
            "Redis TimeSeries keys: OPC UA node id (ns=4;s=...), "
            "sensors.ini line, short name, or legacy cryo.* key"
        ),
    )
    parser.add_argument(
        "--sensor-names",
        nargs="+",
        default=list(DEFAULT_SENSOR_NAMES),
        help=(
            "Short sensor names from sensors.ini "
            f"(default: {' '.join(DEFAULT_SENSOR_NAMES)})"
        ),
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
        help="Output image path (default: cryo_temps.png when not showing interactively)",
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

    try:
        redis_keys = resolve_redis_keys(
            keys=args.keys,
            sensor_names=None if args.keys else args.sensor_names,
            sensors_ini=args.sensors_ini,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    return plot_cryo_temps(
        redis_url=args.redis_url,
        keys=tuple(redis_keys),
        hours=args.hours,
        output=args.output,
        show=args.show,
        n_exp_terms=args.n_exp,
        predict_hours=args.predict_hours,
        fit_max_points=args.fit_max_points,
        plot_max_points=args.plot_max_points,
    )


if __name__ == "__main__":
    raise SystemExit(main())
