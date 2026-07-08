from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtCore import QObject, QTimer, Signal
from qtpy.QtGui import QIcon
from qtpy.QtWidgets import QPushButton, QWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus

_DEVICE_NAME = "InsightDS+"
_MAIN_SHUTTER_DEVICE = "InsightDS+ Main"
_SHUTTER_1040_DEVICE = "InsightDS+ 1040nm"
_POLL_INTERVAL_MS = 500


class SafetyButton(QPushButton):
    """A QPushButton that toggles ON/OFF only after being held for a full countdown.

    Useful when you want to make sure that the user really intends to toggle the button.

    Press and hold to start the countdown; release early to cancel.
    Subclasses can override ``_refresh_stable`` to customise the ON/OFF display.
    """

    _OFF = "off"
    _COUNTING = "counting"
    _ON = "on"

    def __init__(
        self,
        parent: QWidget | None = None,
        on_text: str = "",
        off_text: str = "",
        on_icon: QIcon | None = None,
        counting_icon: QIcon | None = None,
        off_icon: QIcon | None = None,
        countdown_seconds: int = 3,
    ) -> None:
        super().__init__(parent)
        self._state = self._OFF
        self._source_state = self._OFF
        self._remaining = 0
        self.setCheckable(True)

        self._on_text = on_text
        self._off_text = off_text
        self._on_icon = on_icon or QIcon()
        self._counting_icon = counting_icon or QIcon()
        self._off_icon = off_icon or QIcon()

        self._countdown_seconds = countdown_seconds
        self.countdown_seconds = countdown_seconds  # sets tooltip

        self._countdown_timer = QTimer()
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._tick)

        self.pressed.connect(self._on_pressed)
        self.released.connect(self._on_released)
        self._refresh()

    def nextCheckState(self) -> None:
        """Suppress Qt's auto-toggle on click; state is managed entirely by us."""

    @property
    def on_text(self) -> str:
        return self._on_text

    @on_text.setter
    def on_text(self, value: str) -> None:
        self._on_text = value
        self._refresh()

    @property
    def off_text(self) -> str:
        return self._off_text

    @off_text.setter
    def off_text(self, value: str) -> None:
        self._off_text = value
        self._refresh()

    @property
    def on_icon(self) -> QIcon:
        return self._on_icon

    @on_icon.setter
    def on_icon(self, value: QIcon) -> None:
        self._on_icon = value
        self._refresh()

    @property
    def off_icon(self) -> QIcon:
        return self._off_icon

    @off_icon.setter
    def off_icon(self, value: QIcon) -> None:
        self._off_icon = value
        self._refresh()

    @property
    def counting_icon(self) -> QIcon:
        return self._counting_icon

    @counting_icon.setter
    def counting_icon(self, value: QIcon) -> None:
        self._counting_icon = value
        self._refresh()

    @property
    def countdown_seconds(self) -> int:
        return self._countdown_seconds

    @countdown_seconds.setter
    def countdown_seconds(self, value: int) -> None:
        self._countdown_seconds = value
        self.setToolTip(f"Hold for {self._countdown_seconds} seconds to toggle ON")
        self._refresh()

    def _on_pressed(self) -> None:
        if self._state == self._ON:
            self._state = self._OFF
        elif self._state == self._OFF:
            self._source_state = self._state
            self._state = self._COUNTING
            self._remaining = self._countdown_seconds
            self._countdown_timer.start()
        self._refresh()

    def _on_released(self) -> None:
        if self._state == self._COUNTING:
            self._countdown_timer.stop()
            self._state = self._source_state
            self._refresh()

    def _tick(self) -> None:
        self._remaining -= 1
        if self._remaining == 0:
            self._countdown_timer.stop()
            self._state = self._ON if self._source_state == self._OFF else self._OFF
        self._refresh()

    def _refresh(self) -> None:
        self.setChecked(self._state == self._ON)
        text = {
            self._ON: self.on_text,
            self._OFF: self.off_text,
            self._COUNTING: str(self._remaining),
        }
        self.setText(text[self._state])
        icon = {
            self._ON: self.on_icon,
            self._OFF: self.off_icon,
            self._COUNTING: self.counting_icon,
        }
        self.setIcon(icon[self._state])


class _PollingWorker(QObject):
    """Polls a configurable list of (device, property) pairs at a regular interval.

    Emits ``updated(device_name, property_name, value)`` for each pair on every tick.
    """

    updated = Signal(str, str, str)  # device_name, property_name, value

    def __init__(
        self,
        mmcore: CMMCorePlus,
        props: list[tuple[str, str]],
        interval_ms: int = _POLL_INTERVAL_MS,
    ) -> None:
        super().__init__()
        self._mmcore = mmcore
        self._props = props
        self._timer = QTimer()
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _poll(self) -> None:
        for device, prop in self._props:
            value = str(self._mmcore.getProperty(device, prop))
            self.updated.emit(device, prop, value)
