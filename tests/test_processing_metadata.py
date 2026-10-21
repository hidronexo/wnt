"""Coverage for Processing algorithm metadata and parameter setup."""

import pytest

pytest.importorskip("qgis")

from qgis.core import QgsProcessingParameterDefinition, QgsUnitTypes
from processing.gui.AlgorithmDialog import AlgorithmDialog

from wnt.wnt_provider import WaterNetworkToolsProvider

from .utilities import get_qgis_app


QGIS_APP = get_qgis_app()


pytestmark = pytest.mark.qgis


def test_provider_metadata_icon_and_unload():
    provider = WaterNetworkToolsProvider()

    assert provider.id() == "wnt"
    assert provider.name() == "Water Network Tools"
    assert provider.longName() == "Water Network Tools"
    assert provider.icon() is not None
    assert provider.unload() is None


def test_all_algorithms_expose_metadata_and_parameters():
    provider = WaterNetworkToolsProvider()
    provider.loadAlgorithms()

    assert len(provider.algorithms()) == 24

    for algorithm in provider.algorithms():
        clone = algorithm.createInstance()

        assert type(clone) is type(algorithm)
        assert algorithm.name()
        assert algorithm.displayName()
        assert algorithm.group()
        assert algorithm.groupId()
        assert "<p>" in algorithm.shortHelpString()

        clone.initAlgorithm()
        parameters = clone.parameterDefinitions()
        names = [parameter.name() for parameter in parameters]

        assert parameters, clone.name()
        assert len(names) == len(set(names)), clone.name()


def test_network_from_lines_distance_uses_output_crs_units():
    provider = WaterNetworkToolsProvider()
    provider.loadAlgorithms()
    algorithm = next(
        algorithm for algorithm in provider.algorithms()
        if algorithm.name() == "network_from_lines"
    ).createInstance()

    algorithm.initAlgorithm()
    tolerance = algorithm.parameterDefinition(algorithm.TOLERANCE)

    assert tolerance.parentParameterName() == algorithm.CRS
    assert tolerance.defaultUnit() == QgsUnitTypes.DistanceMeters
    assert tolerance.minimum() == 0.001
    assert tolerance.maximum() == 1000.0


def test_split_lines_at_points_distance_uses_selected_crs_units():
    provider = WaterNetworkToolsProvider()
    provider.loadAlgorithms()
    algorithm = next(
        algorithm for algorithm in provider.algorithms()
        if algorithm.name() == "split_lines_at_points"
    ).createInstance()

    algorithm.initAlgorithm()
    tolerance = algorithm.parameterDefinition(algorithm.TOLERANCE)

    assert tolerance.description() == "Tolerance"
    assert tolerance.parentParameterName() == algorithm.CRS
    assert tolerance.defaultUnit() == QgsUnitTypes.DistanceMeters


def test_merge_networks_distance_uses_selected_crs_units():
    provider = WaterNetworkToolsProvider()
    provider.loadAlgorithms()
    algorithm = next(
        algorithm for algorithm in provider.algorithms()
        if algorithm.name() == "merge_networks"
    ).createInstance()

    algorithm.initAlgorithm()
    tolerance = algorithm.parameterDefinition(algorithm.TOLERANCE)

    assert tolerance.parentParameterName() == algorithm.CRS
    assert tolerance.defaultUnit() == QgsUnitTypes.DistanceMeters
    assert tolerance.minimum() == 0.0

@pytest.mark.parametrize(
    "algorithm_name",
    [
        "elevation_from_raster",
        "elevation_from_tin",
        "split_lines_at_points",
        "classify",
        "node_degrees",
        "validate",
    ],
)
def test_update_capable_algorithms_expose_output_mode(algorithm_name):
    provider = WaterNetworkToolsProvider()
    provider.loadAlgorithms()
    algorithm = next(
        algorithm for algorithm in provider.algorithms()
        if algorithm.name() == algorithm_name
    ).createInstance()

    algorithm.initAlgorithm()
    names = [parameter.name() for parameter in algorithm.parameterDefinitions()]

    assert "OUTPUT_MODE" in names

def test_export_group_starts_with_epanet_exports():
    provider = WaterNetworkToolsProvider()
    provider.loadAlgorithms()

    export_names = [
        algorithm.displayName()
        for algorithm in provider.algorithms()
        if algorithm.groupId() == "export"
    ]

    assert export_names[:3] == [
        "Export EPANET model to INP file",
        "Demand to epanet scenario file (.scn)",
        "Pipe properties to EPANET scenario file (.scn)",
    ]


def test_network_from_lines_uses_expected_form_labels():
    provider = WaterNetworkToolsProvider()
    provider.loadAlgorithms()
    algorithm = next(
        algorithm for algorithm in provider.algorithms()
        if algorithm.name() == "network_from_lines"
    ).createInstance()

    algorithm.initAlgorithm()

    assert algorithm.parameterDefinition(algorithm.INCREMENT_NODE).description() == (
        "Node numbering increment"
    )
    assert algorithm.parameterDefinition(algorithm.INCREMENT_LINK).description() == (
        "Link numbering increment"
    )
    assert algorithm.parameterDefinition(algorithm.OUTPUT_NODES).description() == (
        "Network node layer"
    )
    assert algorithm.parameterDefinition(algorithm.OUTPUT_LINES).description() == (
        "Network link layer"
    )


def test_help_code_fragments_are_blue_and_readable():
    provider = WaterNetworkToolsProvider()
    provider.loadAlgorithms()
    algorithms = {algorithm.name(): algorithm for algorithm in provider.algorithms()}

    help_text = algorithms["classify"].shortHelpString()

    assert '<code style="color:#0057b8; font-weight:600;">topology</code>' in help_text
    assert '<code>topology</code>' not in help_text


def test_network_to_epanet_exposes_workflow_controls():
    provider = WaterNetworkToolsProvider()
    provider.loadAlgorithms()
    algorithm = next(
        algorithm for algorithm in provider.algorithms()
        if algorithm.name() == "network_to_epanet"
    ).createInstance()

    algorithm.initAlgorithm()

    assert algorithm.parameterDefinition(algorithm.WORKFLOW).description() == "Output mode"
    assert algorithm.parameterDefinition(algorithm.INPUT_EPANET).description() == (
        "Existing EPANET model file"
    )
    assert algorithm.parameterDefinition(algorithm.EPANET_VERSION).description() == (
        "EPANET version"
    )
    assert algorithm.parameterDefinition(algorithm.FLOW_UNITS).description() == "Flow units"
    names = [parameter.name() for parameter in algorithm.parameterDefinitions()]
    assert names[:2] == [algorithm.WORKFLOW, algorithm.INPUT_EPANET]
    assert algorithm.parameterDefinition(algorithm.INPUT_EPANET).metadata()[
        "epanet_existing_only"
    ] is True
    for name in (
        algorithm.EPANET_VERSION,
        algorithm.FLOW_UNITS,
        algorithm.HEADLOSS,
        algorithm.DEMAND_MODEL,
        algorithm.DEFAULT_PATTERN,
        algorithm.DEMAND_MULTIPLIER,
        algorithm.PRESSURE_EXPONENT,
    ):
        assert algorithm.parameterDefinition(name).metadata()["epanet_scratch_only"] is True
    for name in (
        algorithm.DEMAND_MODEL,
        algorithm.DEFAULT_PATTERN,
        algorithm.DEMAND_MULTIPLIER,
        algorithm.PRESSURE_EXPONENT,
    ):
        assert (
            algorithm.parameterDefinition(name).flags()
            & QgsProcessingParameterDefinition.FlagAdvanced
        )


def test_network_to_epanet_workflow_enables_only_relevant_parameters():
    provider = WaterNetworkToolsProvider()
    provider.loadAlgorithms()
    algorithm = next(
        algorithm for algorithm in provider.algorithms()
        if algorithm.name() == "network_to_epanet"
    ).createInstance()
    algorithm.initAlgorithm()
    dialog = AlgorithmDialog(algorithm)
    wrappers = dialog.mainWidget().wrappers
    scratch_names = (
        algorithm.EPANET_VERSION,
        algorithm.FLOW_UNITS,
        algorithm.HEADLOSS,
        algorithm.DEMAND_MODEL,
        algorithm.DEFAULT_PATTERN,
        algorithm.DEMAND_MULTIPLIER,
        algorithm.EMITTER_EXPONENT,
        algorithm.VISCOSITY,
        algorithm.DIFFUSIVITY,
        algorithm.SPECIFIC_GRAVITY,
        algorithm.TRIALS,
        algorithm.ACCURACY,
        algorithm.UNBALANCED,
        algorithm.MINIMUM_PRESSURE,
        algorithm.REQUIRED_PRESSURE,
        algorithm.PRESSURE_EXPONENT,
    )

    def is_enabled(name):
        wrapper = wrappers[name]
        widget = getattr(wrapper, "widget", None) or wrapper.wrappedWidget()
        return widget.isEnabled()

    assert is_enabled(algorithm.INPUT_EPANET)
    assert all(not is_enabled(name) for name in scratch_names)

    wrappers[algorithm.WORKFLOW].setValue(algorithm.WORKFLOW_SCRATCH)
    wrappers[algorithm.DEMAND_MODEL].setValue(1)
    wrappers['QUALITY_ANALYSIS'].setValue(1)
    from qgis.core import QgsProcessingContext
    wrappers['DURATION'].setParameterValue('24:00', QgsProcessingContext())
    QGIS_APP.processEvents()

    assert not is_enabled(algorithm.INPUT_EPANET)
    assert all(is_enabled(name) for name in scratch_names)
    dialog.close()


def test_corrected_help_strings_are_exposed():
    provider = WaterNetworkToolsProvider()
    provider.loadAlgorithms()
    algorithms = {algorithm.name(): algorithm for algorithm in provider.algorithms()}

    assert "Output mode" in algorithms["network_to_epanet"].shortHelpString()
    assert "external <code" in algorithms["network_to_ppno"].shortHelpString()
    assert ".cat</code>" in algorithms["network_to_ppno"].shortHelpString()
    assert "EPANET demand scenario file" in algorithms["network_to_epanet_demand_scenario"].shortHelpString()
    assert "<code style=\"color:#0057b8; font-weight:600;\">.scn</code>" in algorithms["network_to_epanet_pipe_propierties_scenario"].shortHelpString()
    assert "not generated" in algorithms["hydrant_pairs"].shortHelpString()
    assert algorithms["network_to_epanet"].displayName() == "Export EPANET model to INP file"
    assert algorithms["network_to_xml"].displayName() == "Network to XML"
    assert algorithms["network_from_xml"].displayName() == "Network from XML"
    assert algorithms["network_from_landxml"].displayName() == "Network from LandXML file"
    assert algorithms["network_from_epanet"].displayName() == "Import EPANET model from INP"
    assert algorithms["network_to_graph"].displayName() == "Network to graph file"
