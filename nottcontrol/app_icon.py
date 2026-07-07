from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)
from PyQt5.QtWidgets import QApplication

TEAL = QColor(50, 129, 140)
TEAL_DARK = QColor(18, 48, 54)
TEAL_LIGHT = QColor(72, 164, 176)
ICON_SIZES = (16, 32, 48, 64, 128, 256, 512)


def assets_dir() -> Path:
    return Path(__file__).resolve().parent


def logo_path() -> Path:
    return assets_dir() / "NOTT.png"


def app_icon_path() -> Path:
    return assets_dir() / "NOTT_app_icon.png"


def _sphere_mark(source: QPixmap) -> QPixmap:
    """Crop the NOTT eclipse mark without the surrounding wordmark letters."""
    side = max(1, int(source.height() * 0.68))
    center_x = int(source.width() * 0.39)
    x = max(0, center_x - side // 2)
    width = min(side, source.width() - x)
    return source.copy(x, 0, width, source.height())


def render_app_icon_pixmap(size: int, mark: QPixmap | None = None) -> QPixmap:
    if mark is None:
        source = QPixmap(str(logo_path()))
        if source.isNull():
            return QPixmap()
        mark = _sphere_mark(source)

    canvas = QPixmap(size, size)
    canvas.fill(Qt.transparent)

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)

    inset = max(1, int(size * 0.05))
    radius = int(size * 0.2)
    rect = inset, inset, size - 2 * inset, size - 2 * inset

    gradient = QLinearGradient(0, 0, 0, size)
    gradient.setColorAt(0.0, TEAL_LIGHT)
    gradient.setColorAt(0.55, TEAL)
    gradient.setColorAt(1.0, TEAL_DARK)
    painter.setBrush(gradient)
    painter.setPen(QPen(QColor(255, 255, 255, 90), max(1, size // 128)))
    painter.drawRoundedRect(*rect, radius, radius)

    inner = int(size * 0.74)
    scaled = mark.scaled(
        inner,
        inner,
        Qt.KeepAspectRatio,
        Qt.SmoothTransformation,
    )
    painter.drawPixmap(
        (size - scaled.width()) // 2,
        (size - scaled.height()) // 2,
        scaled,
    )
    painter.end()
    return canvas


def load_app_icon() -> QIcon:
    icon_path = app_icon_path()
    if icon_path.exists():
        icon = QIcon(str(icon_path))
        if not icon.isNull():
            return icon

    source = QPixmap(str(logo_path()))
    if source.isNull():
        return QIcon()

    mark = _sphere_mark(source)
    icon = QIcon()
    for size in ICON_SIZES:
        icon.addPixmap(render_app_icon_pixmap(size, mark))
    return icon


def save_app_icon_png(size: int = 512) -> Path:
    pixmap = render_app_icon_pixmap(size)
    path = app_icon_path()
    pixmap.save(str(path), "PNG")
    return path


def apply_app_icon(app: QApplication) -> QIcon:
    icon = load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    return icon
