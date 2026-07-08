from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus, Device
from qtpy.QtCore import QSize
from superqt import QIconifyIcon

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

from ._utils import _DEVICE_NAME, SafetyButton


class LaserButton(SafetyButton):
    """Laser enable/disable button with a safety countdown."""

    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self._mmcore = mmcore or CMMCorePlus.instance()
        self._dev: Device | None = None

        self.on_icon = QIconifyIcon("game-icons:laser-warning", color="yellow")
        self.off_text = "Off"

        font = self.font()
        font.setPointSize(36)
        self.setFont(font)
        self.setIconSize(QSize(96, 96))
        self.setMinimumHeight(96)
        self.setStyleSheet("""
            QPushButton:checked {
                background-color: #7B1111;
            }
            QPushButton:checked:hover {
                background-color: #8B1818;
            }
        """)

        self.toggled.connect(self._on_toggled)
        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)
        self._try_enable()

    def _try_enable(self) -> None:
        enabled = _DEVICE_NAME in self._mmcore.getLoadedDevices()
        self.setEnabled(enabled)
        self._dev = self._mmcore.getDeviceObject(_DEVICE_NAME) if enabled else None

    def _on_toggled(self, checked: bool) -> None:
        if self.isEnabled() and self._dev:
            self._dev.setProperty("Pump Laser", "On" if checked else "Off")
