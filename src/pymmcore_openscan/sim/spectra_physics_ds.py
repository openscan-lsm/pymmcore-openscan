"""Simulated Spectra-Physics InSight DS+ laser device adapter (unicore).

Three classes live in this module so the hub's ``get_installed_peripherals``
can name them for Micro-Manager's peripheral-discovery mechanism:

- ``InsightDSSim``              - hub, owns the laser state machine
- ``InsightDSMainShutterSim``   - tunable-output main shutter peripheral
- ``InsightDS1040ShutterSim``   - fixed 1040 nm IR shutter peripheral

Load all three via ``UniMMCore.loadPyDevice`` and use the hub label as the
parent for the two shutters (``core.setParentLabel``).

Property names are chosen to match what the pymmcore-openscan widgets query,
which differs slightly from the C++ adapter in a few cases (see inline notes).
"""

from __future__ import annotations

import random
import threading
from typing import TYPE_CHECKING

from pymmcore_plus.experimental.unicore import (  # type: ignore[attr-defined]
    HubDevice,
    ShutterDevice,
    pymm_property,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


class InsightDSSim(HubDevice):
    """Simulated Spectra-Physics InSight DS+ laser hub.

    Parameters
    ----------
    warmup_seconds:
        How long (in seconds) the simulated warmup phase takes.
        Default is 30 s; use a smaller value (e.g. 5) for quick demos.
    """

    # Laser state codes (from manual Appendix A, also used in _laser_diagnostics.py)
    _STATE_READY = 25
    _STATE_RUNNING = 50

    def __init__(self, warmup_seconds: float = 30.0) -> None:
        super().__init__()
        self._warmup_seconds = warmup_seconds

        # NOT self._lock — that attribute belongs to the Device base class and
        # is used by the device manager's `with device:` context manager.
        # Shadowing it would cause a deadlock.
        self._state_lock = threading.Lock()
        self._stop = threading.Event()
        self._trans_stop = threading.Event()

        self._warmup_thread: threading.Thread | None = None
        self._trans_thread: threading.Thread | None = None

        # Core state
        self._warmup_pct: int = 0
        self._laser_state: int = 0
        self._is_energized: bool = False
        self._on_close: str = "Turn off laser"

        # Wavelength
        self._target_wl: int = 800
        self._actual_wl: float = 800.0

        # Diode diagnostics (vary during laser on/off transitions)
        self._diode1_current: float = 0.0
        self._diode2_current: float = 0.0

    # ------------------------------------------------------------------ #
    # Device lifecycle                                                     #
    # ------------------------------------------------------------------ #

    def initialize(self) -> None:
        """Initialize the simulated hub."""
        self._stop.clear()
        self._warmup_thread = threading.Thread(
            target=self._warmup_loop, name="InsightDS-warmup", daemon=True
        )
        self._warmup_thread.start()

    def shutdown(self) -> None:
        """Shut down the simulated hub."""
        self._stop.set()
        self._trans_stop.set()
        for t in (self._warmup_thread, self._trans_thread):
            if t is not None:
                t.join(timeout=2.0)

    def busy(self) -> bool:
        """Return whether the simulated hub is busy."""
        with self._state_lock:
            return 26 <= self._laser_state <= 49

    def get_installed_peripherals(self) -> Sequence[tuple[str, str]]:
        """Return the list of installed peripherals."""
        return [
            ("InsightDSMainShutterSim", "Main Shutter"),
            ("InsightDS1040ShutterSim", "1040nm IR Shutter"),
        ]

    # ------------------------------------------------------------------ #
    # Background simulation loops                                          #
    # ------------------------------------------------------------------ #

    def _warmup_loop(self) -> None:
        step_s = self._warmup_seconds / 100
        for i in range(1, 101):
            if self._stop.wait(step_s):
                return
            with self._state_lock:
                self._warmup_pct = i
                self._laser_state = (
                    self._STATE_READY if i >= 100 else min(24, int(i * 24 / 99))
                )

    def _laser_on_loop(self) -> None:
        n_steps = 24  # walks state 26 → 50
        step_s = 3.0 / n_steps
        for k in range(n_steps + 1):
            if self._trans_stop.wait(step_s):
                return
            t = k / n_steps
            with self._state_lock:
                self._laser_state = 26 + k
                self._diode1_current = 1.5 * t
                self._diode2_current = 1.2 * t

    def _tune_loop(self, target: int, prev_state: int) -> None:
        n_steps = 30
        step_s = 3.0 / n_steps
        with self._state_lock:
            start_wl = self._actual_wl
            self._laser_state = 26

        for k in range(1, n_steps + 1):
            if self._trans_stop.wait(step_s):
                return
            with self._state_lock:
                self._actual_wl = start_wl + (target - start_wl) * (k / n_steps)

        with self._state_lock:
            self._actual_wl = float(target)
            self._laser_state = prev_state

    def _start_trans(self, thread: threading.Thread) -> None:
        if self._trans_thread and self._trans_thread.is_alive():
            self._trans_stop.set()
            self._trans_thread.join(timeout=5.0)
        self._trans_stop.clear()
        self._trans_thread = thread
        thread.start()

    def _cancel_trans(self) -> None:
        if self._trans_thread and self._trans_thread.is_alive():
            self._trans_stop.set()
            self._trans_thread.join(timeout=5.0)
        self._trans_stop.clear()

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @pymm_property(name="Warmup Percentage (%)", is_read_only=True)
    def warmup_percentage(self) -> int:
        """The warmup percentage, in percent."""
        with self._state_lock:
            return self._warmup_pct

    @pymm_property(name="Laser State", is_read_only=True)
    def laser_state(self) -> str:
        """The laser state, as a human-readable string alongside the numeric code."""
        with self._state_lock:
            state = self._laser_state
            if state < 25:
                return f"Initializing ({state})"
            elif state == 25:
                return f"Ready ({state})"
            elif 25 < state and state < 50:
                return f"Turning on and/or optimizing ({state})"
            elif state == 50:
                return f"Running ({state})"
            elif 50 < state and state < 60:
                return f"Moving to Align mode ({state})"
            elif state == 60:
                return f"Aligning ({state})"
            elif 60 < state and state < 70:
                return f"Exiting Align mode ({state})"
            else:
                return f"Unknown state ({state})"

    @pymm_property(name="Relative Humidity (%)", is_read_only=True)
    def relative_humidity(self) -> float:
        """The relative humidity, in percent."""
        return 2.0

    @pymm_property(name="Diode 1 Current (A)", is_read_only=True)
    def diode1_current(self) -> float:
        """The current of diode 1, in amperes."""
        with self._state_lock:
            return self._diode1_current

    @pymm_property(name="Diode 1 Temperature (C)", is_read_only=True)
    def diode1_temperature(self) -> float:
        """The temperature of diode 1, in degrees Celsius."""
        return 22.1

    @pymm_property(name="Diode 1 Accumulated Hours", is_read_only=True)
    def diode1_hours(self) -> float:
        """The number of hours diode 1 has been in operation."""
        return 1234.5

    @pymm_property(name="Diode 2 Current (A)", is_read_only=True)
    def diode2_current(self) -> float:
        """The current of diode 2, in amperes."""
        with self._state_lock:
            return self._diode2_current

    @pymm_property(name="Diode 2 Temperature (C)", is_read_only=True)
    def diode2_temperature(self) -> float:
        """The temperature of diode 2, in degrees Celsius."""
        return 21.8

    @pymm_property(name="Diode 2 Accumulated Hours", is_read_only=True)
    def diode2_hours(self) -> float:
        """The number of hours diode 2 has been in operation."""
        return 987.3

    @pymm_property(name="Laser Power (W)", is_read_only=True)
    def laser_power(self) -> float:
        """The current laser power, in watts."""
        with self._state_lock:
            running = self._laser_state == self._STATE_RUNNING
        if not running:
            return 0.0
        return 2.5 + random.uniform(-0.5, 0.5)

    @pymm_property(name="Status Code Buffer", is_read_only=True)
    def history_buffer(self) -> str:
        """The laser's status code buffer, as a space-separated string of 16 codes."""
        return " ".join(["000"] * 16)

    @pymm_property(name="Pump Laser", allowed_values=["On", "Off"])
    def pump_laser(self) -> str:
        """Whether the pump laser is energized."""
        with self._state_lock:
            return "On" if self._is_energized else "Off"

    @pump_laser.setter  # type: ignore[no-redef]
    def pump_laser(self, value: str) -> None:
        with self._state_lock:
            state = self._laser_state
            already_energized = self._is_energized

        if value == "On":
            if already_energized:
                return
            if state != self._STATE_READY:
                raise RuntimeError(
                    f"Cannot turn on laser: state is {state}, must be "
                    f"{self._STATE_READY} (Ready). Wait for warmup to complete."
                )
            with self._state_lock:
                self._is_energized = True
            self._start_trans(
                threading.Thread(
                    target=self._laser_on_loop,
                    name="InsightDS-laser-on",
                    daemon=True,
                )
            )
        else:
            self._cancel_trans()
            with self._state_lock:
                self._is_energized = False
                if self._laser_state > self._STATE_READY:
                    self._laser_state = self._STATE_READY
                self._diode1_current = 0.0
                self._diode2_current = 0.0

    @pymm_property(
        name="On Close", allowed_values=["Maintain laser emission", "Turn off laser"]
    )
    def on_close(self) -> str:
        """What to do with the laser when the hub is closed."""
        with self._state_lock:
            return "Maintain laser emission" if self._is_energized else "Turn off laser"

    @on_close.setter  # type: ignore[no-redef]
    def on_close(self, value: str) -> None:
        with self._state_lock:
            self._on_close = value

    @pymm_property(name="Emission", is_read_only=True, allowed_values=[0, 1])
    def emission(self) -> int:
        """Whether the laser is currently emitting light (1) or not (0)."""
        with self._state_lock:
            return 1 if self._is_energized else 0

    @pymm_property(name="Pulsing", is_read_only=True, allowed_values=[0, 1])
    def pulsing(self) -> int:
        """Whether the laser is currently pulsing (1) or not (0)."""
        with self._state_lock:
            return 1 if self._laser_state in [50, 60] else 0

    @pymm_property(name="Servo On", is_read_only=True, allowed_values=[0, 1])
    def servo_on(self) -> int:
        """Whether the laser's servo is currently on (1) or not (0)."""
        # TODO: Not sure what this property is supposed to represent
        return 0

    @pymm_property(name="User Interlock", is_read_only=True, allowed_values=[0, 1])
    def user_interlock(self) -> int:
        """Whether the user interlock is currently engaged (1) or not (0)."""
        # TODO: Not sure what this property is supposed to represent
        return 0

    @pymm_property(name="Keyswitch Interlock", is_read_only=True, allowed_values=[0, 1])
    def keyswitch_interlock(self) -> int:
        """Whether the keyswitch interlock is currently engaged (1) or not (0)."""
        # TODO: Not sure what this property is supposed to represent
        return 0

    @pymm_property(
        name="Power supply Interlock", is_read_only=True, allowed_values=[0, 1]
    )
    def power_supply_interlock(self) -> int:
        """Whether the power supply interlock is currently engaged (1) or not (0)."""
        # TODO: Not sure what this property is supposed to represent
        return 0

    @pymm_property(name="Internal Interlock", is_read_only=True, allowed_values=[0, 1])
    def internal_interlock(self) -> int:
        """Whether the internal interlock is currently engaged (1) or not (0)."""
        # TODO: Not sure what this property is supposed to represent
        return 0

    @pymm_property(name="Warning", is_read_only=True, allowed_values=[0, 1])
    def warning(self) -> int:
        """Whether the laser is currently in a warning state (1) or not (0)."""
        # TODO
        return 0

    @pymm_property(name="Fault", is_read_only=True, allowed_values=[0, 1])
    def fault(self) -> int:
        """Whether the laser is currently in a fault state (1) or not (0)."""
        # TODO
        return 0


# --------------------------------------------------------------------------- #
# Peripheral: main tunable-output shutter                                     #
# --------------------------------------------------------------------------- #


class InsightDSMainShutterSim(ShutterDevice):
    """Simulated Spectra-Physics InSight DS+ main shutter (tunable output)."""

    def __init__(self, hub: InsightDSSim) -> None:
        super().__init__()
        self._hub = hub
        self._open: bool = False

    def busy(self) -> bool:
        """Whether the shutter is busy."""
        return self._hub.busy()

    def get_open(self) -> bool:
        """Whether the shutter is open."""
        with self._hub._state_lock:
            return self._open and self._hub._laser_state == InsightDSSim._STATE_RUNNING

    def set_open(self, open: bool) -> None:
        """Open or close the shutter."""
        if open:
            with self._hub._state_lock:
                state = self._hub._laser_state
            if state != InsightDSSim._STATE_RUNNING:
                raise RuntimeError(
                    f"Cannot open main shutter: laser state is {state}, "
                    f"must be {InsightDSSim._STATE_RUNNING} (Running)."
                )
        self._open = open

    @pymm_property(name="Target Wavelength (nm)", limits=(680, 1300))
    def target_wavelength(self) -> int:
        """The target wavelength, in nanometers."""
        with self._hub._state_lock:
            return self._hub._target_wl

    @target_wavelength.setter  # type: ignore[no-redef]
    def target_wavelength(self, value: int) -> None:
        wl = int(value)
        with self._hub._state_lock:
            self._hub._target_wl = wl
            state = self._hub._laser_state

        if state in (self._hub._STATE_READY, self._hub._STATE_RUNNING):
            self._hub._start_trans(
                threading.Thread(
                    target=self._hub._tune_loop,
                    args=(wl, state),
                    name="InsightDS-tune",
                    daemon=True,
                )
            )
        else:
            with self._hub._state_lock:
                self._hub._actual_wl = float(wl)

    @pymm_property(name="Actual Wavelength (nm)", is_read_only=True)
    def actual_wavelength(self) -> float:
        """The actual wavelength, in nanometers."""
        with self._hub._state_lock:
            return self._hub._actual_wl + random.uniform(-0.1, 0.1)

    @pymm_property(name="State", allowed_values=[0, 1])
    def state(self) -> int:
        """Return 1 if the shutter is open, 0 if closed."""
        return 1 if self.get_open() else 0

    @state.setter  # type: ignore[no-redef]
    def state(self, value: int) -> None:
        self.set_open(value == 1)


# --------------------------------------------------------------------------- #
# Peripheral: 1040 nm IR shutter                                              #
# --------------------------------------------------------------------------- #


class InsightDS1040ShutterSim(ShutterDevice):
    """Simulated Spectra-Physics InSight DS+ 1040 nm IR shutter."""

    def __init__(self, hub: InsightDSSim) -> None:
        super().__init__()
        self._hub = hub
        self._open: bool = False

    def busy(self) -> bool:
        """Whether the shutter is busy."""
        return self._hub.busy()

    def get_open(self) -> bool:
        """Whether the shutter is open."""
        with self._hub._state_lock:
            return self._open and self._hub._laser_state == InsightDSSim._STATE_RUNNING

    def set_open(self, open: bool) -> None:
        """Open or close the shutter."""
        if open:
            with self._hub._state_lock:
                state = self._hub._laser_state
            if state != InsightDSSim._STATE_RUNNING:
                raise RuntimeError(
                    f"Cannot open 1040nm shutter: laser state is {state}, "
                    f"must be {InsightDSSim._STATE_RUNNING} (Running)."
                )
        self._open = open

    @pymm_property(name="State", allowed_values=[0, 1])
    def state(self) -> int:
        """Return 1 if the shutter is open, 0 if closed."""
        return 1 if self.get_open() else 0

    @state.setter  # type: ignore[no-redef]
    def state(self, value: int) -> None:
        self.set_open(value == 1)
