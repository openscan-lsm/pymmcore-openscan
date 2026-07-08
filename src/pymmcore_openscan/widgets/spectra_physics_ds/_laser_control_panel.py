from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QThread
from qtpy.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ._laser_button import LaserButton
from ._power_bar import PowerBarWidget
from ._shutter_button import ShutterButton
from ._utils import (
    _DEVICE_NAME,
    _MAIN_SHUTTER_DEVICE,
    _SHUTTER_1040_DEVICE,
    _PollingWorker,
)
from ._wavelength_widget import WavelengthWidget

_STATE_PROPS = [(_DEVICE_NAME, "Laser State")]


def _state_text(code: int) -> str:
    if code < 25:
        return "Initializing"
    if code == 25:
        return "Ready"
    if code < 50:
        return "Turning On and/or Optimizing"
    if code == 50:
        return "Running"
    if code < 59:
        return "Entering Align mode"
    if code == 60:
        return "In Align mode"
    if code < 69:
        return "Exiting Align mode"
    return "INVALID STATE"


class LaserControlPanel(QWidget):
    """Combined panel with laser power, main shutter, and 1040nm shutter controls."""

    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent)
        self._mmcore = mmcore or CMMCorePlus.instance()

        self.laser_button = LaserButton(mmcore=self._mmcore)
        self.main_shutter_button = ShutterButton(
            _MAIN_SHUTTER_DEVICE, mmcore=self._mmcore
        )
        self.shutter_1040_button = ShutterButton(
            _SHUTTER_1040_DEVICE, mmcore=self._mmcore
        )

        expand = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        for btn in (
            self.laser_button,
            self.main_shutter_button,
            self.shutter_1040_button,
        ):
            btn.setSizePolicy(expand)

        main_layout = QVBoxLayout(self)

        self._laser_state = QLabel("N/A")

        laser_group = QGroupBox("Laser")
        laser_group_layout = QVBoxLayout(laser_group)
        laser_form = QFormLayout()
        laser_form.addRow("State:", self._laser_state)
        laser_form.addRow("Power (W):", PowerBarWidget(mmcore=self._mmcore))
        laser_group_layout.addLayout(laser_form)
        laser_group_layout.addWidget(self.laser_button)
        main_layout.addWidget(laser_group)

        # Shutters group
        shutter_group = QGroupBox("Shutters")
        shutter_layout = QHBoxLayout(shutter_group)
        for label_text, btn in (
            ("Main", self.main_shutter_button),
            ("1040nm", self.shutter_1040_button),
        ):
            col = QVBoxLayout()
            col.addWidget(QLabel(label_text))
            col.addWidget(btn)
            shutter_layout.addLayout(col)
        main_layout.addWidget(shutter_group)

        # Wavelength group
        wavelength_group = QGroupBox("Wavelength")
        wavelength_group_layout = QVBoxLayout(wavelength_group)
        wavelength_group_layout.addWidget(WavelengthWidget(mmcore=self._mmcore))
        main_layout.addWidget(wavelength_group)

        self._worker = _PollingWorker(self._mmcore, _STATE_PROPS)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._worker.updated.connect(self._on_updated)

        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)
        self._try_enable()

    def _try_enable(self) -> None:
        enabled = _DEVICE_NAME in self._mmcore.getLoadedDevices()
        if not enabled:
            self._laser_state.setText("N/A")
        if enabled:
            if not self._thread.isRunning():
                self._thread.start()
                self._worker.start()
        else:
            self._worker.stop()
            self._thread.quit()
            self._thread.wait()

    def _on_updated(self, _: str, prop: str, value: str) -> None:
        if prop == "Laser State":
            self._laser_state.setText(_state_text(int(value)))
