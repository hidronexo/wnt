"""Import network layers from WNT Network XML or LandXML."""

import json

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLineString,
    QgsPoint,
    QgsPointXY,
    QgsProcessingContext,
    QgsProject,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFile,
    QgsProcessingParameterString,
    QgsVectorLayer,
    QgsWkbTypes,
)
from .base import WntProcessingAlgorithm, parse_name_list, set_output_layer_name
from .messages import crs as log_crs
from .messages import error, finish, info, start
from ..utils import utils_core as tools
from ..utils import utils_landxml as landxml
from ..utils.safe_xml import parse as safe_xml_parse


DOMAIN_ORDER = ("epanet", "swmm", "landxml", "custom")
NODE_FIELD_TYPES = {
    "elevation": QMetaType.Double,
    "demand": QMetaType.Double,
    "init_lvl": QMetaType.Double,
    "min_lvl": QMetaType.Double,
    "max_lvl": QMetaType.Double,
    "invert_elv": QMetaType.Double,
    "rim_elv": QMetaType.Double,
    "max_depth": QMetaType.Double,
}
LINK_FIELD_TYPES = {
    "length": QMetaType.Double,
    "diameter": QMetaType.Double,
    "roughness": QMetaType.Double,
    "loss_coeff": QMetaType.Double,
    "geom_dim1": QMetaType.Double,
    "geom_dim2": QMetaType.Double,
    "inv_start": QMetaType.Double,
    "inv_end": QMetaType.Double,
    "slope": QMetaType.Double,
    "start_os": QMetaType.Double,
    "end_os": QMetaType.Double,
}


def xml_root_name(path):
    """Return the local root element name for an XML file."""
    try:
        tag = safe_xml_parse(path).getroot().tag
    except Exception as exc:
        raise ValueError(f"Cannot read XML file: {exc}") from exc
    return tag.split("}", 1)[-1]


def stable_json(properties):
    """Return a stable JSON object string or an empty string."""
    if not properties:
        return ""
    return json.dumps(properties, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def ordered_domains(elements):
    """Return non-empty property domains used by a sequence of WNT elements."""
    domains = set()
    for element in elements:
        domains.update(element.all_properties())
    ordered = [domain for domain in DOMAIN_ORDER if domain in domains]
    ordered.extend(sorted(domain for domain in domains if domain not in ordered))
    return ordered


def output_crs(network):
    """Return the CRS stored in the XML network metadata."""
    crs = getattr(network, "xml_crs", None)
    if crs:
        return QgsCoordinateReferenceSystem(crs)
    return QgsCoordinateReferenceSystem()


def qfield(name, field_types):
    """Build a field with the unified LandXML schema type."""
    return QgsField(name, field_types.get(name, QMetaType.QString))


def qfields(field_names, field_types):
    """Build a QgsFields collection from field names."""
    fields = QgsFields()
    for field in field_names:
        fields.append(qfield(field, field_types))
    return fields


def layer_name(network, suffix):
    """Return the QGIS layer name for one imported network."""
    return f"{network['layer_base']}_{suffix}"


def node_feature(node, fields):
    """Build one node feature from a parsed LandXML node record."""
    feature = QgsFeature()
    point = QgsPointXY(node['x'], node['y'])
    feature.setGeometry(QgsGeometry.fromPointXY(point))
    feature.setAttributes([node.get(field) for field in fields])
    return feature


def link_feature(network, link, fields):
    """Build one link feature from a parsed LandXML link record."""
    feature = QgsFeature()
    start_node = network['nodes'][link['start']]
    end_node = network['nodes'][link['end']]
    spoint = QgsPoint(start_node['x'], start_node['y'])
    epoint = QgsPoint(end_node['x'], end_node['y'])
    feature.setGeometry(QgsGeometry(QgsLineString([spoint, epoint])))
    feature.setAttributes([link.get(field) for field in fields])
    return feature


def add_memory_layer(name, geometry, fields, crs, features, context=None):
    """Register an additional per-network memory layer for Processing output loading."""
    uri = geometry
    if crs and crs.isValid():
        uri = f"{uri}?crs={crs.authid()}"
    layer = QgsVectorLayer(uri, name, "memory")
    provider = layer.dataProvider()
    provider.addAttributes(list(fields))
    layer.updateFields()
    provider.addFeatures(features)
    if context is not None and hasattr(context, "temporaryLayerStore"):
        context.temporaryLayerStore().addMapLayer(layer)
        details = QgsProcessingContext.LayerDetails(name, context.project(), name)
        context.addLayerToLoadOnCompletion(layer.id(), details)
    else:
        QgsProject.instance().addMapLayer(layer)
    return layer


def link_length(link):
    """Return stored link length or compute it from geometry."""
    if link.get_length() is not None:
        return link.get_length()
    geometry = link.get_geometry()
    if geometry:
        return tools.polyline_length(geometry)


def wnt_network_names(xml_file):
    """Return WNT network ids in file order."""
    root = safe_xml_parse(str(xml_file)).getroot()
    if root.tag != "wntNetworkStore":
        raise ValueError("Invalid WNT XML file: expected wntNetworkStore root.")
    return [network.get("id") for network in root.findall("network") if network.get("id")]


def wnt_layer_name(network, suffix):
    return "{}_{}".format(getattr(network, "xml_network_id", None) or "network", suffix)


def wnt_layer_data(network):
    """Build fields and features for one WNT network."""
    crs = output_crs(network)
    node_domains = ordered_domains(network.nodes())
    link_domains = ordered_domains(network.links())

    node_fields = QgsFields()
    node_fields.append(QgsField("id", QMetaType.QString))
    node_fields.append(QgsField("type", QMetaType.QString))
    node_fields.append(QgsField("elevation", QMetaType.Double))
    for domain in node_domains:
        node_fields.append(QgsField(domain, QMetaType.QString))

    link_fields = QgsFields()
    link_fields.append(QgsField("id", QMetaType.QString))
    link_fields.append(QgsField("start", QMetaType.QString))
    link_fields.append(QgsField("end", QMetaType.QString))
    link_fields.append(QgsField("type", QMetaType.QString))
    link_fields.append(QgsField("length", QMetaType.Double))
    for domain in link_domains:
        link_fields.append(QgsField(domain, QMetaType.QString))

    node_features = []
    for node in network.nodes():
        feature = QgsFeature(node_fields)
        feature.setGeometry(QgsGeometry.fromWkt(node.to_wkt()))
        attributes = [node.name(), node.get_type(), node.get_elevation()]
        attributes.extend(stable_json(node.all_properties().get(domain, {})) for domain in node_domains)
        feature.setAttributes(attributes)
        node_features.append(feature)

    link_features = []
    for link in network.links():
        feature = QgsFeature(link_fields)
        feature.setGeometry(QgsGeometry.fromWkt(link.to_wkt()))
        attributes = [link.name(), link.start(), link.end(), link.get_type(), link_length(link)]
        attributes.extend(stable_json(link.all_properties().get(domain, {})) for domain in link_domains)
        feature.setAttributes(attributes)
        link_features.append(feature)

    return node_fields, link_fields, node_features, link_features, crs


class NetworkFromXmlAlgorithm(WntProcessingAlgorithm):
    """Import node and link layers from XML."""

    INPUT = "INPUT"
    VERSION_ID = "VERSION_ID"
    NETWORK_NAMES = "NETWORK_NAMES"
    OUTPUT_NODES = "OUTPUT_NODES"
    OUTPUT_LINES = "OUTPUT_LINES"

    def createInstance(self):
        return NetworkFromXmlAlgorithm()

    def name(self):
        return "network_from_xml"

    def displayName(self):
        return self.tr("Network from XML")

    def group(self):
        return self.tr("Import")

    def groupId(self):
        return "import"

    def shortHelpString(self):
        return self.tr("""<p>Imports network node and link layers from XML.</p>
<ul>
<li><code>WNT Network XML</code> files are loaded by network name and version; empty version loads the latest version for each selected network.</li>
<li><code>LandXML 1.2</code> pipe networks are converted to WNT node and link layers.</li>
<li>Network names are written as a comma or semicolon separated list. If empty, all networks are loaded.</li>
</ul>
        """)

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(self.INPUT, self.tr("XML file"), extension="xml"))
        self.addParameter(QgsProcessingParameterString(self.VERSION_ID, self.tr("Version id"), optional=True))
        self.addParameter(QgsProcessingParameterString(self.NETWORK_NAMES, self.tr("Network names"), optional=True))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_NODES, self.tr("Nodes")))
        self.addParameter(QgsProcessingParameterFeatureSink(self.OUTPUT_LINES, self.tr("Links")))

    def processAlgorithm(self, parameters, context, feedback):
        xml_file = self.parameterAsFile(parameters, self.INPUT, context)
        version_id = self.parameterAsString(parameters, self.VERSION_ID, context) or None
        network_names = parse_name_list(self.parameterAsString(parameters, self.NETWORK_NAMES, context))
        try:
            root_name = xml_root_name(xml_file)
        except ValueError as exc:
            error(feedback, str(exc))
        if root_name == "wntNetworkStore":
            return self._process_wnt_xml(xml_file, version_id, network_names, parameters, context, feedback)
        if root_name == "LandXML":
            return self._process_landxml(xml_file, network_names, parameters, context, feedback)
        error(feedback, "Unsupported XML format")

    def _process_wnt_xml(self, xml_file, version_id, selected_network_names, parameters, context, feedback):
        try:
            available_names = wnt_network_names(xml_file)
        except Exception as exc:
            error(feedback, str(exc))
        if not available_names:
            error(feedback, "WNT XML file does not contain networks")
        names_to_load = selected_network_names or available_names
        missing = [name for name in names_to_load if name not in available_names]
        if missing:
            error(feedback, "WNT XML networks not found: " + ", ".join(missing))

        start(feedback, self.displayName())
        netcnt = nodcnt = lnkcnt = 0
        node_id = link_id = None
        first_crs = None
        for index, name in enumerate(names_to_load):
            network = tools.WntNetwork()
            try:
                network.from_xml(xml_file, version_id=version_id, network_id=name)
            except Exception as exc:
                error(feedback, str(exc))
            node_fields, link_fields, node_features, link_features, crs = wnt_layer_data(network)
            if first_crs is None:
                first_crs = crs
                log_crs(feedback, crs)
            netcnt += 1
            nodcnt += len(node_features)
            lnkcnt += len(link_features)
            if index == 0:
                node_sink, node_id = self.parameterAsSink(parameters, self.OUTPUT_NODES, context, node_fields, QgsWkbTypes.Point, crs)
                link_sink, link_id = self.parameterAsSink(parameters, self.OUTPUT_LINES, context, link_fields, QgsWkbTypes.LineString, crs)
                set_output_layer_name(context, node_id, wnt_layer_name(network, "nodes"))
                set_output_layer_name(context, link_id, wnt_layer_name(network, "links"))
                for feature in node_features:
                    node_sink.addFeature(feature)
                for feature in link_features:
                    link_sink.addFeature(feature)
            else:
                add_memory_layer(wnt_layer_name(network, "nodes"), "Point", node_fields, crs, node_features, context)
                add_memory_layer(wnt_layer_name(network, "links"), "LineString", link_fields, crs, link_features, context)

        feedback.setProgress(100)
        info(feedback, "Input file", xml_file)
        info(feedback, "Input format", "WNT Network XML")
        info(feedback, "Networks imported", netcnt)
        info(feedback, "Network names", ", ".join(names_to_load))
        if version_id:
            info(feedback, "Version id", version_id)
        info(feedback, "Nodes imported", nodcnt)
        info(feedback, "Links imported", lnkcnt)
        finish(feedback)
        if feedback.isCanceled():
            return {}
        return {self.OUTPUT_NODES: node_id, self.OUTPUT_LINES: link_id}

    def _process_landxml(self, xml_file, selected_network_names, parameters, context, feedback):
        try:
            imp_net = landxml.network_from_xml(xml_file)
        except Exception as exc:
            error(feedback, str(exc))
        networks = imp_net['networks']
        if 'epsg_code' in imp_net:
            epsg_code = imp_net['epsg_code']
            if not epsg_code.upper().startswith('EPSG:'):
                epsg_code = 'EPSG:' + epsg_code
            crs = QgsCoordinateReferenceSystem(epsg_code)
        elif 'wkt_crs' in imp_net:
            crs = QgsCoordinateReferenceSystem('WKT:' + imp_net['wkt_crs'])
        else:
            crs = QgsCoordinateReferenceSystem()

        start(feedback, self.displayName())
        log_crs(feedback, crs)
        if not networks:
            error(feedback, "No LandXML PipeNetwork definitions found")

        lookup = dict(networks)
        for network in networks.values():
            lookup.setdefault(network['layer_base'], network)
        if selected_network_names:
            missing = [name for name in selected_network_names if name not in lookup]
            if missing:
                error(feedback, "LandXML networks not found: " + ", ".join(missing))
            selected_networks = [lookup[name] for name in selected_network_names]
            selected_names = selected_network_names
        else:
            selected_networks = list(networks.values())
            selected_names = list(networks.keys())

        first_network = selected_networks[0]
        node_fields = first_network["node_fields"]
        link_fields = first_network["link_fields"]
        node_sink, node_id = self.parameterAsSink(parameters, self.OUTPUT_NODES, context, qfields(node_fields, NODE_FIELD_TYPES), QgsWkbTypes.Point, crs)
        set_output_layer_name(context, node_id, layer_name(first_network, "nodes"))
        link_sink, link_id = self.parameterAsSink(parameters, self.OUTPUT_LINES, context, qfields(link_fields, LINK_FIELD_TYPES), QgsWkbTypes.LineString, crs)
        set_output_layer_name(context, link_id, layer_name(first_network, "links"))

        netcnt = nodcnt = lnkcnt = 0
        for index, network in enumerate(selected_networks):
            netcnt += 1
            node_fields = network["node_fields"]
            link_fields = network["link_fields"]
            node_features = [node_feature(node, node_fields) for node in network['nodes'].values()]
            link_features = [link_feature(network, link, link_fields) for link in network['links'].values()]
            nodcnt += len(node_features)
            lnkcnt += len(link_features)
            if index > 0:
                add_memory_layer(layer_name(network, "nodes"), "Point", qfields(node_fields, NODE_FIELD_TYPES), crs, node_features, context)
                add_memory_layer(layer_name(network, "links"), "LineString", qfields(link_fields, LINK_FIELD_TYPES), crs, link_features, context)
                continue
            for feature in node_features:
                node_sink.addFeature(feature)
            for feature in link_features:
                link_sink.addFeature(feature)

        feedback.setProgress(100)
        info(feedback, "Input file", xml_file)
        info(feedback, "Input format", "LandXML 1.2")
        info(feedback, "Networks imported", netcnt)
        info(feedback, "Network names", ", ".join(selected_names))
        info(feedback, "Nodes imported", nodcnt)
        info(feedback, "Links imported", lnkcnt)
        finish(feedback)
        if feedback.isCanceled():
            return {}
        return {self.OUTPUT_NODES: node_id, self.OUTPUT_LINES: link_id}
