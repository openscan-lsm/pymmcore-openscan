from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus, Device
from qtpy.QtCore import Qt, QThread
from superqt.utils import signals_blocked

if TYPE_CHECKING:
    from qtpy.QtCore import QPoint
from qtpy.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QMenu,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt import QFlowLayout

from pymmcore_openscan._settings import Settings

from ._utils import _PollingWorker

_DEVICE_NAME = "InsightDS+ Main"
_TARGET_PROP = "Target Wavelength (nm)"
_ACTUAL_PROP = "Actual Wavelength (nm)"

_STATE_PROPS = [
    (_DEVICE_NAME, _ACTUAL_PROP),
]


class WavelengthWidget(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)
        ## -- STATE -- ##
        self._mmcore = mmcore or CMMCorePlus.instance()
        self._dev: Device | None = None
        self._preset_btns: list[QPushButton] = []

        ## -- WIDGETS -- ##
        self._target = QSpinBox()
        self._target.setRange(680, 1300)
        self._target.setSuffix(" nm")
        self._target.editingFinished.connect(self._on_target_widget_changed)

        self._actual = QLabel()
        self._actual.setText("N/A")

        self._presets_group = QGroupBox("Presets")
        self._presets_layout = QFlowLayout(self._presets_group)
        self._add_btn = QPushButton("+ Add")
        self._add_btn.setToolTip("Save current target as a preset")
        self._add_btn.clicked.connect(self._add_preset)
        self._presets_layout.addWidget(self._add_btn)

        ## -- LAYOUT -- ##
        form = QFormLayout()
        form.addRow("Target:", self._target)
        form.addRow("Actual:", self._actual)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._presets_group)

        ## -- INTERACTION -- ##
        self._worker = _PollingWorker(self._mmcore, _STATE_PROPS)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._worker.updated.connect(self._on_updated)

        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)
        self._mmcore.events.devicePropertyChanged(_DEVICE_NAME, _TARGET_PROP).connect(
            self._on_target_property_change
        )

        ## -- INITIALIZATION -- ##
        self._try_enable()
        for wl in Settings.instance().spectra_physics_wavelength_presets:
            self._insert_preset_button(wl)

    def _try_enable(self) -> None:
        # Search for the device
        self._dev = None
        if _DEVICE_NAME in self._mmcore.getLoadedDevices():
            self._dev = self._mmcore.getDeviceObject(_DEVICE_NAME)

        if self._dev:
            # Enable the widget
            self.setEnabled(True)
            self._target.setValue(int(self._dev.getProperty(_TARGET_PROP)))
            if not self._thread.isRunning():
                self._thread.start()
                self._worker.start()
        else:
            # Disable the widget
            self.setEnabled(False)
            self._target.setValue(0)
            self._worker.stop()
            self._thread.quit()
            self._thread.wait()

    def _on_target_property_change(self, new_value: str) -> None:
        if self._dev is None:
            return
        # Sync widget with property
        with signals_blocked(self._target):
            self._target.setValue(int(new_value))

    def _on_target_widget_changed(self) -> None:
        if self._dev is None:
            return
        # Sync property with widget
        self._dev.setProperty(_TARGET_PROP, str(self._target.value()))

    def _on_updated(self, _: str, prop: str, value: str) -> None:
        if prop == _ACTUAL_PROP:
            val = float(value)
            self._actual.setText(f"{val:g} nm")

    def _add_preset(self) -> None:
        wl = self._target.value()
        existing = [int(b.text().removesuffix(" nm")) for b in self._preset_btns]
        if wl in existing:
            return
        self._insert_preset_button(wl)
        self._save_presets()

    def _insert_preset_button(self, wl: int) -> None:
        btn = QPushButton(f"{wl} nm")
        btn.setToolTip("Click to apply; right-click to delete")
        btn.clicked.connect(lambda: self._apply_preset(wl))
        btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        btn.customContextMenuRequested.connect(
            lambda pos, b=btn, w=wl: self._show_remove_menu(b, w, pos)
        )
        self._presets_layout.addWidget(btn)
        self._preset_btns.append(btn)

    def _save_presets(self) -> None:
        Settings.instance().spectra_physics_wavelength_presets = [
            int(b.text().removesuffix(" nm")) for b in self._preset_btns
        ]
        Settings.instance().flush()

    def _apply_preset(self, wl: int) -> None:
        self._target.setValue(wl)
        self._on_target_widget_changed()

    def _show_remove_menu(self, btn: QPushButton, wl: int, pos: QPoint) -> None:
        menu = QMenu(self)
        remove = menu.addAction("Delete")
        if remove is not None:
            remove.triggered.connect(lambda: self._remove_preset(btn))
        menu.popup(btn.mapToGlobal(pos))

    def _remove_preset(self, btn: QPushButton) -> None:
        idx = self._preset_btns.index(btn)
        self._presets_layout.removeWidget(btn)
        btn.deleteLater()
        self._preset_btns.pop(idx)
        self._save_presets()
