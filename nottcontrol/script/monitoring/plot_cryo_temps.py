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
from scipy.optimize import curve_fit

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
        maxfev=20_000,
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


def plot_cryo_temps(
    redis_url: str,
    keys: tuple[str, ...],
    hours: float,
    output: str | None,
    show: bool,
    n_exp_terms: int,
    predict_hours: float,
) -> int:
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)
    start_ms = unix_time_ms(start)
    end_ms = unix_time_ms(end)
    predict_end_unix = end.timestamp() + predict_hours * 3600.0

    fig, ax = plt.subplots(figsize=(11, 5))
    any_data = False
    min_points = 2 * n_exp_terms + 2

    for key in keys:
        times, values = fetch_timeseries(redis_url, key, start_ms, end_ms)
        if times.size == 0:
            print(f"warning: no samples for {key}", file=sys.stderr)
            continue
        if times.size < min_points:
            print(
                f"warning: not enough samples for {n_exp_terms}-term exponential fit on {key}",
                file=sys.stderr,
            )
            continue

        any_data = True
        label = key.removeprefix("cryo.").removesuffix(".lrTempK")
        try:
            params, t0 = fit_exponential_sum(times, values, n_exp_terms)
        except RuntimeError as exc:
            print(f"warning: fit failed for {key}: {exc}", file=sys.stderr)
            continue

        t_asymp = asymptotic_temperature(params)
        predicted_k = predict_temperature(params, t0, predict_end_unix, n_exp_terms)
        model = build_exponential_model(n_exp_terms)

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
        fit_values = model(fit_hours, *params)
        ax.plot(
            [datetime.utcfromtimestamp(t) for t in fit_times],
            fit_values,
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

    if not any_data:
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
        default=list(DEFAULT_KEYS),
        help="Redis TimeSeries keys to plot",
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

    return plot_cryo_temps(
        redis_url=args.redis_url,
        keys=tuple(args.keys),
        hours=args.hours,
        output=args.output,
        show=args.show,
        n_exp_terms=args.n_exp,
        predict_hours=args.predict_hours,
    )


if __name__ == "__main__":
    raise SystemExit(main())
