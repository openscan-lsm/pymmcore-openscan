from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ._1040_shutter import Shutter1040Button
from ._laser_button import LaserButton
from ._main_shutter import ShutterMainButton


class LaserControlPanel(QGroupBox):
    """Combined panel with laser power, main shutter, and 1040nm shutter controls."""

    def __init__(
        self,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__("Laser Control", parent)
        self._mmcore = mmcore or CMMCorePlus.instance()

        self.laser_button = LaserButton(mmcore=self._mmcore)
        self.main_shutter_button = ShutterMainButton(mmcore=self._mmcore)
        self.shutter_1040_button = Shutter1040Button(mmcore=self._mmcore)

        expand = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        for btn in (
            self.laser_button,
            self.main_shutter_button,
            self.shutter_1040_button,
        ):
            btn.setSizePolicy(expand)

        main_layout = QVBoxLayout(self)

        # Top: laser label + button side by side
        laser_row = QHBoxLayout()
        laser_label = QLabel("Pump Laser")
        laser_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )
        laser_row.addWidget(laser_label)
        laser_row.addWidget(self.laser_button, stretch=1)
        main_layout.addLayout(laser_row)

        # Bottom: two shutters in a labelled box
        shutter_box = QGroupBox("Shutters")
        shutter_layout = QHBoxLayout(shutter_box)
        for label_text, btn in (
            ("Main Shutter", self.main_shutter_button),
            ("1040nm Shutter", self.shutter_1040_button),
        ):
            col = QVBoxLayout()
            col.addWidget(QLabel(label_text))
            col.addWidget(btn)
            shutter_layout.addLayout(col)

        main_layout.addWidget(shutter_box)
