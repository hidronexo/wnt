"""Export network layer pairs to WNT Network XML or LandXML."""

import json
# ElementTree is used only to construct trusted XML output.
import xml.etree.ElementTree as ET  # nosec B405

from qgis.core import (
    QgsProcessing,
    QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFileDestination,
    QgsProcessingParameterString,
)
from .base import WntProcessingAlgorithm, field_names, missing_fields
from .messages import crs as log_crs
from .messages import error, finish, info, start
from ..utils import utils_core as tools
from ..utils import utils_landxml as landxml


DOMAIN_FIELDS = ("epanet", "swmm", "landxml", "custom")
WNT_MODEL_TYPES = ("epanet", "swmm")
LANDXML_NETWORK_TYPES = ("sanitary", "storm", "water", "other")
OUTPUT_FORMATS = ("WNT Network XML", "LandXML 1.2")
NODE_COMMON_FIELDS = {"id", "type", "elevation"}
LINK_COMMON_FIELDS = {"id", "start", "end", "type", "length"}
LANDXML_NODE_FIELDS = set(landxml.NODE_FIELDS)
LANDXML_LINK_FIELDS = set(landxml.LINK_FIELDS)


def crs_label(crs):
    """Return a stable CRS label for XML metadata."""
    if crs and hasattr(crs, "authid"):
        return crs.authid()
    return ""


def json_properties(value, field_name, feature_id):
    """Parse a JSON properties field into a dictionary."""
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return dict(value)
    try:
        data = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON in {} for {}".format(field_name, feature_id)) from exc
    if not isinstance(data, dict):
        raise ValueError("JSON field {} for {} must contain an object".format(field_name, feature_id))
    return data


def apply_properties(model, feature, fields, common_fields, landxml_fields):
    """Copy domain and extra layer attributes into a WNT element."""
    consumed = set(common_fields) | set(DOMAIN_FIELDS)
    for domain in DOMAIN_FIELDS:
        if domain in fields:
            properties = json_properties(feature[domain], domain, feature["id"])
            if properties:
                model.get_properties(domain).update(properties)

    landxml_properties = {}
    custom_properties = {}
    for field in fields:
        if field in consumed:
            continue
        value = feature[field]
        if value in (None, ""):
            continue
        if field in landxml_fields:
            landxml_properties[field] = value
        else:
            custom_properties[field] = value
    if landxml_properties:
        model.get_properties("landxml").update(landxml_properties)
    if custom_properties:
        model.get_properties("custom").update(custom_properties)


def element_properties(feature, fields):
    """Return merged JSON domain properties from a feature."""
    properties = {}
    for domain in DOMAIN_FIELDS:
        if domain in fields:
            properties[domain] = json_properties(feature[domain], domain, feature["id"])
    return properties


def field_value(feature, fields, properties, name, default=None):
    """Read a value from feature fields or domain properties."""
    if name in fields and feature[name] not in (None, ""):
        return feature[name]
    for domain in ("landxml", "swmm", "epanet", "custom"):
        value = properties.get(domain, {}).get(name)
        if value not in (None, ""):
            return value
    return default


def text_or_none(value):
    if value in (None, ""):
        return None
    return str(value)


def add_if_set(attributes, name, value):
    value = text_or_none(value)
    if value is not None:
        attributes[name] = value


def section_element(pipe_element, link, fields, properties):
    """Add a LandXML pipe section element when dimensions are available."""
    shape = str(field_value(link, fields, properties, "geom_shape", "") or "").lower()
    diameter = field_value(link, fields, properties, "diameter")
    dim1 = field_value(link, fields, properties, "geom_dim1")
    dim2 = field_value(link, fields, properties, "geom_dim2")
    if diameter not in (None, ""):
        ET.SubElement(pipe_element, "CircPipe", {"diameter": str(diameter)})
    elif shape in ("box", "rect", "rectangular") and dim1 not in (None, ""):
        attrs = {"height": str(dim1)}
        add_if_set(attrs, "width", dim2)
        ET.SubElement(pipe_element, "RectPipe", attrs)
    elif shape == "egg" and dim1 not in (None, ""):
        attrs = {"height": str(dim1)}
        add_if_set(attrs, "width", dim2)
        ET.SubElement(pipe_element, "EggPipe", attrs)


def write_landxml(path, nodes, links, node_fields, link_fields, network_name, network_type, crs):
    """Write network layers as a LandXML 1.2 pipe network."""
    node_features = list(nodes.getFeatures())
    link_features = list(links.getFeatures())
    net_type = network_type
    root = ET.Element("LandXML", {"xmlns": "http://www.landxml.org/schema/LandXML-1.2"})
    authid = crs_label(crs)
    if authid.upper().startswith("EPSG:"):
        ET.SubElement(root, "CoordinateSystem", {"epsgCode": authid})
    pipe_networks = ET.SubElement(root, "PipeNetworks")
    pipe_network = ET.SubElement(
        pipe_networks,
        "PipeNetwork",
        {"name": str(network_name), "pipeNetworkType": net_type},
    )
    structures = ET.SubElement(pipe_network, "Structs")
    pipes = ET.SubElement(pipe_network, "Pipes")

    node_elements = {}
    node_ids = set()
    for feature in node_features:
        node_id = str(feature["id"])
        if node_id in node_ids:
            raise ValueError("Duplicated node id: {}".format(node_id))
        node_ids.add(node_id)
        properties = element_properties(feature, node_fields)
        attrs = {"name": node_id}
        add_if_set(attrs, "type", feature["type"] if "type" in node_fields else None)
        elevation = field_value(feature, node_fields, properties, "elevation")
        add_if_set(attrs, "elevSump", field_value(feature, node_fields, properties, "invert_elv", elevation))
        add_if_set(attrs, "elevRim", field_value(feature, node_fields, properties, "rim_elv"))
        struct = ET.SubElement(structures, "Struct", attrs)
        point = feature.geometry().asPoint()
        ET.SubElement(struct, "Center").text = "{} {}".format(point.x(), point.y())
        node_elements[node_id] = struct

    for feature in link_features:
        link_id = str(feature["id"])
        start_id = str(feature["start"])
        end_id = str(feature["end"])
        if start_id not in node_ids or end_id not in node_ids:
            raise ValueError("Link references undefined nodes: {}".format(link_id))
        properties = element_properties(feature, link_fields)
        attrs = {"name": link_id, "refStart": start_id, "refEnd": end_id}
        add_if_set(attrs, "length", field_value(feature, link_fields, properties, "length"))
        add_if_set(attrs, "desc", feature["type"] if "type" in link_fields else None)
        add_if_set(attrs, "roughness", field_value(feature, link_fields, properties, "roughness"))
        add_if_set(attrs, "material", field_value(feature, link_fields, properties, "material"))
        add_if_set(attrs, "status", field_value(feature, link_fields, properties, "status"))
        add_if_set(attrs, "lossCoeff", field_value(feature, link_fields, properties, "loss_coeff"))
        pipe = ET.SubElement(pipes, "Pipe", attrs)
        section_element(pipe, feature, link_fields, properties)
        inv_start = field_value(feature, link_fields, properties, "inv_start")
        inv_end = field_value(feature, link_fields, properties, "inv_end")
        if inv_start not in (None, ""):
            ET.SubElement(node_elements[start_id], "Invert", {"refPipe": link_id, "elev": str(inv_start)})
        if inv_end not in (None, ""):
            ET.SubElement(node_elements[end_id], "Invert", {"refPipe": link_id, "elev": str(inv_end)})

    tree = ET.ElementTree(root)
    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ")
    tree.write(str(path), encoding="utf-8", xml_declaration=True)


class NetworkToXmlAlgorithm(WntProcessingAlgorithm):
    """Export node and link layers to XML."""

    INPUT_NODES = "INPUT_NODES"
    INPUT_LINES = "INPUT_LINES"
    NETWORK_NAME = "NETWORK_NAME"
    WNT_MODEL_TYPE = "WNT_MODEL_TYPE"
    LANDXML_NETWORK_TYPE = "LANDXML_NETWORK_TYPE"
    OUTPUT_FORMAT = "OUTPUT_FORMAT"
    OUTPUT = "OUTPUT"
    WNT_MODEL_TYPES = WNT_MODEL_TYPES
    LANDXML_NETWORK_TYPES = LANDXML_NETWORK_TYPES
    OUTPUT_FORMATS = OUTPUT_FORMATS
    FORMAT_WNT = 0
    FORMAT_LANDXML = 1

    def createInstance(self):
        return NetworkToXmlAlgorithm()

    def name(self):
        return "network_to_xml"

    def displayName(self):
        return self.tr("Network to XML")

    def group(self):
        return self.tr("Export")

    def groupId(self):
        return "export"

    def shortHelpString(self):
        return self.tr("""<p>Exports network node and link layers to XML.</p>
<ul>
<li><code>WNT Network XML</code> stores topology and domain property bags using the network name as both network and version name.</li>
<li><code>LandXML 1.2</code> writes a pipe network with the selected standard network type: sanitary, storm, water or other.</li>
</ul>
        """)

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterEnum('LAYER_INPUT_MODE', self.tr('Layer representation'),
                          options=[self.tr('EPANET categories'), self.tr('Generic nodes and links')], defaultValue=0))
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT_NODES, self.tr("Input nodes layer"), [QgsProcessing.TypeVectorPoint], optional=True))
        self.addParameter(QgsProcessingParameterFeatureSource(self.INPUT_LINES, self.tr("Input links layer"), [QgsProcessing.TypeVectorLine], optional=True))
        from ..utils.utils_epanet_model import PHYSICAL_SECTIONS, NODE_SECTIONS
        for category in PHYSICAL_SECTIONS:
            geometry = QgsProcessing.TypeVectorPoint if category in NODE_SECTIONS else QgsProcessing.TypeVectorLine
            self.addParameter(QgsProcessingParameterFeatureSource('INPUT_' + category, category, [geometry], optional=True))
        self.addParameter(QgsProcessingParameterString(self.NETWORK_NAME, self.tr("Network name"), defaultValue="network"))
        self.addParameter(QgsProcessingParameterEnum(self.OUTPUT_FORMAT, self.tr("Output format"), options=list(self.OUTPUT_FORMATS), defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(self.WNT_MODEL_TYPE, self.tr("WNT model type"), options=list(self.WNT_MODEL_TYPES), defaultValue=0))
        self.addParameter(QgsProcessingParameterEnum(self.LANDXML_NETWORK_TYPE, self.tr("LandXML network type"), options=list(self.LANDXML_NETWORK_TYPES), defaultValue=self.LANDXML_NETWORK_TYPES.index("water")))
        self.addParameter(QgsProcessingParameterFileDestination(self.OUTPUT, self.tr("XML file"), fileFilter="*.xml"))

    def processAlgorithm(self, parameters, context, feedback):
        from ..utils.utils_epanet_model import PHYSICAL_SECTIONS
        if self.parameterAsEnum(parameters, 'LAYER_INPUT_MODE', context) == 0 and any('INPUT_' + category in parameters and parameters['INPUT_' + category] for category in PHYSICAL_SECTIONS):
            from .typed_xml import to_network
            from .wnt_network_from_xml import wnt_layer_data
            from pathlib import Path
            from tempfile import TemporaryDirectory
            from ..utils.export_files import publish_files
            sources = {category: self.parameterAsSource(parameters, 'INPUT_' + category, context)
                       for category in PHYSICAL_SECTIONS if parameters.get('INPUT_' + category)}
            network, crs = to_network(sources)
            name = self.parameterAsString(parameters, self.NETWORK_NAME, context) or 'network'
            output = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
            with TemporaryDirectory(prefix='wnt-xml-') as folder:
                temporary = Path(folder) / 'network.xml'
                if self.parameterAsEnum(parameters, self.OUTPUT_FORMAT, context) == self.FORMAT_WNT:
                    network.to_xml(temporary, name, network_id=name, model_type='epanet', crs=crs_label(crs), replace=True)
                else:
                    node_fields, link_fields, node_features, link_features, _crs = wnt_layer_data(network)

                    class Source:
                        def __init__(self, features):
                            self.features = features

                        def getFeatures(self):
                            return iter(self.features)

                    write_landxml(temporary, Source(node_features), Source(link_features),
                                  set(node_fields.names()), set(link_fields.names()), name,
                                  self.LANDXML_NETWORK_TYPES[self.parameterAsEnum(parameters, self.LANDXML_NETWORK_TYPE, context)], crs)
                if feedback.isCanceled():
                    return {}
                publish_files({output: temporary.read_bytes()})
            return {self.OUTPUT: output}
        nodes = self.parameterAsSource(parameters, self.INPUT_NODES, context)
        links = self.parameterAsSource(parameters, self.INPUT_LINES, context)
        network_name = self.parameterAsString(parameters, self.NETWORK_NAME, context) or "network"
        output_format = self.parameterAsEnum(parameters, self.OUTPUT_FORMAT, context)
        wnt_model_type = self.WNT_MODEL_TYPES[self.parameterAsEnum(parameters, self.WNT_MODEL_TYPE, context)]
        landxml_network_type = self.LANDXML_NETWORK_TYPES[self.parameterAsEnum(parameters, self.LANDXML_NETWORK_TYPE, context)]
        output = self.parameterAsFileOutput(parameters, self.OUTPUT, context)

        if nodes.sourceCrs() != links.sourceCrs():
            error(feedback, "Layers have different CRS")
        node_missing = missing_fields(nodes, ("id", "type"))
        link_missing = missing_fields(links, ("id", "start", "end", "type"))
        if node_missing or link_missing:
            error(feedback, "Missing required fields: {}".format(", ".join(node_missing + link_missing)))

        start(feedback, self.displayName())
        log_crs(feedback, nodes.sourceCrs())
        node_fields = field_names(nodes)
        link_fields = field_names(links)

        try:
            if output_format == self.FORMAT_LANDXML:
                write_landxml(output, nodes, links, node_fields, link_fields, network_name, landxml_network_type, nodes.sourceCrs())
                node_count = nodes.featureCount()
                link_count = links.featureCount()
            else:
                network = tools.WntNetwork()
                node_ids = set()
                for count, feature in enumerate(nodes.getFeatures(), start=1):
                    node_id = str(feature["id"])
                    if node_id in node_ids:
                        raise ValueError("Duplicated node id: {}".format(node_id))
                    node_ids.add(node_id)
                    node = tools.WntNode(node_id)
                    node.from_wkt(feature.geometry().asWkt())
                    node.set_type(feature["type"])
                    if "elevation" in node_fields and feature["elevation"] not in (None, ""):
                        node.set_elevation(feature["elevation"])
                    apply_properties(node, feature, node_fields, NODE_COMMON_FIELDS, LANDXML_NODE_FIELDS)
                    network.add_node(node)
                    if count % 100 == 0:
                        feedback.setProgress(50 * count / max(nodes.featureCount(), 1))

                for count, feature in enumerate(links.getFeatures(), start=1):
                    link_id = str(feature["id"])
                    start_id = str(feature["start"])
                    end_id = str(feature["end"])
                    if start_id not in node_ids or end_id not in node_ids:
                        raise ValueError("Link references undefined nodes: {}".format(link_id))
                    link = tools.WntLink(link_id, start_id, end_id)
                    link.from_wkt(feature.geometry().asWkt())
                    link.set_type(feature["type"])
                    if "length" in link_fields and feature["length"] not in (None, ""):
                        link.set_length(feature["length"])
                    apply_properties(link, feature, link_fields, LINK_COMMON_FIELDS, LANDXML_LINK_FIELDS)
                    network.add_link(link)
                    if count % 100 == 0:
                        feedback.setProgress(50 + 50 * count / max(links.featureCount(), 1))
                network.to_xml(
                    output,
                    network_name,
                    network_id=network_name,
                    model_type=wnt_model_type,
                    crs=crs_label(nodes.sourceCrs()),
                    metadata={"source": "qgis", "name": network_name},
                    replace=True,
                )
                node_count = len(network.nodes())
                link_count = len(network.links())
        except (tools.WntError, OSError, TypeError, ValueError) as exc:
            error(feedback, str(exc))

        info(feedback, "Output file", output)
        info(feedback, "Output format", self.OUTPUT_FORMATS[output_format])
        info(feedback, "Network name", network_name)
        if output_format == self.FORMAT_WNT:
            info(feedback, "WNT model type", wnt_model_type)
        else:
            info(feedback, "LandXML network type", landxml_network_type)
        info(feedback, "Nodes exported", node_count)
        info(feedback, "Links exported", link_count)
        finish(feedback)
        if feedback.isCanceled():
            return {}
        return {self.OUTPUT: output}
