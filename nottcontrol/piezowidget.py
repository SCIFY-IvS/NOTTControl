from PyQt5.QtWidgets import QWidget
from PyQt5.uic import loadUi

from nottcontrol.components.pypiezo import piezointerface


class PiezoWidget(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

    def setup(self, piezo_interf: piezointerface, channel_index: int, name: str):
        self._interf = piezo_interf
        self._index = channel_index
        self._enabled = piezo_interf is not None and piezo_interf.ser is not None

        self.ui = loadUi("piezo_widget.ui", self)
        self.ui.label_name.setText(name)

        self.ui.pb_move_abs.clicked.connect(self.move_abs)
        self.ui.pb_move_rel_pos.clicked.connect(self.move_rel_pos)
        self.ui.pb_move_rel_neg.clicked.connect(self.move_rel_neg)

        if not self._enabled:
            self.ui.label_error.setText("Serial interface unavailable")
            for widget in (
                self.ui.pb_move_abs,
                self.ui.pb_move_rel_pos,
                self.ui.pb_move_rel_neg,
                self.ui.lineEdit_abs_pos,
                self.ui.lineEdit_rel_pos,
            ):
                widget.setEnabled(False)

    def refresh_position(self):
        if not self._enabled:
            return
        try:
            position = float(self._interf.values[self._index])
            self.ui.label_current_position.setText(f"{position:.2f}")
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
