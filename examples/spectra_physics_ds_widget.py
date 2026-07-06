# UniMMCore must be instantiated before pymmcore_openscan (which imports
# pymmcore_gui) is imported, due to an ordering conflict in the C extension.
from pymmcore_plus.experimental.unicore import UniMMCore

mmcore = UniMMCore()

from qtpy.QtWidgets import QApplication  # noqa: E402

from pymmcore_openscan.sim.spectra_physics_ds import (  # noqa: E402
    InsightDS1040ShutterSim,
    InsightDSMainShutterSim,
    InsightDSSim,
)
from pymmcore_openscan.widgets.spectra_physics_ds import (  # noqa: E402
    DiodeWidget,
    LaserControlPanel,
    LaserDiagnosticsPanel,
    LaserPowerGraph,
    WavelengthWidget,
)

app = QApplication([])

# Pass warmup_seconds=10 for a short demo; use ~30 for realistic timing.
hub = InsightDSSim(warmup_seconds=10)
mmcore.loadPyDevice("SpectraPhysicsInsightDS+", hub)
mmcore.initializeDevice("SpectraPhysicsInsightDS+")

for label, cls in [
    ("SpectraPhysicsInsightDS+ Main Shutter", InsightDSMainShutterSim),
    ("SpectraPhysicsInsightDS+ 1040nm Shutter", InsightDS1040ShutterSim),
]:
    dev = cls(hub)
    mmcore.loadPyDevice(label, dev)
    mmcore.setParentLabel(label, "SpectraPhysicsInsightDS+")
    mmcore.initializeDevice(label)

# Uncomment to load a real SpectraPhysicsInsightDS+ device instead:
# from pymmcore_plus import CMMCorePlus
# mmcore = CMMCorePlus().instance()
# mmcore.loadDevice("SpectraPhysicsInsightDS+", "SpectraPhysics", "InsightDS+")
# mmcore.initializeDevice("SpectraPhysicsInsightDS+")

diode = DiodeWidget(mmcore=mmcore)
diode.setWindowTitle("Diode Widget")
diode.show()

wavelength = WavelengthWidget(mmcore=mmcore)
wavelength.setWindowTitle("Wavelength Widget")
wavelength.show()

laser = LaserControlPanel(mmcore=mmcore)
laser.setWindowTitle("Laser")
laser.show()

diagnostics = LaserDiagnosticsPanel(mmcore=mmcore)
diagnostics.setWindowTitle("Diagnostics")
diagnostics.show()

power = LaserPowerGraph(mmcore=mmcore)
power.setWindowTitle("Laser Power")
power.show()

app.exec()
