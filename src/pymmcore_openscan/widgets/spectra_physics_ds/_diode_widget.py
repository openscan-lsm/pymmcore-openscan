from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QThread
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QVBoxLayout,
    QWidget,
)

from ._utils import _DEVICE_NAME, _PollingWorker


class _DiodePanel(QGroupBox):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)

        self._current = QDoubleSpinBox()
        self._current.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._current.setSuffix(" Amps")
        self._temperature = QDoubleSpinBox()
        self._temperature.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._temperature.setSuffix(" Celsius")
        self._hours = QDoubleSpinBox()
        self._hours.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._hours.setSuffix(" Hours")

        for sb in (self._current, self._temperature, self._hours):
            sb.setReadOnly(True)

        layout = QFormLayout(self)
        layout.addRow("Current:", self._current)
        layout.addRow("Temperature:", self._temperature)
        layout.addRow("Cumulative Hours:", self._hours)

    def set_enabled(self, enabled: bool) -> None:
        for sb in (self._current, self._temperature, self._hours):
            sb.setEnabled(enabled)

    def update_values(self, current: float, temp: float, hours: float) -> None:
        self._current.setValue(current)
        self._temperature.setValue(temp)
        self._hours.setValue(hours)


class DiodeWidget(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self._mmcore = mmcore or CMMCorePlus.instance()

        self._diode1 = _DiodePanel("Diode 1")
        self._diode2 = _DiodePanel("Diode 2")

        layout = QVBoxLayout(self)
        layout.addWidget(self._diode1)
        layout.addWidget(self._diode2)

        self._worker = _PollingWorker(self._mmcore)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.start)
        self._worker.updated.connect(self._on_updated)

        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)
        self._try_enable()

    def _try_enable(self) -> None:
        enabled = _DEVICE_NAME in self._mmcore.getLoadedDevices()
        self._diode1.set_enabled(enabled)
        self._diode2.set_enabled(enabled)
        if enabled:
            self._thread.start()
        else:
            self._worker.stop()
            self._thread.quit()
            self._thread.wait()

    def _on_updated(self, idx: int, current: float, temp: float, hours: float) -> None:
        panel = self._diode1 if idx == 1 else self._diode2
        panel.update_values(current, temp, hours)
