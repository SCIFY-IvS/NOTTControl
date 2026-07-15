"""UI scaling helpers for high-DPI displays (e.g. Windows 125–150 % scaling)."""

from __future__ import annotations

_scale_factor: float | None = None


def configure_high_dpi() -> None:
    """Call before creating QApplication."""
    import os

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")


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
