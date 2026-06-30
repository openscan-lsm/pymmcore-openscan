from __future__ import annotations

from bisect import bisect
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus, Device
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pymmcore_openscan._settings import Settings

from ._utils import _DEVICE_NAME, _POLL_INTERVAL_MS

if TYPE_CHECKING:
    from qtpy.QtCore import QPoint


class WavelengthWidget(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self._mmcore = mmcore or CMMCorePlus.instance()
        self._dev: Device | None = None
        self._preset_btns: list[QPushButton] = []

        # Target wavelength — user-editable, sent to device on commit
        self._target = QSpinBox()
        self._target.setRange(680, 1300)
        self._target.setSuffix(" nm")
        self._target.editingFinished.connect(self._on_target_changed)

        # Actual wavelength — read-only, updated by poll timer
        self._actual = QDoubleSpinBox()
        self._actual.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._actual.setRange(0, 9999)
        self._actual.setSuffix(" nm")
        self._actual.setReadOnly(True)

        # Presets panel
        self._presets_group = QGroupBox("Presets")
        self._presets_layout = QHBoxLayout(self._presets_group)
        self._add_btn = QPushButton("+ Add")
        self._add_btn.setToolTip("Save current target as a preset")
        self._add_btn.clicked.connect(self._add_preset)
        self._presets_layout.addWidget(self._add_btn)
        self._presets_layout.addStretch()

        form = QFormLayout()
        form.addRow("Target:", self._target)
        form.addRow("Actual:", self._actual)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._presets_group)

        # Polling timer for actual wavelength
        self._poll_timer = QTimer()
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll_actual)

        for wl in Settings.instance().spectra_physics_wavelength_presets:
            self._insert_preset_button(wl)

        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)

    def _try_enable(self) -> None:
        enabled = _DEVICE_NAME in self._mmcore.getLoadedDevices()
        self._dev = self._mmcore.getDeviceObject(_DEVICE_NAME) if enabled else None
        self.setEnabled(enabled)
        if enabled:
            self._poll_timer.start()
            self._on_target_changed()
        else:
            self._poll_timer.stop()

    def _on_target_changed(self) -> None:
        if self._dev is None:
            return
        self._dev.setProperty("Target Wavelength", str(self._target.value()))

    def _poll_actual(self) -> None:
        if self._dev is None:
            return
        try:
            val = float(self._mmcore.getProperty(_DEVICE_NAME, "Actual Wavelength"))
            self._actual.setValue(val)
        except Exception:
            pass

    def _add_preset(self) -> None:
        wl = self._target.value()
        existing = [int(b.text().removesuffix(" nm")) for b in self._preset_btns]
        if wl in existing:
            return
        self._insert_preset_button(wl)
        self._save_presets()

    def _insert_preset_button(self, wl: int) -> None:
        existing = [int(b.text().removesuffix(" nm")) for b in self._preset_btns]
        idx = bisect(existing, wl)
        btn = QPushButton(f"{wl} nm")
        btn.setToolTip("Click to apply; right-click to delete")
        btn.clicked.connect(lambda: self._apply_preset(wl))
        btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        btn.customContextMenuRequested.connect(
            lambda pos, b=btn, w=wl: self._show_remove_menu(b, w, pos)
        )
        self._presets_layout.insertWidget(idx, btn)
        self._preset_btns.insert(idx, btn)

    def _save_presets(self) -> None:
        Settings.instance().spectra_physics_wavelength_presets = [
            int(b.text().removesuffix(" nm")) for b in self._preset_btns
        ]
        Settings.instance().flush()

    def _apply_preset(self, wl: int) -> None:
        self._target.setValue(wl)
        self._on_target_changed()

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
