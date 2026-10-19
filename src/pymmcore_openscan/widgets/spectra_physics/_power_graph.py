from __future__ import annotations

from collections import deque
from time import time

import pyqtgraph as pg
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QEvent, QPoint, Qt
from qtpy.QtGui import QPalette
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ._utils import _DEVICE_NAME, _PollingWorker

_POWER_PROP = "Laser Power (W)"


class LaserPowerGraph(QGroupBox):
    """Time-series of laser output power."""

    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__("Laser Power", parent)
        self._mmcore = mmcore or CMMCorePlus.instance()

        # TODO: We will likely want to be able to track power over longer time intervals
        self._times: deque[float] = deque(maxlen=7200)
        self._powers: deque[float] = deque(maxlen=7200)
        self._setting_range = False

        self._plot = pg.PlotWidget(axisItems={"bottom": pg.DateAxisItem()})
        self._plot.setLabel("left", "Power", units="W")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.setYRange(0, 3, padding=0)
        self._plot.hideButtons()
        vb = self._plot.getViewBox()
        vb.setMouseMode(pg.ViewBox.PanMode)
        vb.setMouseEnabled(x=True, y=False)
        # Disable "Last" mode when the user manually pans/zooms
        vb.sigRangeChangedManually.connect(self._on_manual_range_change)
        highlight = self.palette().color(QPalette.ColorRole.Highlight)
        self._curve = self._plot.plot(pen=pg.mkPen(highlight, width=2))

        self._live_interval = 60  # seconds
        self._live_btn = QPushButton("Live")
        self._live_btn.setCheckable(True)
        self._live_btn.setChecked(True)
        self._live_btn.toggled.connect(self._on_live_toggled)
        self._live_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._live_btn.customContextMenuRequested.connect(
            self._on_live_btn_context_menu
        )

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.addStretch()
        controls.addWidget(self._live_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self._plot)
        layout.addLayout(controls)

        self._worker = _PollingWorker(self._mmcore, [(_DEVICE_NAME, _POWER_PROP)])
        self._worker.updated.connect(self._on_updated)

        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)
        self._try_enable()

    def _on_live_btn_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        title = menu.addAction("Show last:")
        title.setEnabled(False)
        for label, seconds in [
            ("10 seconds", 10),
            ("1 minute", 60),
            ("10 minutes", 600),
            ("1 hour", 3600),
        ]:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self._live_interval == seconds)
            action.triggered.connect(lambda _, s=seconds: self._set_live_interval(s))
        menu.exec(self._live_btn.mapToGlobal(pos))

    def _set_live_interval(self, seconds: int) -> None:
        self._live_interval = seconds
        self._live_btn.setChecked(True)
        self._scroll_to_last()

    def _scroll_to_last(self) -> None:
        self._setting_range = True
        self._plot.setXRange(time() - self._live_interval, time(), padding=0)
        self._setting_range = False

    def _on_live_toggled(self, checked: bool) -> None:
        if checked:
            self._scroll_to_last()

    def _on_last_spin_changed(self) -> None:
        if self._live_btn.isChecked():
            self._scroll_to_last()

    def _on_manual_range_change(self) -> None:
        if not self._setting_range:
            self._live_btn.setChecked(False)

    def _try_enable(self) -> None:
        enabled = _DEVICE_NAME in self._mmcore.getLoadedDevices()
        self.setEnabled(enabled)
        self._times.clear()
        self._powers.clear()
        self._curve.setData([], [])
        if enabled:
            self._worker.start()
        else:
            self._worker.stop()

    def changeEvent(self, a0: QEvent | None) -> None:
        super().changeEvent(a0)
        if a0 is not None and a0.type() == QEvent.Type.PaletteChange:
            highlight = self.palette().color(QPalette.ColorRole.Highlight)
            self._curve.setPen(pg.mkPen(highlight, width=2))

    def _on_updated(self, _: str, prop: str, value: str) -> None:
        if prop != _POWER_PROP:
            return
        try:
            power = float(value)
        except ValueError:
            return
        self._times.append(time())
        self._powers.append(power)
        self._curve.setData(list(self._times), list(self._powers))
        if self._live_btn.isChecked():
            self._scroll_to_last()
