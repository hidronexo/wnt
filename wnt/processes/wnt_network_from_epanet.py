"""Import an EPANET model as six typed QGIS layers."""

from pathlib import Path

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    QgsFeature, QgsField, QgsFields, QgsGeometry,
    QgsProcessingLayerPostProcessorInterface, QgsProject,
    QgsProcessingParameterCrs, QgsProcessingParameterEnum,
    QgsProcessingParameterFeatureSink, QgsProcessingParameterFile, QgsWkbTypes,
)

from .base import WntProcessingAlgorithm, set_output_layer_name
from .messages import crs as log_crs
from .messages import error, finish, info, start
from ..utils import utils_core as tools
from ..utils.utils_epanet_model import (
    LAYER_SCHEMAS, detect_epanet_version, normalise_source, read_sections,
)
from ..utils.utils_parser import parse_tokens


TYPE_MAP = {"string": QMetaType.QString, "double": QMetaType.Double}


class ModelLayerPostProcessor(QgsProcessingLayerPostProcessorInterface):
    """Attach model metadata and place a loaded output in its model group."""

    def __init__(self, model_name, source, version, section):
        super().__init__()
        self.model_name = model_name
        self.source = source
        self.version = version
        self.section = section

    def postProcessLayer(self, layer, context, feedback):  # noqa: N802
        layer.setCustomProperty("wnt/model_name", self.model_name)
        layer.setCustomProperty("wnt/source_inp", self.source)
        layer.setCustomProperty("wnt/epanet_version", self.version)
        layer.setCustomProperty("wnt/epanet_section", self.section)
        project = context.project() if context is not None else None
        project = project or QgsProject.instance()
        root = project.layerTreeRoot()
        node = root.findLayer(layer.id())
        if node is None:
            return
        group = root.findGroup(self.model_name) or root.addGroup(self.model_name)
        if node.parent() == group:
            return
        group.addChildNode(node.clone())
        node.parent().removeChildNode(node)


def _tokens(sections, name):
    for line in sections.get(name, []):
        values = parse_tokens(line)
        if values:
            yield values


def _supplemental_properties(sections):
    """Collect supported properties stored outside the physical sections."""
    nodes = {}
    links = {}
    for line in sections.get('DEMANDS', []):
        parts = line.split(None, 1)
        identifier, definition = parts if len(parts) == 2 else (parts[0], '')
        props = nodes.setdefault(identifier, {})
        props['demand_categories'] = '\n'.join(filter(None, (props.get('demand_categories'), definition.strip())))
    for values in _tokens(sections, "EMITTERS"):
        if len(values) >= 2:
            nodes.setdefault(values[0], {})["emitter_coefficient"] = values[1]
    for values in _tokens(sections, "QUALITY"):
        if len(values) >= 2:
            nodes.setdefault(values[0], {})["initial_quality"] = values[1]
    for values in _tokens(sections, "SOURCES"):
        if len(values) >= 3:
            props = nodes.setdefault(values[0], {})
            props.update(source_type=values[1], source_quality=values[2])
            props["source_pattern"] = values[3] if len(values) > 3 else None
    for values in _tokens(sections, "MIXING"):
        if len(values) >= 2:
            props = nodes.setdefault(values[0], {})
            props["mixing_model"] = values[1]
            props["mixing_fraction"] = values[2] if len(values) > 2 else None
    for values in _tokens(sections, "REACTIONS"):
        if len(values) < 3:
            continue
        reaction_type = values[0].upper()
        if reaction_type == "TANK":
            nodes.setdefault(values[1], {})["tank_reaction_coeff"] = values[2]
        elif reaction_type == "BULK":
            links.setdefault(values[1], {})["bulk_reaction_coeff"] = values[2]
        elif reaction_type == "WALL":
            links.setdefault(values[1], {})["wall_reaction_coeff"] = values[2]
    for values in _tokens(sections, "STATUS"):
        if len(values) >= 2:
            links.setdefault(values[0], {})["status"] = " ".join(values[1:])
    for values in _tokens(sections, "ENERGY"):
        if len(values) < 4 or values[0].upper() != "PUMP":
            continue
        field = {"PRICE": "energy_price", "PATTERN": "energy_pattern", "EFFIC": "efficiency_curve"}.get(values[2].upper())
        if field:
            links.setdefault(values[1], {})[field] = values[3]
    for values in _tokens(sections, "TAGS"):
        if len(values) >= 3:
            target = nodes if values[0].upper() == "NODE" else links
            target.setdefault(values[1], {})["tag"] = " ".join(values[2:])
    return nodes, links


def _fields(schema):
    result = QgsFields()
    for name, kind in schema:
        result.append(QgsField(name, TYPE_MAP[kind]))
    return result


def _attributes(schema, values):
    return [values.get(name) for name, _kind in schema]


def _node_values(node, extra, source, version):
    props = dict(node.epanet)
    values = {"id": node.name(), "elevation": node.get_elevation()}
    if node.get_type() == "JUNCTION":
        values.update(base_demand=props.get("demand"), demand_pattern=props.get("pattern"))
    elif node.get_type() == "RESERVOIR":
        values.update(total_head=props.get("head", node.get_elevation()), head_pattern=props.get("pattern"))
    elif node.get_type() == "TANK":
        values.update(
            initial_level=props.get("init_level"), min_level=props.get("min_level"),
            max_level=props.get("max_level"), diameter=props.get("diameter"),
            min_volume=props.get("min_volume"), volume_curve=props.get("volume_curve"),
        )
    values.update(extra.get(node.name(), {}))
    values.update(inp_source=source, epanet_version=version)
    return values


def _link_values(link, extra, source, version):
    props = dict(link.epanet)
    values = {"id": link.name(), "start": link.start(), "end": link.end()}
    link_type = link.get_type()
    if link_type in ("PIPE", "CVPIPE"):
        values.update(
            length=props.get("length"), diameter=props.get("diameter"),
            roughness=props.get("roughness"), minor_loss=props.get("minor_loss"),
            status="CV" if link_type == "CVPIPE" else props.get("status"),
        )
    elif link_type == "PUMP":
        values.update(
            pump_power=props.get("pump_power"), head_curve=props.get("pump_head"),
            pump_speed=props.get("pump_speed"), pump_pattern=props.get("pump_pattern"),
        )
    else:
        values.update(
            diameter=props.get("diameter"), valve_type=link_type,
            valve_setting=props.get("setting"), minor_loss=props.get("minor_loss"),
        )
    values.update(extra.get(link.name(), {}))
    values.update(inp_source=source, epanet_version=version)
    return values


class NetworkFromEpanetAlgorithm(WntProcessingAlgorithm):
    """Create six editable model layers from an EPANET INP file."""

    INPUT = "INPUT"
    CRS = "CRS"
    VERSION_MODE = "VERSION_MODE"
    VERSION_OPTIONS = ("Automatic", "2.0", "2.2")
    OUTPUT_JUNCTIONS = "OUTPUT_JUNCTIONS"
    OUTPUT_RESERVOIRS = "OUTPUT_RESERVOIRS"
    OUTPUT_TANKS = "OUTPUT_TANKS"
    OUTPUT_PIPES = "OUTPUT_PIPES"
    OUTPUT_PUMPS = "OUTPUT_PUMPS"
    OUTPUT_VALVES = "OUTPUT_VALVES"
    OUTPUTS = {
        "JUNCTIONS": OUTPUT_JUNCTIONS, "RESERVOIRS": OUTPUT_RESERVOIRS,
        "TANKS": OUTPUT_TANKS, "PIPES": OUTPUT_PIPES,
        "PUMPS": OUTPUT_PUMPS, "VALVES": OUTPUT_VALVES,
    }

    def createInstance(self):
        return NetworkFromEpanetAlgorithm()

    def name(self):
        return "network_from_epanet"

    def displayName(self):
        return self.tr("Import EPANET model from INP")

    def group(self):
        return self.tr("Import")

    def groupId(self):
        return "import"

    def shortHelpString(self):
        return self.tr(
            "<p>Imports an EPANET INP file as six typed layers: junctions, reservoirs, "
            "tanks, pipes, pumps and valves.</p><p>Every layer contains source-file and "
            "EPANET-version provenance. The former <code>epanet</code> JSON field is not created.</p>"
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFile(self.INPUT, self.tr("EPANET file"), extension="inp"))
        self.addParameter(QgsProcessingParameterCrs(self.CRS, self.tr("Coordinate reference system (CRS)")))
        self.addParameter(QgsProcessingParameterEnum(
            self.VERSION_MODE, self.tr("EPANET version"),
            options=[self.tr(value) for value in self.VERSION_OPTIONS], defaultValue=0,
        ))
        for section, output in self.OUTPUTS.items():
            self.addParameter(QgsProcessingParameterFeatureSink(output, self.tr(section.title())))

    def processAlgorithm(self, parameters, context, feedback):
        inp_path = self.parameterAsFile(parameters, self.INPUT, context)
        crs = self.parameterAsCrs(parameters, self.CRS, context)
        version_mode = self.parameterAsEnum(parameters, self.VERSION_MODE, context)
        model_name = Path(inp_path).stem
        source = normalise_source(inp_path)
        start(feedback, self.displayName())
        log_crs(feedback, crs)

        sections = read_sections(inp_path)
        detected_version = detect_epanet_version(sections)
        version = detected_version if version_mode == 0 else self.VERSION_OPTIONS[version_mode]
        if version_mode == 0 and detected_version == "2.0" and hasattr(feedback, "pushWarning"):
            feedback.pushWarning(self.tr(
                "The INP contains no unambiguous EPANET 2.2 syntax; version 2.0 compatibility was assumed."
            ))
        network = tools.WntNetwork()
        try:
            network.from_epanet(inp_path)
        except (tools.WntError, OSError, ValueError, IndexError) as exc:
            error(feedback, str(exc))
        node_extra, link_extra = _supplemental_properties(sections)

        sinks = {}
        result = {}
        for section, output in self.OUTPUTS.items():
            point_section = section in ("JUNCTIONS", "RESERVOIRS", "TANKS")
            geometry_type = QgsWkbTypes.Point if point_section else QgsWkbTypes.LineString
            sink, destination = self.parameterAsSink(
                parameters, output, context, _fields(LAYER_SCHEMAS[section]), geometry_type, crs
            )
            sinks[section] = sink
            result[output] = destination
            set_output_layer_name(context, destination, f"{model_name}_{section.lower()}")
            if context is not None:
                details = context.layerToLoadOnCompletionDetails(destination)
                details.groupName = model_name
                processor = ModelLayerPostProcessor(model_name, source, version, section)
                if hasattr(details, "setPostProcessor"):
                    details.setPostProcessor(processor)
                else:
                    details.groupName = model_name

        counts = {section: 0 for section in self.OUTPUTS}
        for node in network.nodes():
            if feedback.isCanceled():
                return {}
            section = {"JUNCTION": "JUNCTIONS", "RESERVOIR": "RESERVOIRS", "TANK": "TANKS"}.get(node.get_type())
            if not section:
                continue
            feature = QgsFeature()
            if node.to_wkt():
                feature.setGeometry(QgsGeometry.fromWkt(node.to_wkt()))
            feature.setAttributes(_attributes(
                LAYER_SCHEMAS[section], _node_values(node, node_extra, source, version)
            ))
            if not sinks[section].addFeature(feature):
                error(feedback, 'Could not write ' + section)
            counts[section] += 1

        for link in network.links():
            if feedback.isCanceled():
                return {}
            link_type = link.get_type()
            section = "PIPES" if link_type in ("PIPE", "CVPIPE") else "PUMPS" if link_type == "PUMP" else "VALVES"
            feature = QgsFeature()
            if link.to_wkt():
                feature.setGeometry(QgsGeometry.fromWkt(link.to_wkt()))
            feature.setAttributes(_attributes(
                LAYER_SCHEMAS[section], _link_values(link, link_extra, source, version)
            ))
            if not sinks[section].addFeature(feature):
                error(feedback, 'Could not write ' + section)
            counts[section] += 1

        info(feedback, "Input file", source)
        info(feedback, "EPANET version", version)
        for section, count in counts.items():
            info(feedback, f"{section.title()} imported", count)
        finish(feedback)
        return {} if feedback.isCanceled() else result
