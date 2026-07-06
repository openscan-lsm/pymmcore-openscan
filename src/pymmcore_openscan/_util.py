from pymmcore_gui import create_mmgui
from pymmcore_gui.actions import WidgetActionInfo
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QWidget

from pymmcore_openscan.widgets import (
    DCCWidget,
    DCUWidget,
    OpenScanParameters,
    SPCRateGraph,
)
from pymmcore_openscan.widgets.spectra_physics_ds import (
    DiodeWidget,
    LaserControlPanel,
    LaserDiagnosticsPanel,
    LaserPowerGraph,
    WavelengthWidget,
)


def augment_pymmcore_gui() -> None:
    """Installs package functionality into pymmcore-gui."""
    # By Creating these WidgetActionInfos, they are installed in pymmcore-gui.
    _get_action_infos()


def run() -> None:
    """Run the pymmcore-gui with OpenScan widgets."""
    augment_pymmcore_gui()
    create_mmgui()


def _get_action_infos() -> list[WidgetActionInfo]:
    return [
        WidgetActionInfo(
            key="bh_dcc",
            text="Becker & Hickl DCC",
            icon="mdi-light:format-list-bulleted",
            create_widget=_create_dcc,
        ),
        WidgetActionInfo(
            key="bh_dcu",
            text="Becker & Hickl DCU",
            icon="mdi-light:format-list-bulleted",
            create_widget=_create_dcu,
        ),
        WidgetActionInfo(
            key="bh_spc",
            text="Becker & Hickl SPC Rates",
            icon="carbon:meter",
            create_widget=_create_spc_rate_graph,
        ),
        WidgetActionInfo(
            key="openscan_params",
            text="OpenScan Params",
            icon="mynaui:scan",
            create_widget=_create_openscan_params,
        ),
        WidgetActionInfo(
            key="insight_ds_diode",
            text="Insight DS+ Diode",
            icon="game-icons:laser-warning",
            create_widget=_create_insight_ds_diode,
        ),
        WidgetActionInfo(
            key="insight_ds_wavelength",
            text="Insight DS+ Wavelength",
            icon="game-icons:laser-warning",
            create_widget=_create_insight_ds_wavelength,
        ),
        WidgetActionInfo(
            key="insight_ds_laser_control",
            text="Insight DS+ Laser Control",
            icon="game-icons:laser-warning",
            create_widget=_create_insight_ds_laser_control,
        ),
        WidgetActionInfo(
            key="insight_ds_diagnostics",
            text="Insight DS+ Diagnostics",
            icon="game-icons:laser-warning",
            create_widget=_create_insight_ds_diagnostics,
        ),
        WidgetActionInfo(
            key="insight_ds_power_graph",
            text="Insight DS+ Power",
            icon="game-icons:laser-warning",
            create_widget=_create_insight_ds_power_graph,
        ),
    ]


# -- Widget Creators --


def _create_dcc(parent: QWidget) -> QWidget:
    mmcore = CMMCorePlus.instance()
    return DCCWidget(parent=parent, mmcore=mmcore)


def _create_dcu(parent: QWidget) -> QWidget:
    mmcore = CMMCorePlus.instance()
    return DCUWidget(parent=parent, mmcore=mmcore)


def _create_spc_rate_graph(parent: QWidget) -> QWidget:
    mmcore = CMMCorePlus.instance()
    return SPCRateGraph(parent=parent, mmcore=mmcore)


def _create_openscan_params(parent: QWidget) -> QWidget:
    mmcore = CMMCorePlus.instance()
    return OpenScanParameters(parent=parent, mmcore=mmcore)


def _create_insight_ds_diode(parent: QWidget) -> QWidget:
    return DiodeWidget(parent=parent, mmcore=CMMCorePlus.instance())


def _create_insight_ds_wavelength(parent: QWidget) -> QWidget:
    return WavelengthWidget(parent=parent, mmcore=CMMCorePlus.instance())


def _create_insight_ds_laser_control(parent: QWidget) -> QWidget:
    return LaserControlPanel(parent=parent, mmcore=CMMCorePlus.instance())


def _create_insight_ds_diagnostics(parent: QWidget) -> QWidget:
    return LaserDiagnosticsPanel(parent=parent, mmcore=CMMCorePlus.instance())


def _create_insight_ds_power_graph(parent: QWidget) -> QWidget:
    return LaserPowerGraph(parent=parent, mmcore=CMMCorePlus.instance())
