from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_openscan.widgets.spectra_physics import (
    LaserControlPanel,
    LaserDiagnosticsPanel,
)

app = QApplication([])

mmcore = CMMCorePlus().instance()

try:
    mmcore.loadDevice("Laser", "SpectraPhysicsLasers", "Spectra-Physics Laser")
    mmcore.initializeDevice("Laser")

    mmcore.loadDevice(
        "Main Shutter", "SpectraPhysicsLasers", "Spectra-Physics Main Shutter"
    )
    mmcore.initializeDevice("Main Shutter")
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
