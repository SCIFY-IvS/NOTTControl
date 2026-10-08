import logging
import os
import sys
from pathlib import Path

_MISSING_CONFIG_MSG = (
    "Missing nottcontrol/config.ini. "
    "Copy config.ini.example to config.ini and fill in your site values before first run."
)


def main():
    # Change the running directory to this directory so config.ini / .ui files resolve.
    package_dir = Path(__file__).resolve().parent
    os.chdir(package_dir)

    if not (package_dir / "config.ini").is_file():
        raise SystemExit(_MISSING_CONFIG_MSG)

    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication

    from nottcontrol.app_icon import apply_app_icon, ensure_windows_app_identity
    from nottcontrol.opcua import OPCUAConnection
    from nottcontrol.scifygui import MainWindow
    from nottcontrol.ui_scale import (
        apply_platform_font,
        configure_high_dpi,
        init_ui_scale,
    )
    from nottcontrol import config

    configure_high_dpi()
    ensure_windows_app_identity()

    # initialize the OPC UA connection
    url = config["DEFAULT"]["opcuaaddress"]

    logger = logging.getLogger("asyncua")
    logger.setLevel(logging.WARNING)

    opcua_timeout_s = config.getfloat("SENSORS", "opcua_timeout_s", fallback=10.0)
    opcua_conn = OPCUAConnection(url, timeout=opcua_timeout_s)
    opcua_conn.connect()

    # set up the main window
    # Must set OpenGL attribute before QApplication exists (Linux/VNC stability).
    if sys.platform.startswith("linux"):
        QApplication.setAttribute(Qt.AA_UseSoftwareOpenGL, True)
        # Prefer no high-DPI attribute path on Linux/VNC (see configure_high_dpi).
        try:
            QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, True)
        except AttributeError:
            pass
        try:
            QApplication.setAttribute(Qt.AA_Use96Dpi, True)
        except AttributeError:
            pass
    app = QApplication(sys.argv)
    if not sys.platform.startswith("linux"):
        app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    apply_platform_font(app)
    init_ui_scale(app)
    apply_app_icon(app)
    main_window = MainWindow(opcua_conn)
    main_window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--create-shortcut", "--shortcut"):
        from nottcontrol.windows.create_desktop_shortcut import create_desktop_shortcut

        shortcut = create_desktop_shortcut()
        print(f"Created shortcut: {shortcut}")
        raise SystemExit(0)
    main()
