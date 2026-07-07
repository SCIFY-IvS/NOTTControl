"""Build Windows launcher assets (NOTT.ico)."""

from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication

from nottcontrol.app_icon import save_app_icon_ico


def main() -> int:
    app = QApplication(sys.argv)
    path = save_app_icon_ico()
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
