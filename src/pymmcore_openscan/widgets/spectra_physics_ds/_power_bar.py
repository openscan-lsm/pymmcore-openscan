from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, QThread
from qtpy.QtGui import QColor, QPainter
from qtpy.QtWidgets import QGroupBox, QVBoxLayout, QWidget

from ._utils import _DEVICE_NAME, _PollingWorker

if TYPE_CHECKING:
    from qtpy.QtGui import QPaintEvent

_POWER_PROP = "Laser Power (Watts)"
_BAR_MAX = 3.0
_TICK_INTERVAL = 0.5


class _PowerBarCanvas(QWidget):
    """Horizontal power bar, 0-3 with tick marks at 0.5 intervals."""

    _TICK_LINE_H = 5
    _LABEL_GAP = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self.setFixedHeight(52)
        self.setMinimumWidth(100)

    def set_value(self, value: float) -> None:
        if value == self._value:
            return
        self._value = value
        self.update()

    def paintEvent(self, a0: QPaintEvent | None) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        font = painter.font()
        font.setPointSize(7)
        painter.setFont(font)
        fm = painter.fontMetrics()

        tick_area_h = self._TICK_LINE_H + self._LABEL_GAP + fm.height()
        bar_h = max(4, h - tick_area_h - 2)

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(60, 60, 60))
        painter.drawRoundedRect(0, 0, w, bar_h, 3, 3)

        # Filled portion
        fraction = max(0.0, min(1.0, self._value / _BAR_MAX))
        fill_w = int(fraction * w)
        if fill_w > 0:
            painter.setBrush(QColor(180, 80, 80))
            painter.drawRoundedRect(0, 0, fill_w, bar_h, 3, 3)

        # Ticks and labels
        painter.setPen(QColor(160, 160, 160))
        tick_top = bar_h + 2
        label_baseline = tick_top + self._TICK_LINE_H + self._LABEL_GAP + fm.ascent()

        n_ticks = round(_BAR_MAX / _TICK_INTERVAL) + 1
        for i in range(n_ticks):
            val = i * _TICK_INTERVAL
            x = min(round(val / _BAR_MAX * w), w - 1)
            painter.drawLine(x, tick_top, x, tick_top + self._TICK_LINE_H - 1)
            label = f"{val:g}"
            lw = fm.horizontalAdvance(label)
            lx = max(0, min(x - lw // 2, w - lw))
            painter.drawText(lx, label_baseline, label)


class PowerBarWidget(QGroupBox):
    """Laser output power bar (0-3), polled from the device."""

    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__("Laser Power", parent)
        self._mmcore = mmcore or CMMCorePlus.instance()

        self._bar = _PowerBarCanvas()

        layout = QVBoxLayout(self)
        layout.addWidget(self._bar)

        self._worker = _PollingWorker(self._mmcore, [(_DEVICE_NAME, _POWER_PROP)])
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._worker.updated.connect(self._on_updated)

        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)
        self._try_enable()

    def _try_enable(self) -> None:
        enabled = _DEVICE_NAME in self._mmcore.getLoadedDevices()
        self.setEnabled(enabled)
        if enabled:
            if not self._thread.isRunning():
                self._thread.start()
                self._worker.start()
        else:
            self._worker.stop()
            self._thread.quit()
            self._thread.wait()

    def _on_updated(self, _: str, prop: str, value: str) -> None:
        if prop == _POWER_PROP:
            try:
                self._bar.set_value(float(value))
            except ValueError:
                pass
