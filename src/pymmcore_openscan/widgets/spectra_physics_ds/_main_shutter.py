from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize
from qtpy.QtGui import QPalette
from qtpy.QtWidgets import QApplication
from superqt import QIconifyIcon

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

from pymmcore_plus.core import ShutterDevice

from ._utils import SafetyButton

DEVICE_NAME = "InsightDS+ Main"


class ShutterMainButton(SafetyButton):
    """Main shutter open/close button with a safety countdown."""

    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self._mmcore = mmcore or CMMCorePlus.instance()
        self._dev: ShutterDevice | None = None

        text_color = (
            QApplication.palette()
            .color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text)
            .name()
        )
        self.off_icon = QIconifyIcon(
            "material-symbols-light:camera-outline", color=text_color
        )
        self.on_icon = QIconifyIcon(
            "material-symbols-light:circle-outline", color=text_color
        )

        font = self.font()
        font.setPointSize(36)
        self.setFont(font)
        self.setIconSize(QSize(96, 96))
        self.setMinimumHeight(96)

        self.toggled.connect(self._on_toggled)
        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)
        self._try_enable()

    def _try_enable(self) -> None:
        enabled = DEVICE_NAME in self._mmcore.getLoadedDevices()
        self.setEnabled(enabled)
        if enabled:
            self._dev = self._mmcore.getDeviceObject(DEVICE_NAME, ShutterDevice)
        else:
            self._dev = None

    def _on_toggled(self, checked: bool) -> None:
        if self.isEnabled() and self._dev:
            if checked:
                self._dev.open()
            else:
                self._dev.close()
