"""Create or refresh the Windows Desktop shortcut with the NOTT icon."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_desktop_shortcut() -> Path:
    desktop = Path.home() / "Desktop"
    return desktop / "NOTTControl.lnk"


def create_desktop_shortcut(destination: Path | None = None) -> Path:
    if sys.platform != "win32":
        raise OSError("Desktop shortcuts are only supported on Windows.")

    if destination is None:
        destination = default_desktop_shortcut()

    ps1 = Path(__file__).resolve().parent / "Create-NOTTControlShortcut.ps1"
    if not ps1.is_file():
        raise FileNotFoundError(f"Missing shortcut script: {ps1}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps1),
            "-Destination",
            str(destination),
        ],
        check=True,
        cwd=repo_root(),
    )
    return destination


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    destination = Path(argv[0]).expanduser() if argv else None
    path = create_desktop_shortcut(destination)
    print(f"Created shortcut: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
