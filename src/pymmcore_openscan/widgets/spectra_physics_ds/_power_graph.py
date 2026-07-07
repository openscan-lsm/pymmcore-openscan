from __future__ import annotations

from collections import deque
from time import monotonic

import pyqtgraph as pg
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QTimer
from qtpy.QtWidgets import QGroupBox, QVBoxLayout, QWidget

from ._utils import _DEVICE_NAME, _POLL_INTERVAL_MS

# MM device property name for laser output power — update to match the adapter
_POWER_PROP = "Laser Power"


class LaserPowerGraph(QGroupBox):
    """Time-series of laser output power."""

    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__("Laser Power", parent)
        self._mmcore = mmcore or CMMCorePlus.instance()

        self._times: deque[float] = deque()
        self._powers: deque[float] = deque()
        self._t0 = monotonic()

        self._plot = pg.PlotWidget()
        self._plot.setLabel("left", "Power", units="mW")
        self._plot.setLabel("bottom", "Time", units="s")
        self._plot.showGrid(x=True, y=True, alpha=0.3)
        self._plot.getViewBox().setMouseMode(pg.ViewBox.PanMode)
        self._curve = self._plot.plot(pen=pg.mkPen("r", width=2))

        layout = QVBoxLayout(self)
        layout.addWidget(self._plot)

        self._timer = QTimer()
        self._timer.setInterval(_POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)

        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)
        self._try_enable()

    def _try_enable(self) -> None:
        enabled = _DEVICE_NAME in self._mmcore.getLoadedDevices()
        self.setEnabled(enabled)
        if enabled:
            self._t0 = monotonic()
            self._times.clear()
            self._powers.clear()
            self._timer.start()
        else:
            self._timer.stop()

    def _poll(self) -> None:
        try:
            power = float(self._mmcore.getProperty(_DEVICE_NAME, _POWER_PROP))
        except Exception:
            return
        t = monotonic() - self._t0
        self._times.append(t)
        self._powers.append(power)
        self._curve.setData(list(self._times), list(self._powers))
