from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QApplication

from pymmcore_openscan.widgets.spectra_physics_ds import (
    DiodeWidget,
    LaserControlPanel,
    WavelengthWidget,
)

app = QApplication([])

mmcore = CMMCorePlus().instance()

# Uncomment to load a real SpectraPhysicsInsightDS+ device:
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

app.exec()
