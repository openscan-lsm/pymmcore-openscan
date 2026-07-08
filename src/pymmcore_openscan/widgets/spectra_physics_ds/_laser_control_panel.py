from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, QThread
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


class LaserControlPanel(QGroupBox):
    """Combined panel with laser power, main shutter, and 1040nm shutter controls."""

    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__("Laser Control", parent)
        self._mmcore = mmcore or CMMCorePlus.instance()

        self._laser_state = QLabel("N/A")

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

        state_form = QFormLayout()
        state_form.addRow("Laser State:", self._laser_state)
        main_layout.addLayout(state_form)

        power_bar = PowerBarWidget(mmcore=self._mmcore)
        main_layout.addWidget(power_bar)

        # Laser enable button
        laser_row = QHBoxLayout()
        laser_label = QLabel("Pump Laser")
        laser_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        laser_row.addWidget(laser_label)
        laser_row.addWidget(self.laser_button, stretch=1)
        main_layout.addLayout(laser_row)

        # Two shutters in a labelled box
        shutter_box = QGroupBox("Shutters")
        shutter_layout = QHBoxLayout(shutter_box)
        for label_text, btn in (
            ("Main Shutter", self.main_shutter_button),
            ("1040nm Shutter", self.shutter_1040_button),
        ):
            col = QVBoxLayout()
            col.addWidget(QLabel(label_text))
            col.addWidget(btn)
            shutter_layout.addLayout(col)

        main_layout.addWidget(shutter_box)

        self._worker = _PollingWorker(self._mmcore, _STATE_PROPS)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._worker.updated.connect(self._on_updated)

        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)
        self._try_enable()

    def _try_enable(self) -> None:
        enabled = _DEVICE_NAME in self._mmcore.getLoadedDevices()
        self._laser_state.setEnabled(enabled)
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
