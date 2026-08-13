#!/usr/bin/env python3
"""Pull /archive/nott from nott-server onto a local computer.

Server-side Hawaii backups land under /archive/nott (UTC day folders).
This script mirrors that tree to a user-chosen local folder via rsync over SSH.

Default local destination:

    /Volumes/T7 Data/Data/nott

Override with --dest or the NOTT_BACKUP_DEST environment variable.

Notes
-----
macOS ships openrsync, which is incompatible with GNU rsync on Linux servers
(typical symptom: ``unexpected tag``). Install a modern rsync with:

    brew install rsync

The remote shell must produce no stdout on non-interactive SSH (rsync manpage
"is your shell clean?"). Keep banners in ``~/.bashrc`` behind the interactive
guard, or comment them out.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DEFAULT_REMOTE_USER = "labo"
DEFAULT_REMOTE_HOST = "nott-server"
DEFAULT_REMOTE_PATH = "/archive/nott"
DEFAULT_LOCAL_DEST = Path("/Volumes/T7 Data/Data/nott")
DEFAULT_EXCLUDES = ("old/",)
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"

# Prefer Homebrew GNU rsync over Apple openrsync.
_RSYNC_CANDIDATES = (
    "/opt/homebrew/bin/rsync",
    "/usr/local/bin/rsync",
)


def env_or_default(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value if value else default


def utc_day_string(day: str | None) -> str:
    if day is not None:
        datetime.strptime(day, "%Y%m%d")
        return day
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    return yesterday.strftime("%Y%m%d")


def remote_source(
    user: str | None,
    host: str,
    remote_path: str,
    day: str | None = None,
) -> str:
    path = remote_path.rstrip("/")
    if day is not None:
        path = f"{path}/{day}"
    if user:
        return f"{user}@{host}:{path}/"
    return f"{host}:{path}/"


def rsync_version_text(rsync_bin: str) -> str:
    try:
        completed = subprocess.run(
            [rsync_bin, "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return str(exc)
    return (completed.stdout or completed.stderr or "").strip()


def is_openrsync(version_text: str) -> bool:
    lower = version_text.lower()
    return "openrsync" in lower or "rsync version 2.6.9 compatible" in lower


def resolve_rsync_bin(explicit: str | None = None) -> str:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"rsync not found: {path}")
        return str(path)

    env_bin = os.environ.get("NOTT_BACKUP_RSYNC", "").strip()
    candidates: list[str] = []
    if env_bin:
        candidates.append(env_bin)
    candidates.extend(_RSYNC_CANDIDATES)
    which = shutil.which("rsync")
    if which:
        candidates.append(which)

    seen: set[str] = set()
    openrsync_hit: str | None = None
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if not Path(candidate).is_file() and shutil.which(candidate) is None:
            continue
        version = rsync_version_text(candidate)
        if is_openrsync(version):
            openrsync_hit = candidate
            continue
        return candidate

    if openrsync_hit is not None:
        raise RuntimeError(
            "macOS openrsync cannot talk to GNU rsync on nott-server "
            "(error looks like: unexpected tag).\n"
            "Install a compatible client and re-run:\n"
            "  brew install rsync\n"
            "Or point at a GNU rsync binary with --rsync / NOTT_BACKUP_RSYNC."
        )
    raise FileNotFoundError("rsync not found in PATH")


def rsync_pull(
    rsync_bin: str,
    source: str,
    dest: Path,
    *,
    dry_run: bool,
    delete: bool,
    ssh_command: str,
    excludes: tuple[str, ...] = DEFAULT_EXCLUDES,
) -> int:
    dest.mkdir(parents=True, exist_ok=True)

    cmd = [
        rsync_bin,
        "-aH",
        "--partial",
        "-h",
        "--progress",
        "--stats",
        "-e",
        ssh_command,
    ]
    for pattern in excludes:
        cmd.extend(["--exclude", pattern])
    if dry_run:
        cmd.append("--dry-run")
    if delete:
        cmd.append("--delete")

    # Trailing slash on source: copy contents into dest.
    cmd.extend([source, f"{dest}/"])

    logging.info("Running: %s", " ".join(cmd))
    return subprocess.call(cmd)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backup nott-server /archive/nott to a local folder "
            "(default: /Volumes/T7 Data/Data/nott)."
        ),
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help=(
            f"Local destination root (default: NOTT_BACKUP_DEST or "
            f"{DEFAULT_LOCAL_DEST})"
        ),
    )
    parser.add_argument(
        "--host",
        default=None,
        help=(
            f"Remote host (default: NOTT_BACKUP_HOST or "
            f"{DEFAULT_REMOTE_HOST})"
        ),
    )
    parser.add_argument(
        "--user",
        default=None,
        help=(
            f"SSH user on the remote host (default: NOTT_BACKUP_USER or "
            f"{DEFAULT_REMOTE_USER})"
        ),
    )
    parser.add_argument(
        "--remote-path",
        default=None,
        help=(
            f"Remote archive path (default: NOTT_BACKUP_REMOTE or "
            f"{DEFAULT_REMOTE_PATH})"
        ),
    )
    parser.add_argument(
        "--mode",
        choices=("incremental", "day"),
        default="incremental",
        help=(
            "incremental: rsync entire archive tree (default); "
            "day: copy one UTC day folder only"
        ),
    )
    parser.add_argument(
        "--day",
        metavar="YYYYMMDD",
        default=None,
        help="UTC day for --mode day (default: yesterday)",
    )
    parser.add_argument(
        "--delete",
        action="store_true",
        help=(
            "Remove local files that no longer exist on the server "
            "(incremental mode only)"
        ),
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=None,
        metavar="PATTERN",
        help=(
            "Extra rsync exclude pattern (repeatable). "
            f"Default excludes: {', '.join(DEFAULT_EXCLUDES)}"
        ),
    )
    parser.add_argument(
        "--include-old",
        action="store_true",
        help="Do not exclude the archive 'old/' directory",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without writing",
    )
    parser.add_argument(
        "--rsync",
        default=None,
        help="Path to GNU rsync binary (default: Homebrew rsync, then PATH)",
    )
    parser.add_argument(
        "--ssh-opts",
        default=None,
        help=(
            "Extra ssh options appended to the ssh command "
            '(e.g. "-i ~/.ssh/id_ed25519")'
        ),
    )
    parser.add_argument(
        "--allow-password",
        action="store_true",
        help="Allow interactive password prompts (disables SSH BatchMode)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Optional log file path (default: <dest>/backup_local.log)",
    )
    return parser.parse_args(argv)


def configure_logging(log_file: Path | None) -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file is not None:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
        except OSError as exc:
            print(
                f"warning: cannot write log file {log_file}: {exc}",
                file=sys.stderr,
            )

    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=handlers,
    )


def build_ssh_command(*, allow_password: bool, ssh_opts: str | None) -> str:
    parts = ["ssh", "-T"]
    if not allow_password:
        # Fail fast on missing keys instead of hanging on a password prompt.
        parts.extend(
            ["-o", "BatchMode=yes", "-o", "PreferredAuthentications=publickey"]
        )
    if ssh_opts:
        parts.append(ssh_opts)
    return " ".join(parts)


def main(argv: list[str] | None = None) -> int:
    if shutil.which("ssh") is None:
        print("error: ssh not found in PATH", file=sys.stderr)
        return 1

    args = parse_args(argv)

    try:
        rsync_bin = resolve_rsync_bin(args.rsync)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    user = args.user or env_or_default("NOTT_BACKUP_USER", DEFAULT_REMOTE_USER)
    host = args.host or env_or_default("NOTT_BACKUP_HOST", DEFAULT_REMOTE_HOST)
    remote_path = args.remote_path or env_or_default(
        "NOTT_BACKUP_REMOTE", DEFAULT_REMOTE_PATH
    )
    if args.dest is not None:
        dest_root = args.dest
    else:
        dest_root = Path(
            env_or_default("NOTT_BACKUP_DEST", str(DEFAULT_LOCAL_DEST))
        )

    # Volume mount check: refuse to create a fake tree if the disk is not mounted.
    if dest_root.is_absolute():
        volume = (
            Path("/Volumes") / dest_root.parts[2]
            if len(dest_root.parts) >= 3 and dest_root.parts[1] == "Volumes"
            else None
        )
        if volume is not None and not volume.exists():
            print(
                f"error: volume not mounted: {volume}\n"
                f"Mount the drive or pass --dest to another folder.",
                file=sys.stderr,
            )
            return 1

    log_file = args.log_file or (dest_root / "backup_local.log")
    configure_logging(log_file)

    ssh_command = build_ssh_command(
        allow_password=args.allow_password,
        ssh_opts=args.ssh_opts,
    )

    excludes: list[str] = []
    if not args.include_old:
        excludes.extend(DEFAULT_EXCLUDES)
    if args.exclude:
        excludes.extend(args.exclude)
    excludes_tuple = tuple(excludes)

    logging.info("Local archive backup start (mode=%s)", args.mode)
    logging.info("rsync: %s", rsync_bin)
    logging.info("Remote: %s@%s:%s", user, host, remote_path)
    logging.info("Local dest: %s", dest_root)
    if excludes_tuple:
        logging.info("Excludes: %s", ", ".join(excludes_tuple))

    try:
        if args.mode == "day":
            day = utc_day_string(args.day)
            source = remote_source(user, host, remote_path, day=day)
            dest = dest_root / day
            logging.info("Backing up UTC day %s", day)
            rc = rsync_pull(
                rsync_bin,
                source,
                dest,
                dry_run=args.dry_run,
                delete=False,
                ssh_command=ssh_command,
                excludes=excludes_tuple,
            )
        else:
            source = remote_source(user, host, remote_path)
            rc = rsync_pull(
                rsync_bin,
                source,
                dest_root,
                dry_run=args.dry_run,
                delete=args.delete,
                ssh_command=ssh_command,
                excludes=excludes_tuple,
            )
    except OSError as exc:
        logging.error("%s", exc)
        return 1

    if rc == 0:
        logging.info("Local archive backup completed successfully")
    else:
        logging.error("Local archive backup failed with exit code %s", rc)
        if rc == 2:
            logging.error(
                "rsync protocol mismatch usually means the remote shell prints "
                "text on login (check ~/.bashrc on the server)."
            )
        if rc in (10, 12, 255) and not args.allow_password:
            logging.error(
                "If this was an auth failure, confirm key login works: "
                "ssh %s@%s  (or pass --allow-password)",
                user,
                host,
            )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
