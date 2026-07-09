from __future__ import annotations

from pathlib import Path

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QByteArray, QRectF, QSize, Qt, QThread
from qtpy.QtGui import QPainter, QPalette, QPixmap
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import (
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
from superqt import QElidingLabel

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

_ASSETS = Path(__file__).parent / "_assets"
_ICON_ACTIVE_PATH = _ASSETS / "laser-symbol.svg"
_ICON_INACTIVE_PATH = _ASSETS / "laser-symbol-inactive.svg"
_ICON_SIZE = QSize(128, 128)


def _render_svg(data: bytes) -> QPixmap:
    pixmap = QPixmap(_ICON_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    renderer = QSvgRenderer(QByteArray(data))
    scaled = renderer.defaultSize().scaled(
        _ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio
    )
    x = (_ICON_SIZE.width() - scaled.width()) / 2
    y = (_ICON_SIZE.height() - scaled.height()) / 2
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(x, y, scaled.width(), scaled.height()))
    painter.end()
    return pixmap


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

        main_layout = QVBoxLayout(self)

        self._laser_state = QElidingLabel("N/A")

        laser_group = QGroupBox("Laser")
        laser_group.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
        )
        laser_group_layout = QVBoxLayout(laser_group)
        laser_form = QFormLayout()
        laser_form.addRow("State:", self._laser_state)
        laser_form.addRow("Power (W):", PowerBarWidget(mmcore=self._mmcore))
        laser_group_layout.addLayout(laser_form)
        laser_group_layout.addWidget(self.laser_button)
        main_layout.addWidget(laser_group, stretch=0)

        # Shutters group
        self._shutter_icon = QLabel()
        self._shutter_icon.setPixmap(self._inactive_laser_pixmap())

        shutter_group = QGroupBox("Shutters")
        shutter_layout = QGridLayout(shutter_group)
        shutter_layout.addWidget(
            self._shutter_icon, 2, 0, 1, 2, Qt.AlignmentFlag.AlignHCenter
        )
        shutter_layout.addWidget(QLabel("Main"), 0, 0, Qt.AlignmentFlag.AlignHCenter)
        shutter_layout.addWidget(self.main_shutter_button, 1, 0)
        shutter_layout.addWidget(QLabel("1040nm"), 0, 1, Qt.AlignmentFlag.AlignHCenter)
        shutter_layout.addWidget(self.shutter_1040_button, 1, 1)
        self.main_shutter_button.toggled.connect(self._update_shutter_icon)
        self.shutter_1040_button.toggled.connect(self._update_shutter_icon)
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

    def _inactive_laser_pixmap(self) -> QPixmap:
        color = self.palette().color(QPalette.ColorRole.Mid).name()
        data = _ICON_INACTIVE_PATH.read_bytes().replace(b"currentColor", color.encode())
        return _render_svg(data)

    def _update_shutter_icon(self) -> None:
        if self.main_shutter_button.isChecked() or self.shutter_1040_button.isChecked():
            self._shutter_icon.setPixmap(_render_svg(_ICON_ACTIVE_PATH.read_bytes()))
        else:
            self._shutter_icon.setPixmap(self._inactive_laser_pixmap())

    def _on_updated(self, _: str, prop: str, value: str) -> None:
        if prop == "Laser State":
            self._laser_state.setText(_state_text(int(value)))
