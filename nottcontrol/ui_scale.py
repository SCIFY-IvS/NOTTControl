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
        os.environ["QT_SCREEN_SCALE_FACTORS"] = "1"
        os.environ["QT_FONT_DPI"] = "96"
        # Obsolete but still honored by some conda Qt5 builds.
        os.environ["QT_DEVICE_PIXEL_RATIO"] = "1"
        os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
        os.environ.setdefault("QT_OPENGL", "software")
        os.environ.setdefault("QT_X11_NO_MITSHM", "1")
        os.environ.setdefault("QT_XCB_GL_INTEGRATION", "none")
        os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)
        return

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")


def _pick_linux_font_family(preferred: str, fallbacks: tuple[str, ...]) -> str:
    from PyQt5.QtGui import QFontDatabase

    families = set(QFontDatabase().families())
    for name in (preferred, *fallbacks):
        if name in families:
            return name
    # Last resort: Qt default; PreferBitmap path still avoids many crashes.
    return QFontDatabase().families()[0] if families else preferred


def apply_platform_font(app) -> None:
    """Use fonts that exist on the host; avoids XCB FreeType segfaults on Linux."""
    import sys

    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import QStyleFactory

    from nottcontrol import theme

    if not sys.platform.startswith("linux"):
        app.setFont(QFont(theme.APP_FONT_FAMILY, 10))
        return

    # Ignore X11/VNC DPI (fractional transforms → QFontEngineFT SIGSEGV).
    try:
        app.setDesktopSettingsAware(False)
    except Exception:
        pass
    if "Fusion" in QStyleFactory.keys():
        app.setStyle("Fusion")

    family = _pick_linux_font_family(
        theme.APP_FONT_FAMILY,
        ("Noto Sans", "Liberation Sans", "FreeSans", "Ubuntu", "Cantarell", "Sans Serif"),
    )
    mono = _pick_linux_font_family(
        theme.APP_MONO_FAMILY,
        (
            "DejaVu Sans Mono",
            "Noto Sans Mono",
            "Liberation Mono",
            "FreeMono",
            "Ubuntu Mono",
            "Monospace",
        ),
    )
    theme.APP_FONT_FAMILY = family
    theme.APP_MONO_FAMILY = mono
    theme.FONT = f'"{family}", sans-serif'
    theme.MONO_FONT = f'"{mono}", monospace'

    # Pixel size avoids point→DPI glyph transforms in QFontEngineFT::loadGlyphSet.
    font = QFont(family)
    font.setPixelSize(13)
    font.setStyleStrategy(
        QFont.PreferBitmap
        | QFont.PreferQuality
        | QFont.NoAntialias
        | QFont.NoSubpixelAntialias
        | QFont.NoFontMerging
    )
    try:
        font.setHintingPreference(QFont.PreferFullHinting)
    except Exception:
        pass
    app.setFont(font)
    print(f"NOTTControl Linux UI font: {family} (mono={mono}, pixelSize=13)")
    patch_linux_lineedit_paint()


def patch_linux_lineedit_paint() -> None:
    """Bypass QWidgetLineControl/FreeType path that SIGSEGVs under conda Qt+VNC."""
    import sys

    if not sys.platform.startswith("linux"):
        return

    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QColor, QFontMetrics, QPainter
    from PyQt5.QtWidgets import QLineEdit

    def _safe_paint(self, event) -> None:  # noqa: ANN001
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), self.palette().brush(self.backgroundRole()))
            painter.setFont(self.font())
            text = self.text()
            if self.echoMode() != QLineEdit.Normal:
                text = "*" * len(text)
            content = self.rect().adjusted(6, 0, -6, 0)
            fg = self.palette().color(self.foregroundRole())

            if self.hasFocus() and self.hasSelectedText() and text:
                try:
                    start = max(0, int(self.selectionStart()))
                    selected = self.selectedText()
                    if selected:
                        fm = QFontMetrics(self.font())
                        before = text[:start]
                        align = int(self.alignment())
                        text_w = fm.horizontalAdvance(text)
                        before_w = fm.horizontalAdvance(before)
                        if align & int(Qt.AlignRight):
                            x0 = content.right() - text_w + before_w
                        elif align & int(Qt.AlignHCenter):
                            x0 = content.left() + (content.width() - text_w) // 2 + before_w
                        else:
                            x0 = content.left() + before_w
                        sel_w = max(1, fm.horizontalAdvance(selected))
                        sel_rect = content.adjusted(0, 2, 0, -2)
                        sel_rect.setLeft(int(x0))
                        sel_rect.setWidth(int(sel_w))
                        painter.fillRect(sel_rect, QColor(50, 129, 140, 90))
                except Exception:
                    pass

            painter.setPen(fg)
            painter.drawText(content, int(self.alignment()) | Qt.AlignVCenter, text)

            # Stock paint drew the caret; without it focused fields look dead.
            if self.hasFocus() and not self.isReadOnly():
                try:
                    caret = self.cursorRect()
                    if caret.isValid():
                        bar = caret.adjusted(0, 2, 0, -2)
                        if bar.width() < 2:
                            bar.setWidth(2)
                        painter.fillRect(bar, fg)
                except Exception:
                    pass
        finally:
            painter.end()

    QLineEdit.paintEvent = _safe_paint  # type: ignore[method-assign]
    print("NOTTControl Linux: using safe QLineEdit paint (avoid FreeType crash)")


def init_ui_scale(app) -> None:
    """Record the primary screen scale factor after QApplication exists."""
    import sys

    global _scale_factor
    if sys.platform.startswith("linux"):
        # Keep UI math at 1.0; VNC DPI reports are often wrong/fractional.
        _scale_factor = 1.0
        return
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
