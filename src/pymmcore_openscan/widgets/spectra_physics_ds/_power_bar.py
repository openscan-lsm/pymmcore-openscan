from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, QThread
from qtpy.QtGui import QPainter
from qtpy.QtWidgets import QVBoxLayout, QWidget

from ._utils import _DEVICE_NAME, _PollingWorker

if TYPE_CHECKING:
    from qtpy.QtGui import QPaintEvent

_POWER_PROP = "Laser Power (W)"
_BAR_MAX = 3.0
_TICK_INTERVAL = 0.5


class _PowerBarCanvas(QWidget):
    """Horizontal power bar, 0-3 with tick marks at 0.5 intervals."""

    _TICK_LINE_H = 5
    _LABEL_GAP = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self.setFixedHeight(30)
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

        bar_h = h - self._LABEL_GAP - fm.height()

        pal = self.palette()

        # Background track
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(pal.color(pal.ColorRole.Mid))
        painter.drawRect(0, 0, w, bar_h)

        # Filled portion
        fraction = max(0.0, min(1.0, self._value / _BAR_MAX))
        fill_w = int(fraction * w)
        if fill_w > 0:
            painter.setBrush(pal.color(pal.ColorRole.Highlight))
            painter.drawRoundedRect(0, 0, fill_w, bar_h, 3, 3)

        # Ticks on the bar; labels below ticks
        painter.setPen(pal.color(pal.ColorRole.PlaceholderText))
        tick_top = 0
        label_baseline = bar_h + self._LABEL_GAP + fm.ascent()

        n_ticks = round(_BAR_MAX / _TICK_INTERVAL) + 1
        for i in range(n_ticks):
            val = i * _TICK_INTERVAL
            x = min(round(val / _BAR_MAX * w), w - 1)
            top = tick_top if val % 1 == 0 else tick_top + (3 * bar_h // 4)
            painter.drawLine(x, top, x, bar_h)
            if val % 3 == 0:
                label = f"{val:g}"
                lw = fm.horizontalAdvance(label)
                lx = max(0, min(x - lw // 2, w - lw))
                painter.drawText(lx, label_baseline, label)

        # "Output Power (W)" title centered on the bar
        painter.setPen(pal.color(pal.ColorRole.PlaceholderText))
        title = "Output Power (W)"
        tw = fm.horizontalAdvance(title)
        tx = max(0, (w - tw) // 2)
        ty = label_baseline
        painter.drawText(tx, ty, title)


class PowerBarWidget(QWidget):
    """Laser output power bar (0-3), polled from the device."""

    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent)
        self._mmcore = mmcore or CMMCorePlus.instance()

        self._bar = _PowerBarCanvas()

        layout = QVBoxLayout(self)
        layout.addWidget(self._bar)
        layout.setContentsMargins(0, 0, 0, 0)

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
            self._bar.set_value(0.0)

    def _on_updated(self, _: str, prop: str, value: str) -> None:
        if prop == _POWER_PROP:
            try:
                self._bar.set_value(float(value))
            except ValueError:
                pass
