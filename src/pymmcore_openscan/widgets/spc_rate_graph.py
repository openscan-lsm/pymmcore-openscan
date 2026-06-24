from math import log10
from typing import Any, cast

from pymmcore_plus import CMMCorePlus, Device, DeviceProperty
from qtpy.QtCore import QPointF, QRectF, Qt, QTimer
from qtpy.QtGui import QColor, QPainter, QPaintEvent, QPalette, QPen
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pymmcore_openscan._settings import Settings

MAX_POWER = 8

RATES = [
    "Sync",
    "CFD",
    "TAC",
    "ADC",
]

# Rate colors chosen for:
# 1) Good contrast with both light and dark themes
# 2) Colorblind accessibility (tested against protanopia, deuteranopia, tritanopia)
#    https://davidmathlogic.com/colorblind/#%23D81B60-%23FFC107-%231E88E5-%2376AB10
COLORS = [
    QColor(216, 27, 96),  # Red
    QColor(255, 193, 7),  # Yellow
    QColor(30, 136, 229),  # Blue
    QColor(118, 171, 16),  # Green
]


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


class SPCRateGraphCanvas(QWidget):
    """Canvas widget displaying an x-y rate graph."""

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent=parent)
        self._mmcore = mmcore or CMMCorePlus.instance()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Margins in pixels
        self.margin_left = 10
        self.margin_right = 30
        self.margin_top = 10
        self.margin_bottom = 30

        self._x_range = Settings.instance().spc_graph_time
        self._sample_interval = 100  # ms
        self._num_x_ticks = 6
        self._num_y_ticks = 8

        # The newest value is at index 0
        self._values: dict[DeviceProperty, list[float]] = {}

        self._dev: Device | None = None
        self._try_enable(self._mmcore)

    @property
    def _max_values(self) -> int:
        """The number of samples per value that can fit on the graph."""
        return int(self._x_range * 1000 / self._sample_interval) + 1

    def _try_enable(self, mmcore: CMMCorePlus) -> None:
        self._dev = None
        self._values.clear()

        if "OSc-LSM" in mmcore.getLoadedDevices():
            self._dev = mmcore.getDeviceObject("OSc-LSM")
            for rate in RATES:
                name = f"BH-TCSPC-RateCounter-{rate}"
                if name in self._dev.propertyNames():
                    self._values[self._dev.getPropertyObject(name)] = []

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
            secs = i / (self._num_x_ticks - 1) * self._x_range
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
        for i in range(len(RATES)):
            color = COLORS[i]
            prop = list(self._values.keys())[i]
            values = self._values[prop]
            if len(values) < 2:
                continue

            pen = QPen(color, 3)
            painter.setPen(pen)

            # Draw lines between points
            for j in range(1, len(values)):
                x1 = self._x((j - 1) / (self._max_values - 1))
                y1 = self._y(values[j - 1])
                x2 = self._x(j / (self._max_values - 1))
                y2 = self._y(values[j])
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
        for prop, values in self._values.items():
            if len(values) >= self._max_values:
                values.pop()
            values.insert(0, prop.value)
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

        self._canvas = SPCRateGraphCanvas(parent=self, mmcore=self._mmcore)

        # Create spinboxes for each rate
        self._spinboxes: dict[str, _StandardFormSpinBox] = {}
        for rate in RATES:
            self._spinboxes[rate] = _StandardFormSpinBox()

        # Create horizontal layout for spinboxes
        spinboxes_layout = QHBoxLayout()
        for i, rate in enumerate(RATES):
            rate_layout = QVBoxLayout()
            label = QLabel(rate)
            label.setStyleSheet(
                f"color: rgb({COLORS[i].red()}, {COLORS[i].green()}, {COLORS[i].blue()})"  # noqa: E501
            )
            rate_layout.addWidget(label)
            rate_layout.addWidget(self._spinboxes[rate])
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
        for i, rate in enumerate(RATES):
            if i < len(self._canvas._values):
                self._spinboxes[rate].setEnabled(True)
            else:
                self._spinboxes[rate].setEnabled(False)
                self._spinboxes[rate].clear()

    def _pollRates(self) -> None:
        """Poll rates and update display."""
        self._canvas.update_data()
        # Update spinbox values
        for i, rate in enumerate(RATES):
            if i < len(self._canvas._values):
                props = list(self._canvas._values.keys())
                if i < len(props):
                    self._spinboxes[rate].setValue(props[i].value)
