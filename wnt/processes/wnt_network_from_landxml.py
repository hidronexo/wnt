"""Import network layers from a LandXML pipe-network file."""

from qgis.core import (
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFile,
    QgsProcessingParameterString,
)

from .base import parse_name_list
from .messages import error
from .wnt_network_from_xml import NetworkFromXmlAlgorithm, xml_root_name


class NetworkFromLandXMLAlgorithm(NetworkFromXmlAlgorithm):
    """Import node and link layers from LandXML 1.2."""

    def createInstance(self):
        return NetworkFromLandXMLAlgorithm()

    def name(self):
        return "network_from_landxml"

    def displayName(self):
        return self.tr("Network from LandXML file")

    def shortHelpString(self):
        return self.tr("""<p>Imports pipe networks from a LandXML 1.2 file.</p>
<ul>
<li>Creates WNT node and link layers for pressure, sanitary and storm networks.</li>
<li>Network names are written as a comma or semicolon separated list. If empty, all networks are loaded.</li>
<li>Uses the coordinate reference system stored in the LandXML file when available.</li>
</ul>
        """)

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(self.INPUT, self.tr("LandXML file"), extension="xml"))
        self.addParameter(QgsProcessingParameterString(self.NETWORK_NAMES, self.tr("Network names"), optional=True))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_NODES, self.tr("Nodes")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_LINES, self.tr("Links")))

    def processAlgorithm(self, parameters, context, feedback):
        xml_file = self.parameterAsFile(parameters, self.INPUT, context)
        try:
            root_name = xml_root_name(xml_file)
        except ValueError as exc:
            error(feedback, str(exc))
        if root_name != "LandXML":
            error(feedback, "Invalid LandXML file: expected LandXML root")
        network_names = parse_name_list(self.parameterAsString(parameters, self.NETWORK_NAMES, context))
        return self._process_landxml(xml_file, network_names, parameters, context, feedback)
