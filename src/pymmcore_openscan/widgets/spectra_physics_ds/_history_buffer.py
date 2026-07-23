from __future__ import annotations

import enum
from datetime import datetime

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ._utils import _DEVICE_NAME

_HISTORY_PROP = "Status Code Buffer"
_NUM_SLOTS = 16


class CodeType(enum.Enum):
    """Enum for the type of history code."""

    STATUS = enum.auto()
    WARNING = enum.auto()
    FAULT = enum.auto()


# Code map derived from Insight DS+ manual, Appendix B.
_HISTORY_CODES: dict[int, tuple[CodeType, str]] = {
    0: (CodeType.STATUS, "Normal operation"),
    56: (CodeType.FAULT, "Hardware watchdog expired"),
    66: (CodeType.FAULT, "Software watchdog expired"),
    88: (CodeType.FAULT, "Diode thermistor shorted"),
    89: (CodeType.FAULT, "Diode thermistor open"),
    90: (CodeType.FAULT, "Diode(s) too hot (> 30°C)"),
    91: (CodeType.FAULT, "Diode(s) are warm (> 27°C)"),
    92: (CodeType.FAULT, "Diode(s) are too cold (< 18°C)"),
    117: (CodeType.FAULT, "Internal interlock"),
    118: (CodeType.FAULT, "CDRH interlock"),
    119: (CodeType.FAULT, "Power supply interlock"),
    120: (CodeType.FAULT, "Key switch interlock"),
    129: (CodeType.FAULT, "Very high humidity"),
    130: (CodeType.WARNING, "High humidity"),
    481: (CodeType.FAULT, "Slow diode ramp"),
    482: (CodeType.FAULT, "Low FSec Oscillator power"),
    483: (CodeType.FAULT, "Low FTO power"),
}

_EMPTY_CODE = "000"


class HistoryBufferPanel(QGroupBox):
    """Snapshot view of the laser history buffer (16 slots, most recent first)."""

    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__("History Buffer", parent)
        self._mmcore = mmcore or CMMCorePlus.instance()

        self._table = QTableWidget(_NUM_SLOTS, 2)
        self._table.setHorizontalHeaderLabels(["Code", "Description"])
        if (h_header := self._table.horizontalHeader()) is not None:
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        if (v_header := self._table.verticalHeader()) is not None:
            v_header.setVisible(False)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._last_read_label = QLabel("Last read: never")
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._refresh)

        bottom_row = QHBoxLayout()
        bottom_row.addWidget(self._last_read_label)
        bottom_row.addStretch()
        bottom_row.addWidget(self._refresh_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addLayout(bottom_row)

        self._mmcore.events.systemConfigurationLoaded.connect(self._try_enable)
        self._try_enable()

    def _try_enable(self) -> None:
        enabled = _DEVICE_NAME in self._mmcore.getLoadedDevices()
        self.setEnabled(enabled)

    def _refresh(self) -> None:
        raw = self._mmcore.getProperty(_DEVICE_NAME, _HISTORY_PROP)
        self._populate(raw)
        self._last_read_label.setText(
            f"Last read: {datetime.now().strftime('%H:%M:%S')}"
        )

    def _populate(self, raw: str) -> None:
        cleaned = raw.replace(" ", "")
        codes = [cleaned[i : i + 3] for i in range(0, len(cleaned), 3)]
        codes = (codes + [_EMPTY_CODE] * _NUM_SLOTS)[:_NUM_SLOTS]

        _COLORS = {
            CodeType.FAULT: QColor(220, 80, 80),
            CodeType.WARNING: QColor(210, 160, 40),
        }
        for row, code in enumerate(codes):
            int_code = int(code)
            entry = _HISTORY_CODES.get(
                int_code, (CodeType.WARNING, f"Unknown code: {int_code}")
            )
            desc = entry[1] if entry else ""
            code_item = QTableWidgetItem(code)
            desc_item = QTableWidgetItem(desc)
            if entry and (color := _COLORS.get(entry[0])):
                code_item.setForeground(color)
                desc_item.setForeground(color)
            self._table.setItem(row, 0, code_item)
            self._table.setItem(row, 1, desc_item)
