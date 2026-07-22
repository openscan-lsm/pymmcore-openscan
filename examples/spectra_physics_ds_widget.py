from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_openscan.widgets.spectra_physics_ds import (
    LaserControlPanel,
    LaserDiagnosticsPanel,
)

app = QApplication([])

mmcore = CMMCorePlus().instance()

try:
    mmcore.loadDevice("InsightDS+", "SpectraPhysics", "InsightDS+")
    mmcore.initializeDevice("InsightDS+")
except Exception:
    # Device not available - widgets will be shown disabled
    pass


laser = LaserControlPanel(mmcore=mmcore)
laser.setWindowTitle("Laser")
laser.show()

diagnostics = LaserDiagnosticsPanel(mmcore=mmcore)
diagnostics.setWindowTitle("Diagnostics")
diagnostics.show()

app.exec()
