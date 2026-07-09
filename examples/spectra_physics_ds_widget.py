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
    LaserControlPanel,
)

app = QApplication([])

# Pass warmup_seconds=10 for a short demo; use ~30 for realistic timing.
hub = InsightDSSim(warmup_seconds=10)
mmcore.loadPyDevice("InsightDS+", hub)
mmcore.initializeDevice("InsightDS+")

for label, cls in [
    ("InsightDS+ Main", InsightDSMainShutterSim),
    ("InsightDS+ 1040nm", InsightDS1040ShutterSim),
]:
    dev = cls(hub)
    mmcore.loadPyDevice(label, dev)
    mmcore.setParentLabel(label, "InsightDS+")
    mmcore.initializeDevice(label)

# Uncomment to load a real InsightDS+ device instead:
# from pymmcore_plus import CMMCorePlus
# mmcore = CMMCorePlus().instance()
# mmcore.loadDevice("InsightDS+", "SpectraPhysics", "InsightDS+")
# mmcore.initializeDevice("InsightDS+")

laser = LaserControlPanel(mmcore=mmcore)
laser.setWindowTitle("Laser")
laser.show()

# diagnostics = LaserDiagnosticsPanel(mmcore=mmcore)
# diagnostics.setWindowTitle("Diagnostics")
# diagnostics.show()

# browser = PropertyBrowser(mmcore=mmcore)
# browser.setWindowTitle("Device Property Browser")
# browser.show()

app.exec()
