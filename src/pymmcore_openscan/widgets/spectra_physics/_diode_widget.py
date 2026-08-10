"""Widgets displaying diode info."""

from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from ._utils import _DEVICE_NAME, _PollingWorker

_DIODE_PROPS = [
    (_DEVICE_NAME, f"Diode {i} {field}")
    for i in (1, 2)
    for field in ("Current (A)", "Temperature (C)", "Accumulated Hours")
]


class _DiodePanel(QGroupBox):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(title, parent)

        self._current = QLabel("N/A")
        self._temperature = QLabel("N/A")
        self._hours = QLabel("N/A")

        self._form_layout = QFormLayout(self)
        self._form_layout.addRow("Current:", self._current)
        self._form_layout.addRow("Temperature:", self._temperature)
        self._form_layout.addRow("Cumulative Hours:", self._hours)

    def refresh_visibility(self, mmcore: CMMCorePlus, device: str) -> bool:
        """Hide rows for unavailable properties. Returns True if any are available."""
        fields = [
            ("Current (A)", self._current),
            ("Temperature (C)", self._temperature),
            ("Accumulated Hours", self._hours),
        ]
        any_visible = False
        for field, widget in fields:
            visible = mmcore.hasProperty(device, f"{self.title()} {field}")
            if label := self._form_layout.labelForField(widget):
                label.setVisible(visible)
            widget.setVisible(visible)
            any_visible = any_visible or visible
        return any_visible

    def update_field(self, field: str, value: float) -> None:
        if field == "Current (A)":
            self._current.setText(f"{value:.3f} A")
        elif field == "Temperature (C)":
            self._temperature.setText(f"{value:.1f} °C")
        elif field == "Accumulated Hours":
            self._hours.setText(f"{value:.1f} h")


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

        layout = QHBoxLayout(self)
        layout.addWidget(self._diode1)
        layout.addWidget(self._diode2)

        self._worker = _PollingWorker(self._mmcore, _DIODE_PROPS)
        self._worker.updated.connect(self._on_updated)

        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)
        self._try_enable()

    def _try_enable(self) -> None:
        enabled = _DEVICE_NAME in self._mmcore.getLoadedDevices()
        self.setEnabled(enabled)
        if enabled:
            for panel in (self._diode1, self._diode2):
                panel.setVisible(panel.refresh_visibility(self._mmcore, _DEVICE_NAME))
            self._worker.start()
        else:
            self._worker.stop()

    def _on_updated(self, _: str, prop: str, value: str) -> None:
        for i, panel in enumerate((self._diode1, self._diode2), start=1):
            prefix = f"Diode {i} "
            if prop.startswith(prefix):
                panel.update_field(prop[len(prefix) :], float(value))
                break
