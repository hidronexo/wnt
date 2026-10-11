"""Processing provider for Water Network Tools."""

from importlib import import_module

from qgis.core import Qgis, QgsMessageLog, QgsProcessingProvider


ALGORITHM_SPECS = (
    ('.processes.wnt_assign_demand', 'AssignDemandAlgorithm'),
    ('.processes.wnt_classify', 'ClassifyAlgorithm'),
    ('.processes.wnt_config_toolkit', 'ConfigToolkitAlgorithm'),
    ('.processes.wnt_connect_by_distance', 'ConnectByDistanceAlgorithm'),
    ('.processes.wnt_elevation_from_raster', 'ElevationFromRasterAlgorithm'),
    ('.processes.wnt_elevation_from_tin', 'ElevationFromTINAlgorithm'),
    ('.processes.wnt_network_to_epanet', 'NetworkToEpanetAlgorithm'),
    ('.processes.wnt_demand_to_epanet_scenario', 'DemandToEpanetScenarioAlgorithm'),
    ('.processes.wnt_pipe_properties_to_epanet_scenario', 'PipePropertiesToEpanetScenarioAlgorithm'),
    ('.processes.wnt_network_to_xml', 'NetworkToXmlAlgorithm'),
    ('.processes.wnt_network_to_graph', 'NetworkToGraphAlgorithm'),
    ('.processes.wnt_hydrant_pairs', 'HydrantPairsAlgorithm'),
    ('.processes.wnt_network_from_landxml', 'NetworkFromLandXMLAlgorithm'),
    ('.processes.wnt_network_from_xml', 'NetworkFromXmlAlgorithm'),
    ('.processes.wnt_merge_networks', 'MergeNetworksAlgorithm'),
    ('.processes.wnt_network_from_epanet', 'NetworkFromEpanetAlgorithm'),
    ('.processes.wnt_network_from_lines', 'NetworkFromLinesAlgorithm'),
    ('.processes.wnt_node_degrees', 'NodeDegreesAlgorithm'),
    ('.processes.wnt_network_to_ppno', 'NetworkToPpnoAlgorithm'),
    ('.processes.wnt_network_to_pipesizing', 'NetworkToPipesizingAlgorithm'),
    ('.processes.wnt_results_from_epanet', 'ResultsFromEpanetAlgorithm'),
    ('.processes.wnt_split_lines_at_points', 'SplitLinesAtPointsAlgorithm'),
    ('.processes.wnt_validate', 'ValidateAlgorithm'),
    ('.processes.wnt_update_assignment', 'UpdateAssignmentAlgorithm'),
)


class WaterNetworkToolsProvider(QgsProcessingProvider):
    """Main class"""
    def __init__(self):
        """
        Default constructor.
        """
        QgsProcessingProvider.__init__(self)
        self.load_errors = []

    def unload(self):
        """
        Unloads the provider. Any tear-down steps required by the provider
        should be implemented here.
        """
        pass

    def loadAlgorithms(self):
        """
        Loads all algorithms belonging to this provider.
        """
        self.load_errors = []
        for module_name, class_name in ALGORITHM_SPECS:
            try:
                module = import_module(module_name, package=__package__)
                algorithm_class = getattr(module, class_name)
                self.addAlgorithm(algorithm_class())
            except Exception as exc:
                message = str(exc)
                self.load_errors.append((class_name, message))
                QgsMessageLog.logMessage(
                    f"Failed to load {class_name}: {message}",
                    "Water Network Tools",
                    Qgis.Warning,
                )

    def id(self):
        """
        Returns the unique provider id, used for identifying the provider. This
        string should be a unique, short, character only string, eg "qgis" or
        "gdal". This string should not be localised.
        """
        return 'wnt'

    def name(self):
        """
        Returns the provider name, which is used to describe the provider
        within the GUI.
        """
        return 'Water Network Tools'

    def icon(self):
        """
        Should return a QIcon which is used for your provider inside
        the Processing toolbox.
        """
        return QgsProcessingProvider.icon(self)

    def longName(self):
        """
        Returns the a longer version of the provider name, which can include
        extra details such as version numbers. E.g. "Water Network Tools
        (version 2.2.1)". This string should be localised. The default
        implementation returns the same string as name().
        """
        return self.name()
