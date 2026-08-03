"""UI scaling helpers for high-DPI displays (e.g. Windows 125–150 % scaling)."""

from __future__ import annotations

_scale_factor: float | None = None


def configure_high_dpi() -> None:
    """Call before creating QApplication."""
    import os
    import sys

    # Linux/VNC: high-DPI transforms often crash FreeType in QFontEngineFT::loadGlyphSet.
    if sys.platform.startswith("linux"):
        os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
        os.environ["QT_SCALE_FACTOR"] = "1"
        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
        os.environ.setdefault("QT_OPENGL", "software")
        os.environ.setdefault("QT_X11_NO_MITSHM", "1")
        os.environ.setdefault("QT_XCB_GL_INTEGRATION", "none")
        os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)
        return

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")


def apply_platform_font(app) -> None:
    """Use fonts that exist on the host; avoids XCB FreeType segfaults on Linux."""
    import sys

    from PyQt5.QtGui import QFont

    from nottcontrol.theme import APP_FONT_FAMILY

    font = QFont(APP_FONT_FAMILY, 10)
    if sys.platform.startswith("linux"):
        # Avoid subpixel/transformed glyph paths that crash under remote X.
        font.setStyleStrategy(
            QFont.PreferDefault
            | QFont.PreferQuality
            | QFont.NoSubpixelAntialias
        )
        try:
            font.setHintingPreference(QFont.PreferFullHinting)
        except Exception:
            pass
    app.setFont(font)


def init_ui_scale(app) -> None:
    """Record the primary screen scale factor after QApplication exists."""
    global _scale_factor
    screen = app.primaryScreen()
    if screen is None:
        _scale_factor = 1.0
        return
    dpi = screen.logicalDotsPerInch()
    # 96 DPI is the Qt / Windows logical baseline.
    _scale_factor = max(1.0, dpi / 96.0)


def ui_scale_factor() -> float:
    if _scale_factor is None:
        try:
            from PyQt5.QtWidgets import QApplication

            app = QApplication.instance()
            if app is not None:
                init_ui_scale(app)
            else:
                return 1.0
        except Exception:
            return 1.0
    return _scale_factor or 1.0


def scaled(value: int | float) -> int:
    return max(1, int(round(value * ui_scale_factor())))


def scaled_font_pt(base_pt: int | float) -> int:
    return max(1, int(round(base_pt)))


def cryo_temp_panel_height(
    tag_count: int, *, columns: int = 2, dense: bool = True
) -> int:
    """Minimum height for a cryostat temperature group box."""
    rows = max(1, (tag_count + columns - 1) // columns)
    row_h = scaled(20 if dense else 22)
    return scaled(38) + rows * row_h
