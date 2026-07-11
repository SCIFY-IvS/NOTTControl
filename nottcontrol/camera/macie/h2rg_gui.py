from __future__ import annotations

import os
import threading
from pathlib import Path

import numpy
import pyqtgraph as pg
from astropy.io import fits
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QMessageBox
from PyQt5.uic import loadUi

from nottcontrol import config
from nottcontrol.camera.macie.macie_interface import DetectorMode, MacieInterface
from nottcontrol.camera.macie.zmq_server_manager import MacieZmqServerProcess

MACIE_CONFIG_FILE = config.get(
    "MACIE", "config_file", fallback="basic_warm_slow.cfg"
)
MACIE_ZMQ_ADDRESS = config.get(
    "MACIE", "zmq_address", fallback="tcp://localhost:65534"
)
MACIE_OFFLINE_MODE = config.getboolean("MACIE", "offline_mode", fallback=False)
MACIE_IMAGE_SCALE = config.getint("MACIE", "image_display_scale", fallback=2)


def macie_config_path(config_name: str) -> Path:
    base = Path(__file__).resolve().parent / "macie_exe" / "config_files"
    return base / config_name


def parse_macie_save_dir(config_path: Path) -> Path:
    save_dir: str | None = None
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("saveDir"):
            parts = stripped.split(maxsplit=1)
            if len(parts) == 2:
                save_dir = parts[1].strip()
            break
    if save_dir is None:
        return Path.home() / "test_data"
    return Path(os.path.expanduser(save_dir))


def newest_fits_file(directory: Path) -> Path | None:
    if not directory.is_dir():
        return None
    candidates = [
        *directory.glob("*.fits"),
        *directory.glob("*.FITS"),
        *directory.glob("**/*.fits"),
        *directory.glob("**/*.FITS"),
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_fits_image(filepath: Path) -> numpy.ndarray:
    with fits.open(filepath, memmap=False) as hdul:
        data = numpy.asarray(hdul[0].data, dtype=numpy.float32)
    while data.ndim > 2:
        data = data[0]
    return data


class H2rgMainWindow(QMainWindow):
    closing = pyqtSignal()
    frame_ready = pyqtSignal(object)
    operation_failed = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    controls_enabled = pyqtSignal(bool)
    readouts_updated = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self.ui = loadUi("camera/macie/ui/MacieControl.ui", self)
        self.setWindowTitle("H2RG / MACIE")

        pg.setConfigOptions(imageAxisOrder="row-major")
        pg.setConfigOption("background", "w")
        pg.setConfigOption("foreground", "k")

        self._config_path = macie_config_path(MACIE_CONFIG_FILE)
        self._save_dir = parse_macie_save_dir(self._config_path)
        self._macie: MacieInterface | None = None
        self._live_active = False
        self._background: numpy.ndarray | None = None
        self._last_fits_mtime = 0.0
        self._operation_lock = threading.Lock()
        self._zmq_server = MacieZmqServerProcess(MACIE_ZMQ_ADDRESS)

        self._setup_image_view()
        self._populate_comboboxes()
        self._connect_signals()
        self._set_status("Not connected")
        self._set_controls_enabled(False)
        self.ui.checkBox_substract_background.setEnabled(False)

        self.frame_ready.connect(self._display_frame, Qt.QueuedConnection)
        self.operation_failed.connect(self._on_operation_failed, Qt.QueuedConnection)
        self.status_updated.connect(self._set_status, Qt.QueuedConnection)
        self.controls_enabled.connect(self._set_controls_enabled, Qt.QueuedConnection)
        self.readouts_updated.connect(self._apply_readouts, Qt.QueuedConnection)

        threading.Thread(target=self._ensure_zmq_server, daemon=True).start()

    def _ensure_zmq_server(self) -> None:
        try:
            self._zmq_server.ensure_running()
            if self._zmq_server.started_by_gui:
                self.status_updated.emit("ZMQ server started")
            else:
                self.status_updated.emit(
                    f"Connected to ZMQ server at {MACIE_ZMQ_ADDRESS}"
                )
        except Exception as exc:
            self.operation_failed.emit(str(exc))

    def _setup_image_view(self) -> None:
        self.image = pg.ImageView(self.ui.frame_camera)
        self.image.ui.histogram.hide()
        self.image.ui.roiBtn.hide()
        self.image.ui.menuBtn.hide()
        self.image.setGeometry(0, 0, self.ui.frame_camera.width(), self.ui.frame_camera.height())
        self.image.show()
        self.image.getView().setAspectLocked(True)

    def _populate_comboboxes(self) -> None:
        self.ui.comboBox_detector_mode.clear()
        self.ui.comboBox_detector_mode.addItems(["Slow", "Fast"])
        self.ui.comboBox_window_mode.clear()
        self.ui.comboBox_window_mode.addItems(["Full frame", "Windowed"])

    def _connect_signals(self) -> None:
        self.ui.button_init.clicked.connect(self.init_camera)
        self.ui.button_powerOn.clicked.connect(self.power_on)
        self.ui.button_powerOff.clicked.connect(self.power_off)
        self.ui.button_take_background.clicked.connect(self.take_background)
        self.ui.button_live.clicked.connect(self.live_clicked)
        self.ui.button_acquire.clicked.connect(self.acquire)
        self.ui.button_halt.clicked.connect(self.halt)

        for widget in (
            self.ui.lineEdit_integration_time,
            self.ui.lineEdit_nb_coadd,
            self.ui.lineEdit_nb_frames,
        ):
            widget.editingFinished.connect(self._update_total_integration_label)

    def _set_status(self, message: str) -> None:
        self.ui.lineEdit_status.setText(message)

    def _set_controls_enabled(self, enabled: bool) -> None:
        for name in (
            "button_powerOn",
            "button_powerOff",
            "button_take_background",
            "button_live",
            "button_acquire",
            "button_halt",
        ):
            getattr(self.ui, name).setEnabled(enabled)

    def _on_operation_failed(self, message: str) -> None:
        self._set_status(message)
        QMessageBox.warning(self, "H2RG", message)

    def _ensure_macie(self) -> MacieInterface:
        if self._macie is None:
            self._macie = MacieInterface(
                offline_mode=MACIE_OFFLINE_MODE,
                config_file=MACIE_CONFIG_FILE,
                zmq_address=MACIE_ZMQ_ADDRESS,
            )
        return self._macie

    def _run_macie_operation(self, label: str, operation) -> None:
        def worker() -> None:
            try:
                with self._operation_lock:
                    operation()
            except Exception as exc:
                self.operation_failed.emit(f"{label} failed: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def init_camera(self) -> None:
        def operation() -> None:
            macie = self._ensure_macie()
            macie.init_camera()
            self._refresh_readouts(macie)
            self.status_updated.emit("Initialized")
            self.controls_enabled.emit(True)

        self._run_macie_operation("Init", operation)

    def power_on(self) -> None:
        self._run_macie_operation("Power on", lambda: self._ensure_macie().power_on())

    def power_off(self) -> None:
        self._run_macie_operation("Power off", lambda: self._ensure_macie().power_off())

    def _apply_exposure_settings(self, macie: MacieInterface) -> None:
        (
            save,
            ncoadds,
            nseq,
            ngroups,
            nreads,
            ndrops,
            nresets,
        ) = macie.read_exposure_settings()

        try:
            if self.ui.lineEdit_nb_coadd.text().strip():
                ncoadds = int(self.ui.lineEdit_nb_coadd.text())
            if self.ui.lineEdit_nb_frames.text().strip():
                nseq = int(self.ui.lineEdit_nb_frames.text())
        except ValueError as exc:
            raise ValueError(f"Invalid exposure field: {exc}") from exc

        macie.exposure_settings(save, ncoadds, nseq, ngroups, nreads, ndrops, nresets)
        self._update_total_integration_label()

    def acquire(self) -> None:
        def operation() -> None:
            macie = self._ensure_macie()
            self._apply_exposure_settings(macie)
            before_mtime = self._latest_fits_mtime()
            macie.acquire()
            frame = self._wait_for_new_frame(before_mtime)
            if frame is not None:
                self.frame_ready.emit(frame)
            self.status_updated.emit("Acquire complete")

        self._run_macie_operation("Acquire", operation)

    def live_clicked(self) -> None:
        if self._macie is None:
            self._on_operation_failed("Initialize the detector first")
            return
        if self._live_active:
            self._macie.stop_continuous_acquisition()
            self._live_active = False
            self.ui.button_live.setText("Live")
            self._set_status("Live stopped")
            return

        self._live_active = True
        self.ui.button_live.setText("Stop live")
        self._set_status("Live acquiring…")
        self._macie.start_continuous_acquisition()

        def poll_frames() -> None:
            import time

            while self._live_active and self._macie is not None:
                frame = self._load_latest_frame()
                if frame is not None:
                    self.frame_ready.emit(frame)
                time.sleep(0.5)

        threading.Thread(target=poll_frames, daemon=True).start()

    def halt(self) -> None:
        if self._live_active and self._macie is not None:
            self._macie.stop_continuous_acquisition()
            self._live_active = False
            self.ui.button_live.setText("Live")

        if self._macie is not None:
            self._run_macie_operation("Halt", self._macie.halt_acquisition)
        self._set_status("Halted")

    def take_background(self) -> None:
        frame = self._load_latest_frame()
        if frame is None:
            self._on_operation_failed("No FITS frame available for background")
            return
        self._background = frame.copy()
        self.ui.checkBox_substract_background.setEnabled(True)
        self._set_status("Background stored")

    def _refresh_readouts(self, macie: MacieInterface) -> None:
        mode = macie.get_detector_mode()
        x_window, y_window, x1, x2, y1, y2 = macie.read_frame_settings()
        (
            _save,
            ncoadds,
            nseq,
            _ngroups,
            nreads,
            _ndrops,
            _nresets,
        ) = macie.read_exposure_settings()
        self.readouts_updated.emit(
            {
                "mode_index": 0 if mode == DetectorMode.SLOW else 1,
                "windowed": x_window or y_window,
                "window_status": f"Window x=[{x1},{x2}] y=[{y1},{y2}]",
                "ncoadds": str(ncoadds),
                "nseq": str(nseq),
                "nreads": str(nreads) if nreads else "",
            }
        )

    def _apply_readouts(self, data: dict) -> None:
        self.ui.comboBox_detector_mode.setCurrentIndex(data["mode_index"])
        self.ui.comboBox_window_mode.setCurrentIndex(1 if data["windowed"] else 0)
        if data["windowed"]:
            self._set_status(data["window_status"])
        self.ui.lineEdit_nb_coadd.setText(data["ncoadds"])
        self.ui.lineEdit_nb_frames.setText(data["nseq"])
        if data["nreads"]:
            self.ui.lineEdit_integration_time.setText(data["nreads"])
        self._update_total_integration_label()

    def _update_total_integration_label(self) -> None:
        try:
            per_frame = float(self.ui.lineEdit_integration_time.text() or 0)
            coadds = int(self.ui.lineEdit_nb_coadd.text() or 1)
            frames = int(self.ui.lineEdit_nb_frames.text() or 1)
            total = per_frame * coadds * frames
            self.ui.lineEdit_integration_time_total.setText(f"{total:g}")
        except ValueError:
            self.ui.lineEdit_integration_time_total.setText("—")

    def _latest_fits_mtime(self) -> float:
        path = newest_fits_file(self._save_dir)
        if path is None:
            return 0.0
        return path.stat().st_mtime

    def _wait_for_new_frame(
        self, before_mtime: float, timeout_s: float = 30.0
    ) -> numpy.ndarray | None:
        import time

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            path = newest_fits_file(self._save_dir)
            if path is not None and path.stat().st_mtime > before_mtime:
                return load_fits_image(path)
            time.sleep(0.2)
        return self._load_latest_frame()

    def _load_latest_frame(self) -> numpy.ndarray | None:
        path = newest_fits_file(self._save_dir)
        if path is None:
            return None
        mtime = path.stat().st_mtime
        if mtime == self._last_fits_mtime:
            return None
        self._last_fits_mtime = mtime
        return load_fits_image(path)

    def _display_frame(self, frame: numpy.ndarray) -> None:
        display = frame
        if (
            self.ui.checkBox_substract_background.isChecked()
            and self._background is not None
            and self._background.shape == frame.shape
        ):
            display = frame - self._background

        self.image.getImageItem().setImage(display, autoLevels=False)
        path = newest_fits_file(self._save_dir)
        if path is not None:
            self.ui.lineEdit_frame_nb.setText(path.name)

    def get_dashboard_status(self) -> dict[str, object]:
        powered = None
        if self._macie is not None:
            try:
                powered = self._macie.get_power()
            except Exception:
                powered = None
        return {
            "connected": self._macie is not None,
            "live": self._live_active,
            "powered": powered,
            "save_dir": str(self._save_dir),
        }

    def closeEvent(self, event) -> None:
        if self._macie is not None:
            if self._live_active:
                self._macie.stop_continuous_acquisition()
            try:
                self._macie.close()
            except Exception:
                pass
            self._macie = None
        self._zmq_server.stop()
        self.closing.emit()
        super().closeEvent(event)
