"""Ramp timing plans and science reduction for H2RG/MACIE (CDS vs Fowler)."""

from __future__ import annotations

import math
from typing import Literal

RampMode = Literal["SingleFrame", "Ramp", "CDS", "Fowler"]

RAMP_MODES: tuple[RampMode, ...] = ("SingleFrame", "Ramp", "CDS", "Fowler")

# GUI label, internal mode (PyQt combo userData)
RAMP_MODE_ITEMS: tuple[tuple[str, RampMode], ...] = (
    ("Single Frame", "SingleFrame"),
    ("Ramp", "Ramp"),
    ("CDS", "CDS"),
    ("Fowler", "Fowler"),
)
EXP_MODE_UTR = 0
EXP_MODE_FOWLER = 1


def fits_wait_timeout_s(
    execution_s: float,
    *,
    ncoadds: int = 1,
    nseq: int = 1,
    margin_s: float = 30.0,
    minimum_s: float = 30.0,
    maximum_s: float | None = None,
) -> float:
    """Estimate how long the GUI should wait for FITS after acquire."""
    total = float(execution_s) * max(1, int(ncoadds)) * max(1, int(nseq)) + margin_s
    total = max(minimum_s, total)
    if maximum_s is not None:
        total = min(total, maximum_s)
    return total


def _windowed_one_group_plan(
    frametime_ms: float,
    *,
    n_frames: int,
) -> dict[str, float | int]:
    """Soft SC / stripe: one group × N reads (no inter-group drops).

    A lone read ignores StripeSkips1 and clocks from row 0 (wrong Y band).
    Drop frames between groups can also desync soft-SC geometry. Keep all
    samples in one group so middle-stripe counters stay latched for every read.
    Photon time reported by MACIE is N × frametime (minus resets separately).
    """
    n_frames = max(2, int(n_frames))
    return {
        "ngroups": 1,
        "nreads": n_frames,
        "ndrops": 0,
        "fowler_pairs": 0,
        "tint_ms": n_frames * frametime_ms,
    }


def calc_ramp_plan(
    tint_ms: float,
    frametime_ms: float,
    *,
    mode: RampMode = "CDS",
    fowler_pairs: int = 2,
    ngmax: int = 2,
    windowed_cds: bool = False,
) -> dict[str, int]:
    """Return ngroups, nreads, ndrops for a ramp at the requested integration time.

    CDS uses two correlated samples with drop frames when tint exceeds one frame
    time. Full frame: two groups × one read. Window/stripe modes: one group × N
    reads (N ≥ 2) so samples share detector geometry and long DIT is honored.

    Fowler uses one group with an even number of reads (2 × fowler_pairs) and
    ASIC ExpMode=Fowler; pair-difference averaging is done in software.

    SingleFrame uses one group × one read with no drop frames (one clocked frame).
    On window/stripe (soft SC), SingleFrame is promoted to the same 1×2 plan as
    windowed CDS — a lone read ignores StripeSkips1 and clocks from row 0.

    Ramp rounds the requested DIT to the nearest whole number of frame times
    (minimum one frame on full frame). One frame → single read; two or more →
    two groups with drop frames between. On window/stripe, Ramp uses one group ×
    N reads (minimum two) for the same soft-SC stability reasons as CDS.
    """
    if frametime_ms <= 0:
        frametime_ms = 1.0
    if tint_ms <= 0:
        tint_ms = frametime_ms

    fowler_pairs = max(1, min(int(fowler_pairs), 8))

    if mode == "Fowler":
        nreads = 2 * fowler_pairs
        return {"ngroups": 1, "nreads": nreads, "ndrops": 0, "fowler_pairs": fowler_pairs}

    if mode == "SingleFrame":
        if windowed_cds:
            # Soft SC: one read clocks from row 0; need two reads in one group.
            return {
                "ngroups": 1,
                "nreads": 2,
                "ndrops": 0,
                "fowler_pairs": 0,
                "tint_ms": 2.0 * frametime_ms,
            }
        return {"ngroups": 1, "nreads": 1, "ndrops": 0, "fowler_pairs": 0}

    if mode == "Ramp":
        # Photon time is quantized in whole frame times — round the request
        # to the nearest multiple (at least one frame on full frame).
        n_frames = max(1, int(round(tint_ms / frametime_ms)))
        if windowed_cds:
            # Soft SC: never 1-read; never inter-group drops (geometry).
            return _windowed_one_group_plan(
                frametime_ms, n_frames=n_frames
            )
        tint_rounded = n_frames * frametime_ms
        if n_frames == 1:
            return {
                "ngroups": 1,
                "nreads": 1,
                "ndrops": 0,
                "fowler_pairs": 0,
                "tint_ms": tint_rounded,
            }
        return {
            "ngroups": 2,
            "nreads": 1,
            "ndrops": n_frames - 2,
            "fowler_pairs": 0,
            "tint_ms": tint_rounded,
        }

    # CDS — window/stripe before the short-DIT shortcut so soft SC never gets
    # a 1-read plan (that ignores StripeSkips1 and shows the bottom of the array).
    # Scale NReads so requested long DIT is actually clocked (was stuck at 1×2).
    if windowed_cds:
        n_frames = max(2, int(math.ceil(tint_ms / frametime_ms)))
        return _windowed_one_group_plan(frametime_ms, n_frames=n_frames)

    if tint_ms < frametime_ms:
        return {"ngroups": 1, "nreads": 1, "ndrops": 0, "fowler_pairs": 0}

    nftot = int(math.ceil(tint_ms / frametime_ms))
    if ngmax <= 2:
        ndrops = max(0, nftot - 2)
        return {"ngroups": 2, "nreads": 1, "ndrops": ndrops, "fowler_pairs": 0}

    nr = 1
    nd = 0
    ng = 2
    if nftot > ngmax:
        ngmin = max(1, ngmax - 1) if ngmax <= 3 else 2
        ng_best, nd_best = ng, nd
        nf_diff_prev = 10.0
        for i in range(ngmax, ngmin, -1):
            ng = i
            nd = int(math.ceil((tint_ms / frametime_ms - (ng * nr)) / max(ng - 1, 1)))
            nftot_res = ng * nr + (ng - 1) * nd
            nf_diff = abs(nftot - nftot_res)
            if nf_diff < nf_diff_prev:
                ng_best, nd_best = ng, nd
                nf_diff_prev = nf_diff
        ng, nd = ng_best, nd_best
    else:
        nd = max(0, nftot - ng * nr)

    return {"ngroups": ng, "nreads": nr, "ndrops": nd, "fowler_pairs": 0}


def exp_mode_for_ramp(mode: RampMode) -> int:
    return EXP_MODE_FOWLER if mode == "Fowler" else EXP_MODE_UTR
