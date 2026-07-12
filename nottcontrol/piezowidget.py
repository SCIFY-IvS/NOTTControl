import time

import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QWidget
from PyQt5.uic import loadUi

from nottcontrol import config
from nottcontrol.components.pypiezo import piezointerface
from nottcontrol.theme import style_piezo_widget


class PiezoScanWorker(QThread):
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self,
        piezo_interf: piezointerface,
        channel_index: int,
        amplitude_um: float,
        steps: int,
        step_delay_s: float,
    ):
        super().__init__()
        self._interf = piezo_interf
        self._channel_index = channel_index
        self._amplitude_um = amplitude_um
        self._steps = steps
        self._step_delay_s = step_delay_s

    def run(self):
        try:
            center = float(self._interf.values[self._channel_index])
            positions = np.linspace(
                center - self._amplitude_um,
                center + self._amplitude_um,
                self._steps,
            )
            sweep = np.concatenate([positions, positions[-2::-1]])
            for position in sweep:
                values = self._interf.values.copy()
                values[self._channel_index] = position
                self._interf.send(values)
                time.sleep(self._step_delay_s)

            values = self._interf.values.copy()
            values[self._channel_index] = center
            self._interf.send(values)
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


class PiezoWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._scan_worker: PiezoScanWorker | None = None

    def setup(
        self,
        piezo_interf: piezointerface,
        channel_index: int,
        name: str,
        port: str | None = None,
    ):
        self._interf = piezo_interf
        self._index = channel_index
        self._enabled = piezo_interf is not None and piezo_interf.ser is not None
        self._scan_steps = config.getint("PIEZO", "scan_steps", fallback=50)
        self._scan_step_delay_s = config.getfloat(
            "PIEZO", "scan_step_delay_s", fallback=0.05
        )

        self.ui = loadUi("piezo_widget.ui", self)
        style_piezo_widget(self)
        self.ui.label_name.setText(name)

        self.ui.pb_move_abs.clicked.connect(self.move_abs)
        self.ui.pb_move_rel_pos.clicked.connect(self.move_rel_pos)
        self.ui.pb_move_rel_neg.clicked.connect(self.move_rel_neg)
        self.ui.pb_scan.clicked.connect(self.scan_piezo)

        if not self._enabled:
            port_hint = f" ({port})" if port else ""
            self.ui.label_error.setText(
                f"Serial interface unavailable{port_hint}. "
                "Connect the controller and check [PIEZO] port in config.ini."
            )
            for widget in (
                self.ui.pb_move_abs,
                self.ui.pb_move_rel_pos,
                self.ui.pb_move_rel_neg,
                self.ui.pb_scan,
                self.ui.lineEdit_abs_pos,
                self.ui.lineEdit_rel_pos,
                self.ui.lineEdit_scan_amplitude,
            ):
                widget.setEnabled(False)

    def _set_scan_enabled(self, enabled: bool) -> None:
        for widget in (
            self.ui.pb_scan,
            self.ui.pb_move_abs,
            self.ui.pb_move_rel_pos,
            self.ui.pb_move_rel_neg,
            self.ui.lineEdit_abs_pos,
            self.ui.lineEdit_rel_pos,
            self.ui.lineEdit_scan_amplitude,
        ):
            widget.setEnabled(enabled and self._enabled)

    def scan_piezo(self):
        if not self._enabled or self._scan_worker is not None:
            return
        try:
            amplitude_um = float(self.ui.lineEdit_scan_amplitude.text())
            if amplitude_um <= 0:
                raise ValueError("Scan amplitude must be positive")
        except Exception as exc:
            self.ui.label_error.setText(str(exc))
            return

        self.ui.label_error.clear()
        self._set_scan_enabled(False)
        self._scan_worker = PiezoScanWorker(
            self._interf,
            self._index,
            amplitude_um,
            self._scan_steps,
            self._scan_step_delay_s,
        )
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.error.connect(self._on_scan_error)
        self._scan_worker.start()

    def _on_scan_finished(self):
        self._scan_worker = None
        self._set_scan_enabled(True)
        self.refresh_position()

    def _on_scan_error(self, message: str):
        self._scan_worker = None
        self._set_scan_enabled(True)
        self.ui.label_error.setText(message)

    def refresh_position(self):
        if not self._enabled:
            return
        try:
            position = float(self._interf.values[self._index])
            self.ui.label_current_position.setText(f"{position:.2f}")
            if self._scan_worker is None:
                self.ui.label_error.clear()
        except Exception as e:
            self.ui.label_error.setText(str(e))

    def move_abs(self):
        if not self._enabled:
            return
        try:
            position = float(self.ui.lineEdit_abs_pos.text())
            values = self._interf.values.copy()
            values[self._index] = position
            self._interf.send(values)
            self.refresh_position()
        except Exception as e:
            self.ui.label_error.setText(str(e))

    def move_rel(self, sign: float):
        if not self._enabled:
            return
        try:
            delta = sign * float(self.ui.lineEdit_rel_pos.text())
            values = self._interf.values.copy()
            values[self._index] += delta
            self._interf.send(values)
            self.refresh_position()
        except Exception as e:
            self.ui.label_error.setText(str(e))

    def move_rel_pos(self):
        self.move_rel(1.0)

    def move_rel_neg(self):
        self.move_rel(-1.0)
