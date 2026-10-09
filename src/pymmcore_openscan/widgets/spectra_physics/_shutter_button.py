from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from pymmcore_plus.core import ShutterDevice
from qtpy.QtCore import QByteArray, QRectF, QSize, Qt
from qtpy.QtGui import QIcon, QImage, QPainter, QPalette, QPixmap
from qtpy.QtSvg import QSvgRenderer
from qtpy.QtWidgets import QApplication
from superqt.utils import signals_blocked

if TYPE_CHECKING:
    from qtpy.QtWidgets import QWidget

from ._utils import SafetyButton

_ASSETS = Path(__file__).parent / "_assets"
_ICON_ACTIVE_PATH = _ASSETS / "laser-symbol.svg"
_ICON_INACTIVE_PATH = _ASSETS / "laser-symbol-inactive.svg"
_ICON_SIZE = QSize(128, 128)


class ShutterButton(SafetyButton):
    """Shutter open/close button with a safety countdown."""

    def __init__(
        self,
        device_name: str,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self._mmcore = mmcore or CMMCorePlus.instance()
        self._device_name = device_name
        self._dev: ShutterDevice | None = None
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.setIconSize(_ICON_SIZE)

        text_color = (
            QApplication.palette()
            .color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
            .name()
        )
        self.off_text = ""
        self.on_text = ""
        self.off_icon = self._qIcon(_ICON_INACTIVE_PATH, color=text_color)
        self.on_icon = self._qIcon(_ICON_ACTIVE_PATH)

        self.toggled.connect(self._on_toggled)
        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)
        self._mmcore.events.shutterOpenChanged.connect(self._on_shutter_open_change)
        self._mmcore.events.propertyChanged.connect(self._on_property_change)
        self._try_enable()

    def _try_enable(self) -> None:
        enabled = self._device_name in self._mmcore.getLoadedDevices()
        self.setEnabled(enabled)
        if enabled:
            self._dev = self._mmcore.getDeviceObject(self._device_name, ShutterDevice)
        else:
            self._dev = None

    def _on_shutter_open_change(self, device_name: str, open: bool) -> None:
        if device_name != self._device_name:
            return
        with signals_blocked(self):
            self.setChecked(open)

    def _on_property_change(
        self, device_name: str, prop_name: str, prop_val: str
    ) -> None:
        if device_name != self._device_name:
            return
        if prop_name != "State":
            return
        with signals_blocked(self):
            self.setChecked(bool(prop_val))

    def _on_toggled(self, checked: bool) -> None:
        if self.isEnabled() and self._dev:
            if checked:
                try:
                    self._dev.open()
                except RuntimeError as e:
                    # The device adapter prevents opening the shutter before turning on
                    # the laser
                    with signals_blocked(self):
                        self.setChecked(False)
                    raise e
            else:
                self._dev.close()

    def _qIcon(self, path: Path, color: str | None = None) -> QIcon:
        if color is not None:
            data = path.read_bytes().replace(b"currentColor", color.encode())
            renderer = QSvgRenderer(QByteArray(data))
        else:
            renderer = QSvgRenderer(str(path))

        w, h = _ICON_SIZE.width(), _ICON_SIZE.height()
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        img.fill(0x0)

        scaled = renderer.defaultSize().scaled(
            _ICON_SIZE, Qt.AspectRatioMode.KeepAspectRatio
        )
        x = (w - scaled.width()) / 2
        y = (h - scaled.height()) / 2

        painter = QPainter(img)
        renderer.render(painter, QRectF(x, y, scaled.width(), scaled.height()))
        painter.end()

        pixmap = QPixmap.fromImage(img)
        return QIcon(pixmap)
