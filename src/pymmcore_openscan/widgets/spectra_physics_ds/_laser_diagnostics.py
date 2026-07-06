from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QThread
from qtpy.QtGui import QPalette
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt import QIconifyIcon

from ._diode_widget import DiodeWidget
from ._history_buffer import HistoryBufferPanel
from ._utils import _DEVICE_NAME, _PollingWorker

_HUMIDITY_WARNING_THRESHOLD = 5

_DIAG_PROPS = [
    (_DEVICE_NAME, "Warmup Percentage"),
    (_DEVICE_NAME, "Laser State"),
    (_DEVICE_NAME, "Relative Humidity"),
]


class LaserDiagnosticsPanel(QGroupBox):
    """Displays laser diagnostics."""

    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__("Laser Diagnostics", parent)
        self._mmcore = mmcore or CMMCorePlus.instance()

        self._warmup = QProgressBar()
        self._warmup.setRange(0, 100)
        self._warmup.setFormat("%v%")

        self._laser_state = QLineEdit()
        self._laser_state.setReadOnly(True)

        self._humidity = QSpinBox()
        self._humidity.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._humidity.setSuffix(" %")
        self._humidity.setReadOnly(True)
        self._humidity.setRange(0, 100)
        self._humidity_warning = QLabel()
        accent = (
            QApplication.palette()
            .color(QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight)
            .name()
        )
        self._humidity_warning.setPixmap(
            QIconifyIcon("mdi:warning-outline", color=accent).pixmap(24, 24)
        )
        self._humidity_warning.setToolTip("Humidity above 5% - check the purge unit!")
        self._humidity_warning.setVisible(False)
        humidity_row = QHBoxLayout()
        humidity_row.addWidget(self._humidity)
        humidity_row.addWidget(self._humidity_warning)
        humidity_row.addStretch()

        self._history = HistoryBufferPanel(mmcore=mmcore)

        self._diodes = DiodeWidget(mmcore=mmcore)

        form = QFormLayout()
        form.addRow("System Warmup:", self._warmup)
        form.addRow("Laser State:", self._laser_state)
        form.addRow("Humidity:", humidity_row)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._history)
        layout.addWidget(self._diodes)

        self._worker = _PollingWorker(self._mmcore, _DIAG_PROPS)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self._worker.updated.connect(self._on_updated)

        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)
        self._try_enable()

    def _try_enable(self) -> None:
        enabled = _DEVICE_NAME in self._mmcore.getLoadedDevices()
        self.setEnabled(enabled)
        if enabled:
            if not self._thread.isRunning():
                self._thread.start()
        else:
            self._worker.stop()
            self._thread.quit()
            self._thread.wait()

    def _on_updated(self, _: str, prop: str, value: str) -> None:
        if prop == "Warmup Percentage":
            self._warmup.setValue(int(value))
        elif prop == "Laser State":
            code = int(value)
            # Code map taken from Insight DS+ manual, Appendix A
            if 0 <= code and code < 25:
                state_text = "Initializing"
            elif code == 25:
                state_text = "Ready"
            elif 26 <= code and code < 50:
                state_text = "Turning On and/or Optimizing"
            elif code == 50:
                state_text = "Running"
            elif 51 <= code and code < 59:
                state_text = "Entering Align mode"
            elif code == 60:
                state_text = "In Align mode"
            elif 61 <= code and code < 69:
                state_text = "Exiting Align mode"
            else:
                state_text = "INVALID STATE"
            self._laser_state.setText(state_text)
        elif prop == "Relative Humidity":
            humidity = int(value)
            self._humidity.setValue(humidity)
            self._humidity_warning.setVisible(humidity > _HUMIDITY_WARNING_THRESHOLD)
