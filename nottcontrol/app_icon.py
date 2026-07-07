from __future__ import annotations

import struct
import sys
from pathlib import Path

from PyQt5.QtCore import QBuffer, QIODevice, Qt
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
WINDOWS_ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
WINDOWS_APP_ID = "org.nott.nottcontrol"


def assets_dir() -> Path:
    return Path(__file__).resolve().parent


def logo_path() -> Path:
    return assets_dir() / "NOTT.png"


def app_icon_path() -> Path:
    return assets_dir() / "NOTT_app_icon.png"


def macos_icns_path() -> Path:
    return assets_dir() / "macos" / "NOTT.icns"


def windows_ico_path() -> Path:
    return assets_dir() / "windows" / "NOTT.ico"


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
    if sys.platform == "win32":
        ico_path = windows_ico_path()
        if ico_path.exists():
            icon = QIcon(str(ico_path))
            if not icon.isNull():
                return icon

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


def _pixmap_png_bytes(pixmap: QPixmap) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(buffer.data())


def _write_png_ico(path: Path, images: list[tuple[int, bytes]]) -> None:
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)
    entries = bytearray()
    payload = bytearray()
    offset = 6 + 16 * count

    for size, png_data in images:
        width = size if size < 256 else 0
        height = width
        entries.extend(
            struct.pack(
                "<BBBBHHII",
                width,
                height,
                0,
                0,
                1,
                32,
                len(png_data),
                offset,
            )
        )
        payload.extend(png_data)
        offset += len(png_data)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + bytes(entries) + bytes(payload))


def save_app_icon_ico() -> Path:
    mark_source = QPixmap(str(logo_path()))
    mark = _sphere_mark(mark_source) if not mark_source.isNull() else None
    images: list[tuple[int, bytes]] = []
    for size in WINDOWS_ICO_SIZES:
        pixmap = render_app_icon_pixmap(size, mark)
        images.append((size, _pixmap_png_bytes(pixmap)))

    path = windows_ico_path()
    _write_png_ico(path, images)
    return path


def save_app_icon_png(size: int = 512) -> Path:
    pixmap = render_app_icon_pixmap(size)
    path = app_icon_path()
    pixmap.save(str(path), "PNG")
    return path


def _launcher_icon_path() -> Path:
    if sys.platform == "win32":
        ico_path = windows_ico_path()
        if ico_path.exists():
            return ico_path
    if sys.platform == "darwin":
        icns_path = macos_icns_path()
        if icns_path.exists():
            return icns_path
    png_path = app_icon_path()
    if png_path.exists():
        return png_path
    return save_app_icon_png()


def ensure_windows_app_identity() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            WINDOWS_APP_ID
        )
    except Exception:
        pass


def _set_macos_dock_icon(icon_path: Path) -> None:
    """Replace the Python dock icon when launched from a terminal."""
    try:
        from AppKit import NSApplication, NSImage
    except ImportError:
        return

    path = str(icon_path.resolve())
    image = NSImage.alloc().initWithContentsOfFile_(path)
    if image is not None:
        NSApplication.sharedApplication().setApplicationIconImage_(image)


def apply_platform_launcher_icon() -> None:
    if sys.platform == "darwin":
        _set_macos_dock_icon(_launcher_icon_path())


def apply_app_icon(app: QApplication) -> QIcon:
    ensure_windows_app_identity()
    icon = load_app_icon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    apply_platform_launcher_icon()
    return icon
