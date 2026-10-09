#!/usr/bin/env python3
"""Run plot_uptheramp (+ QA) for every session folder that still needs it.

Intended for cron on the acquisition machine. Walks immediate subdirectories
of ``--root`` (same layout as ``scan_uptheramp_sessions.py``), skips sessions
whose flux / QA products are already up to date relative to the source FITS,
and invokes ``plot_uptheramp.main`` for the rest.

Example::

    ./nottcontrol/script/detector/msac_ramp/process_uptheramp_sessions.sh
    ./nottcontrol/script/detector/msac_ramp/process_uptheramp_sessions.sh --dry-run
    ./nottcontrol/script/detector/msac_ramp/process_uptheramp_sessions.sh --force
    ./nottcontrol/script/detector/msac_ramp/process_uptheramp_sessions.sh \\
        --root /data/bench_data/H2RG_ASIC/UpTheRamp

Cron (every 30 min, log to archive)::

    */30 * * * * /home/labo/src/NOTTControl/nottcontrol/script/detector/msac_ramp/process_uptheramp_sessions.sh >> /archive/bench_data/uptheramp_qa_cron.log 2>&1
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

DEFAULT_ROOT = Path("/data/bench_data/H2RG_ASIC/UpTheRamp")

try:
    from . import plot_uptheramp as ramp
    from .scan_uptheramp_sessions import collect_session_dirs
except ImportError:
    import plot_uptheramp as ramp  # type: ignore[no-redef]
    from scan_uptheramp_sessions import collect_session_dirs  # type: ignore[no-redef]


def _source_fits(session: Path, slug: str) -> list[Path]:
    """FITS that are acquisition data, not plot/QA products."""
    prefix = f"{slug}_msac_"
    return sorted(
        p
        for p in session.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".fits"
        and not p.name.startswith(prefix)
    )


def session_done(
    session: Path,
    *,
    require_qa: bool = True,
) -> tuple[bool, str]:
    """Return (done, reason). Done means products exist and are not older than sources."""
    slug = ramp.session_filename_slug(session)
    flux_png = session / f"{slug}_msac_uptheramp_illum_vs_file.png"
    qa_png = session / f"{slug}_msac_qa_ramp.png"

    if not flux_png.is_file():
        return False, "missing flux plot"
    if require_qa and not qa_png.is_file():
        return False, "missing QA ramp plot"

    sources = _source_fits(session, slug)
    if not sources:
        return True, "products present (no source FITS left)"

    newest_src = max(p.stat().st_mtime for p in sources)
    product_mtimes = [flux_png.stat().st_mtime]
    if require_qa:
        product_mtimes.append(qa_png.stat().st_mtime)
    oldest_product = min(product_mtimes)
    if newest_src > oldest_product + 1.0:
        return False, "source FITS newer than products"
    return True, "up to date"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Process all MSAC UpTheRamp session folders that still need "
            "flux/QA plots (cron-friendly)."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help=f"Parent of session folders (default: {DEFAULT_ROOT})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-run even when products look up to date",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List sessions that would be processed; do not run plot_uptheramp",
    )
    parser.add_argument(
        "--no-qa",
        action="store_true",
        help="Pass --no-qa to plot_uptheramp (also skip QA files in 'done' check)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help="Process at most N pending sessions (oldest first)",
    )
    parser.add_argument(
        "--newest-first",
        action="store_true",
        help="Process newest pending sessions first (default: oldest first)",
    )
    parser.add_argument(
        "--plot-arg",
        action="append",
        default=[],
        metavar="ARG",
        help=(
            "Extra argument forwarded to plot_uptheramp "
            "(repeatable; e.g. --plot-arg --no-ref-correct)"
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Debug logging",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format=LOG_FORMAT,
    )

    try:
        sessions = collect_session_dirs(args.root)
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        return 1

    require_qa = not args.no_qa
    pending: list[tuple[Path, str]] = []
    skipped = 0
    for session in sessions:
        done, reason = session_done(session, require_qa=require_qa)
        if done and not args.force:
            skipped += 1
            logging.debug("skip %s (%s)", session.name, reason)
            continue
        pending.append((session, "forced" if args.force and done else reason))

    pending.sort(
        key=lambda item: item[0].stat().st_mtime,
        reverse=bool(args.newest_first),
    )
    if args.limit is not None:
        pending = pending[: max(0, int(args.limit))]

    logging.info(
        "Found %d session(s) under %s: %d pending, %d already done",
        len(sessions),
        args.root,
        len(pending),
        skipped,
    )

    if not pending:
        return 0

    failures = 0
    for session, reason in pending:
        logging.info("Process %s (%s)", session.name, reason)
        if args.dry_run:
            continue
        plot_argv = ["--ramp-dir", str(session)]
        if args.no_qa:
            plot_argv.append("--no-qa")
        plot_argv.extend(args.plot_arg)
        t0 = time.monotonic()
        try:
            rc = int(ramp.main(plot_argv) or 0)
        except Exception as exc:  # noqa: BLE001 — keep cron going
            logging.exception("Failed %s: %s", session.name, exc)
            failures += 1
            continue
        elapsed = time.monotonic() - t0
        if rc != 0:
            logging.error("plot_uptheramp exited %s for %s", rc, session.name)
            failures += 1
        else:
            logging.info("Done %s in %.1fs", session.name, elapsed)

    if args.dry_run:
        logging.info("Dry-run: would process %d session(s)", len(pending))
        return 0

    if failures:
        logging.error("Finished with %d failure(s)", failures)
        return 1
    logging.info("Finished successfully (%d processed)", len(pending))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 — CLI surface
        logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
        logging.error("%s", exc)
        raise SystemExit(1) from exc
