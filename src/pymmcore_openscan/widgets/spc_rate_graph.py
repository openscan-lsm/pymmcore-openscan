from dataclasses import dataclass, field
from math import log10
from typing import Any, cast

from pymmcore_plus import CMMCorePlus, Device, DeviceProperty
from qtpy.QtCore import QPoint, QPointF, QRectF, Qt, QTimer
from qtpy.QtGui import QColor, QIcon, QPainter, QPaintEvent, QPalette, QPen, QPixmap
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QAction,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from pymmcore_openscan._settings import Settings

MAX_POWER = 8


class _StandardFormSpinBox(QDoubleSpinBox):
    def __init__(self, parent: Any = None) -> None:
        super().__init__(parent)
        self.setRange(0, 1e8)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        cast("QLineEdit", self.lineEdit()).setReadOnly(True)
        # Set fixed width to accommodate ~6 characters (e.g., "1.23E45")
        self.setFixedWidth(60)

    def textFromValue(self, value: float) -> str:
        if value == 0:
            return "0.00E1"
        base = int(log10(value))
        prefix = value / 10**base
        return f"{prefix:.2f}E{base}"


@dataclass
class Rate:
    """SPC rate state."""

    text: str
    color: QColor
    visible: bool = True
    samples: list[float] = field(default_factory=list)
    prop: DeviceProperty | None = None
    spinbox: _StandardFormSpinBox = field(default_factory=_StandardFormSpinBox)


class SPCRateGraphCanvas(QWidget):
    """Canvas widget displaying an x-y rate graph."""

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
        rates: list[Rate],
    ) -> None:
        super().__init__(parent=parent)
        self._mmcore = mmcore or CMMCorePlus.instance()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Margins in pixels
        self.margin_left = 10
        self.margin_right = 30
        self.margin_top = 10
        self.margin_bottom = 30

        self._sample_interval = 100  # ms
        self._num_x_ticks = 6
        self._num_y_ticks = MAX_POWER

        self._rates = rates
        self._dev: Device | None = None
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._try_enable(self._mmcore)

    @property
    def _max_values(self) -> int:
        """The number of samples per value that can fit on the graph."""
        span = Settings.instance().spc_graph_span
        return int(span * 1000 / self._sample_interval) + 1

    def _try_enable(self, mmcore: CMMCorePlus) -> None:
        self._dev = None
        for rate in self._rates:
            rate.prop = None
            rate.samples.clear()

        if "OSc-LSM" in mmcore.getLoadedDevices():
            self._dev = mmcore.getDeviceObject("OSc-LSM")
            for rate in self._rates:
                name = f"BH-TCSPC-RateCounter-{rate.text}"
                if name in self._dev.propertyNames():
                    rate.prop = self._dev.getPropertyObject(name)

    def paintEvent(self, event: QPaintEvent) -> None:
        """Paint the graph."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Get palette colors
        palette = self.palette()
        text_color = palette.color(QPalette.ColorRole.Text)
        mid_color = palette.color(QPalette.ColorRole.Mid)

        # Calculate plot area
        width = self.width()
        height = self.height()
        plot_left = self.margin_left
        plot_right = width - self.margin_right
        plot_top = self.margin_top
        plot_bottom = height - self.margin_bottom
        plot_height = plot_bottom - plot_top
        plot_width = plot_right - plot_left

        # Draw grid lines
        painter.setPen(QPen(mid_color, 1))
        for i in range(self._num_y_ticks):
            y = plot_top + plot_height * i / (self._num_y_ticks - 1)
            painter.drawLine(QPointF(plot_left, y), QPointF(plot_right, y))
        for i in range(self._num_x_ticks):
            x = plot_left + plot_width * i / (self._num_x_ticks - 1)
            painter.drawLine(QPointF(x, plot_top), QPointF(x, plot_bottom))

        # Draw axes
        painter.setPen(QPen(text_color, 2))
        painter.drawLine(
            QPointF(plot_right, plot_top), QPointF(plot_right, plot_bottom)
        )
        painter.drawLine(QPointF(plot_left, plot_top), QPointF(plot_left, plot_bottom))
        painter.drawLine(
            QPointF(plot_left, plot_bottom), QPointF(plot_right, plot_bottom)
        )
        painter.drawLine(QPointF(plot_left, plot_top), QPointF(plot_right, plot_top))

        # Draw X-axis labels
        painter.setPen(text_color)
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)

        for i in range(self._num_x_ticks):
            secs = i / (self._num_x_ticks - 1) * Settings.instance().spc_graph_span
            label = f"{secs:g}"
            x = self._x(i / (self._num_x_ticks - 1))
            painter.drawText(
                QRectF(x - 20, plot_bottom + 1, 40, 13),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
        painter.drawText(
            QRectF(plot_left, plot_bottom + 15, plot_width, 14),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
            "time (seconds)",
        )

        # Draw Y-axis labels
        painter.setPen(text_color)
        font = painter.font()
        font.setPointSize(9)
        painter.setFont(font)

        for i in range(self._num_y_ticks):
            label = "10" if i == 0 else "100" if i == 1 else f"1e{i + 1}"
            y = self._y(10 ** (i + 1))
            # Draw label to the right of the axis
            text_rect = QRectF(plot_right, y - 10, self.margin_right, 20)
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter,
                label,
            )

        if self._dev is None:
            # Don't paint anything more if we don't have a device loaded
            return
        for rate in self._rates:
            if not rate.visible or rate.prop is None or len(rate.samples) < 2:
                continue

            pen = QPen(rate.color, 3)
            painter.setPen(pen)

            for j in range(1, len(rate.samples)):
                x1 = self._x((j - 1) / (self._max_values - 1))
                y1 = self._y(rate.samples[j - 1])
                x2 = self._x(j / (self._max_values - 1))
                y2 = self._y(rate.samples[j])
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))

    def _x(self, value: float) -> int:
        """Convert a value [0, 1] to a x coordinate on the plot."""
        plot_left = self.margin_left
        plot_right = self.width() - self.margin_right
        return int(plot_left * (value) + plot_right * (1 - value))

    def _y(self, value: float) -> int:
        """Convert a rate value to a y coordinate."""
        if value <= 0:
            return int(self.height() - self.margin_bottom)

        log_value = log10(value)
        max_log = MAX_POWER
        min_log = 1  # 10 Hz
        normalized = (log_value - min_log) / (max_log - min_log)
        y = (
            self.height()
            - self.margin_bottom
            - normalized * (self.height() - self.margin_top - self.margin_bottom)
        )
        return int(y)

    def update_data(self) -> None:
        """Update data and trigger repaint."""
        for rate in self._rates:
            if rate.prop is None:
                continue
            if len(rate.samples) >= self._max_values:
                rate.samples.pop()
            rate.samples.insert(0, rate.prop.value)
        self.update()

    def _show_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        # visibility toggles for each rate
        for rate in self._rates:
            action = QAction(rate.text, menu)
            action.setCheckable(True)
            action.setChecked(rate.visible)
            pixmap = QPixmap(12, 12)
            pixmap.fill(rate.color)
            action.setIcon(QIcon(pixmap))
            action.triggered.connect(lambda _, r=rate: self._toggle_rate(r))
            menu.addAction(action)
        menu.addSeparator()
        # A spinbox to control the graph span
        duration_action = QWidgetAction(menu)
        container = QWidget(menu)
        h_layout = QHBoxLayout(container)
        h_layout.setContentsMargins(8, 4, 8, 4)
        h_layout.addWidget(QLabel("Duration:"))
        spinbox = QDoubleSpinBox(container)
        spinbox.setRange(0.1, 600)
        spinbox.setSuffix(" s")
        spinbox.setDecimals(1)
        spinbox.setValue(Settings.instance().spc_graph_span)
        spinbox.editingFinished.connect(lambda: self._set_duration(spinbox.value()))
        h_layout.addWidget(spinbox)
        duration_action.setDefaultWidget(container)
        menu.addAction(duration_action)
        # run it
        menu.exec(self.mapToGlobal(pos))

    def _toggle_rate(self, rate: Rate) -> None:
        rate.visible = not rate.visible
        settings = Settings.instance()
        settings.spc_rate_visibility[rate.text] = rate.visible
        settings.flush()
        self.update()

    def _set_duration(self, secs: float) -> None:
        settings = Settings.instance()
        if secs == settings.spc_graph_span:
            return
        for rate in self._rates:
            del rate.samples[self._max_values :]
        settings.spc_graph_span = round(secs)
        settings.flush()
        self.update()


class SPCRateGraph(QWidget):
    """Widget displaying SPC Rate Graph with controls."""

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent)
        self._mmcore = mmcore or CMMCorePlus.instance()
        self.setMinimumWidth(300)
        self.setMinimumHeight(300)

        # Rate colors chosen for to be:
        # 1) contrasting against light and dark themes
        # 2) Colorblind-accessible (tested against protanopia, deuteranopia, tritanopia)
        #    https://davidmathlogic.com/colorblind/#%23D81B60-%23FFC107-%231E88E5-%2376AB10
        self._rates = [
            Rate(text="Sync", color=QColor(216, 27, 96)),
            Rate(text="CFD", color=QColor(255, 193, 7)),
            Rate(text="TAC", color=QColor(30, 136, 229)),
            Rate(text="ADC", color=QColor(118, 171, 16)),
        ]

        # Create a canvas to display the rate
        self._canvas = SPCRateGraphCanvas(
            parent=self, mmcore=self._mmcore, rates=self._rates
        )

        # Set initial visibility for each rate
        settings = Settings.instance()
        for rate in self._rates:
            rate.visible = settings.spc_rate_visibility.get(rate.text, True)

        # Create horizontal layout for spinboxes
        spinboxes_layout = QHBoxLayout()
        for rate in self._rates:
            rate_layout = QVBoxLayout()
            color = rate.color
            label = QLabel(rate.text)
            label.setStyleSheet(
                f"color: rgb({color.red()}, {color.green()}, {color.blue()})"
            )
            rate_layout.addWidget(label)
            rate_layout.addWidget(rate.spinbox)
            spinboxes_layout.addLayout(rate_layout)

        layout = QVBoxLayout(self)
        layout.addWidget(self._canvas)
        layout.addLayout(spinboxes_layout)

        t = QTimer(self)
        t.setInterval(self._canvas._sample_interval)
        t.timeout.connect(self._pollRates)
        t.start()

        self._mmcore.events.systemConfigurationLoaded.connect(self._on_conf_loaded)
        self._on_conf_loaded()

    def _on_conf_loaded(self) -> None:
        """Handle configuration loaded event."""
        self._canvas._try_enable(self._mmcore)
        self._update_spinbox_states()

    def _update_spinbox_states(self) -> None:
        """Update spinbox enabled states based on available properties."""
        for rate in self._rates:
            enabled = rate.prop is not None
            rate.spinbox.setEnabled(enabled)
            if not enabled:
                rate.spinbox.clear()

    def _pollRates(self) -> None:
        """Poll rates and update display."""
        self._canvas.update_data()
        for rate in self._rates:
            if rate.samples:
                rate.spinbox.setValue(rate.samples[0])
