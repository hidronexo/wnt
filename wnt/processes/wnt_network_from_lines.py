"""Build network node and link layers from line features."""

from collections import defaultdict
from math import dist, isfinite
from qgis.PyQt.QtCore import QMetaType
from qgis.core import (QgsFeature,
                       QgsField,
                       QgsFields,
                       QgsGeometry,
                       QgsProject,
                       QgsCoordinateTransform,
                       QgsWkbTypes,
                       QgsProcessing,
                       QgsProcessingParameterDefinition,
                       QgsProcessingParameterCrs,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterField,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterRasterLayer,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterDistance,
                       QgsProcessingParameterString,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource,
                       QgsUnitTypes,
                       QgsPointXY
                       )
from .base import WntProcessingAlgorithm, require_projected_crs, set_output_layer_name
from .widgets import LandXmlSurfaceWidgetWrapper
from ..utils import utils_core as tools
from ..utils import utils_graph as graph
from ..utils.utils_tin import TIN
from .messages import crs as log_crs
from .messages import error, finish, info
from .messages import start as log_start


ELEVATION_NONE = 0
ELEVATION_LINE_Z = 1
ELEVATION_DEM = 2
ELEVATION_LANDXML = 3
ELEVATION_OPTIONS = (
    'None',
    'Line endpoint Z',
    'DEM raster',
    'LandXML TIN',
)
TOPOLOGY_VALUES = {
    'BRANCHED': 'branched',
    'MESHED': 'mesh',
}
PROGRESS_READ = 20
PROGRESS_BUILD = 35
PROGRESS_ELEVATION = 50
PROGRESS_NODES = 70
PROGRESS_LINKS = 95


def layer_base_name(layer):
    """Return a stable base name for generated output layers."""
    for attribute in ('sourceName', 'name'):
        if hasattr(layer, attribute):
            value = getattr(layer, attribute)()
            if value:
                return value
    return 'network_from_lines'

class NetworkFromLinesAlgorithm(WntProcessingAlgorithm):
    """
    Build a network from line features.
    """

    # DEFINE CONSTANTS
    INPUT = 'INPUT'
    CRS = 'CRS'
    TOLERANCE = 'TOLERANCE'
    MASK_NODE = 'MASK_NODE'
    INITIAL_NODE = 'INITIAL_NODE'
    INCREMENT_NODE = 'INCREMENT_NODE'
    MASK_LINK = 'MASK_LINK'
    INITIAL_LINK = 'INITIAL_LINK'
    INCREMENT_LINK = 'INCREMENT_LINK'
    LINK_TYPE_FIELD = 'LINK_TYPE_FIELD'
    ADD_NODE_DEGREE = 'ADD_NODE_DEGREE'
    ADD_LINK_TOPOLOGY = 'ADD_LINK_TOPOLOGY'
    ELEVATION_SOURCE = 'ELEVATION_SOURCE'
    INPUT_DEM = 'INPUT_DEM'
    INPUT_LANDXML = 'INPUT_LANDXML'
    SURFACE_NAME = 'SURFACE_NAME'
    OUTPUT_NODES = 'OUTPUT_NODES'
    OUTPUT_LINES = 'OUTPUT_LINES'


    def createInstance(self):
        """
        Create a instance and return a new copy of algorithm.
        """
        return NetworkFromLinesAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        return 'network_from_lines'

    def displayName(self):
        """
        Returns the translated algorithm name.
        """
        return self.tr('Network from lines')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to.
        """
        return self.tr('Build')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to.
        """
        return 'build'

    def shortHelpString(self):
        """
        Returns a localised short help string for the algorithm.
        """
        return self.tr('''<p>Builds EPANET-style network node and link layers from input line features.</p>
<ul>
<li>Output geometries are created in the selected coordinate reference system.</li>
<li>Line endpoints closer than the tolerance are merged into a single node.</li>
<li>The node layer contains <code>id</code>, <code>type</code>, and <code>elevation</code>; node type defaults to <code>JUNCTION</code>.</li>
<li>The link layer contains <code>id</code>, <code>start</code>, <code>end</code>, <code>type</code>, and <code>length</code>.</li>
<li>When a <code>link_type</code> field is selected, link type values are copied from the input features.</li>
<li>Optional fields can add node degree and link topology data.</li>
<li>Node elevations can be left at zero, copied from line endpoint Z values, sampled from a DEM raster, or interpolated from a LandXML TIN surface.</li>
<li>Input layer fields are preserved in the output link layer.</li>
<li>Multipart geometries are split into individual output links.</li>
</ul>
<p>Looped lines are rejected.</p>
        ''')

    def initAlgorithm(self, config=None):
        """
        Define the inputs and outputs of the algorithm.
        """

        # INPUT
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Line vector layer input'),
                types=[QgsProcessing.TypeVectorLine]
                )
            )
        self.addParameter(
            QgsProcessingParameterCrs(
                self.CRS,
                self.tr('Coordinate reference system (CRS)'),
                defaultValue='ProjectCrs'
                )
            )
        tolerance_parameter = QgsProcessingParameterDistance(
            self.TOLERANCE,
            self.tr('Minimum node separation, otherwise merge them'),
            defaultValue=0.001,
            minValue=0.001,
            maxValue=1000.0,
            parentParameterName=self.CRS
            )
        tolerance_parameter.setDefaultUnit(QgsUnitTypes.DistanceMeters)
        self.addParameter(tolerance_parameter)
        self.addParameter(
            QgsProcessingParameterString(
                self.MASK_NODE,
                self.tr('Node mask (P-$$-S generates P-01-S)'),
                defaultValue='$'
                )
            )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INITIAL_NODE,
                self.tr('Number of the first node'),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=1
                )
            )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INCREMENT_NODE,
                self.tr('Node numbering increment'),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=1
                )
            )
        self.addParameter(
            QgsProcessingParameterString(
                self.MASK_LINK,
                self.tr('Link mask (P-$$-S generates P-01-S)'),
                defaultValue='$'
                )
            )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INITIAL_LINK,
                self.tr('Number of first link'),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=1
                )
            )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.INCREMENT_LINK,
                self.tr('Link numbering increment'),
                type=QgsProcessingParameterNumber.Integer,
                defaultValue=1
                )
            )
        self.addParameter(
            QgsProcessingParameterField(
                self.LINK_TYPE_FIELD,
                self.tr('Link type field'),
                None,
                self.INPUT,
                allowMultiple=False,
                optional=True
                )
            )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ADD_NODE_DEGREE,
                self.tr('Add node_degree field'),
                defaultValue=False
                )
            )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.ADD_LINK_TOPOLOGY,
                self.tr('Add topology and zone fields'),
                defaultValue=False
                )
            )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.ELEVATION_SOURCE,
                self.tr('Node elevation source'),
                options=[self.tr(option) for option in ELEVATION_OPTIONS],
                defaultValue=ELEVATION_NONE,
                optional=False
                )
            )
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_DEM,
                self.tr('DEM raster layer input'),
                optional=True
                )
            )
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_LANDXML,
                self.tr('LandXML file'),
                extension='xml',
                optional=True
                )
            )
        surface_parameter = QgsProcessingParameterString(
            self.SURFACE_NAME,
            self.tr('Surface name (if empty, first found)'),
            defaultValue='',
            multiLine=False,
            optional=True
            )
        surface_parameter.setMetadata({
            'widget_wrapper': {'class': LandXmlSurfaceWidgetWrapper},
            'landxml_file_parameter': self.INPUT_LANDXML,
        })
        self.addParameter(
            surface_parameter
            )

        # ADD NODE AND LINK FEATURE SINK
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_NODES,
                self.tr('Network node layer')
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LINES,
                self.tr('Network link layer')
            )
        )

        from .category_sinks import add_outputs
        for key in (self.OUTPUT_NODES, self.OUTPUT_LINES):
            parameter = self.parameterDefinition(key)
            parameter.setFlags(parameter.flags() | QgsProcessingParameterDefinition.FlagHidden | QgsProcessingParameterDefinition.FlagOptional)
        add_outputs(self, ('JUNCTIONS', 'PIPES', 'PUMPS', 'VALVES'))

    def parameterAsSink(self, parameters, name, context, fields, geometry, crs, *args, **kwargs):
        if (self.parameterDefinition('OUTPUT_PIPES') is not None
                and self.OUTPUT_NODES not in parameters and self.OUTPUT_LINES not in parameters
                and name in (self.OUTPUT_NODES, self.OUTPUT_LINES)):
            from .category_sinks import create_sinks
            point = name == self.OUTPUT_NODES
            categories = ('JUNCTIONS',) if point else ('PIPES', 'PUMPS', 'VALVES')
            sink, outputs = create_sinks(self, parameters, context, fields, geometry, crs,
                                         point, categories, super().parameterAsSink)
            self._category_outputs.update(outputs)
            return sink, next(iter(outputs.values()))
        return super().parameterAsSink(parameters, name, context, fields, geometry, crs, *args, **kwargs)

    def checkParameterValues(self, parameters, context):
        """
        Validate algorithm parameters before running.
        """
        ninc = self.parameterAsInt(parameters, self.INCREMENT_NODE, context)
        if ninc == 0:
            return False, self.tr(
                'Node numbering increment must be an integer different from 0'
            )

        linc = self.parameterAsInt(parameters, self.INCREMENT_LINK, context)
        if linc == 0:
            return False, self.tr(
                'Link numbering increment must be an integer different from 0'
            )

        return super().checkParameterValues(parameters, context)

    def processAlgorithm(self, parameters, context, feedback):
        self._category_outputs = {}
        """
        RUN PROCESS
        """
        # INPUT
        linelayer = self.parameterAsSource(parameters, self.INPUT, context)
        output_crs = self.parameterAsCrs(parameters, self.CRS, context)
        tol = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        nmask = self.parameterAsString(parameters, self.MASK_NODE, context)
        nini = self.parameterAsInt(parameters, self.INITIAL_NODE, context)
        ninc = self.parameterAsInt(parameters, self.INCREMENT_NODE, context)
        lmask = self.parameterAsString(parameters, self.MASK_LINK, context)
        lini = self.parameterAsInt(parameters, self.INITIAL_LINK, context)
        linc = self.parameterAsInt(parameters, self.INCREMENT_LINK, context)
        link_type_field = self.parameterAsString(parameters, self.LINK_TYPE_FIELD, context)
        add_node_degree = self.parameterAsBool(parameters, self.ADD_NODE_DEGREE, context)
        add_link_topology = self.parameterAsBool(parameters, self.ADD_LINK_TOPOLOGY, context)
        elevation_source = self.parameterAsEnum(parameters, self.ELEVATION_SOURCE, context)
        dem_layer = (
            self.parameterAsRasterLayer(parameters, self.INPUT_DEM, context)
            if elevation_source == ELEVATION_DEM else None
        )
        landxml_file = (
            self.parameterAsFile(parameters, self.INPUT_LANDXML, context)
            if elevation_source == ELEVATION_LANDXML else ''
        )
        surface_name = (
            self.parameterAsString(parameters, self.SURFACE_NAME, context)
            if elevation_source == ELEVATION_LANDXML else ''
        )

        # SEND INFORMATION TO THE USER
        require_projected_crs(output_crs, feedback)
        log_start(feedback, self.displayName())
        log_crs(feedback, output_crs)
        self._log_options(
            feedback,
            elevation_source,
            dem_layer,
            landxml_file,
            surface_name,
            link_type_field,
            add_node_degree,
            add_link_topology,
            linelayer,
        )

        input_crs = linelayer.sourceCrs()
        transform = None
        if input_crs != output_crs:
            transform = QgsCoordinateTransform(input_crs, output_crs, QgsProject.instance())

        # READ LINESTRINGS
        lines = []
        line_attrs = []
        line_elevations = []
        line_types = []
        feedback.pushInfo("Reading input geometries...")
        total_features = linelayer.featureCount() if hasattr(linelayer, 'featureCount') else 0
        read_count = 0
        for feature in linelayer.getFeatures():
            if feedback.isCanceled():
                return {}
            geom = feature.geometry()
            if transform is not None:
                geom.transform(transform)
            for line in self._line_parts(geom):
                if len(line) < 2:
                    error(feedback, f"Invalid LineString geometry (FID: {feature.id()})")

                start = tools.xy(line[0])
                end = tools.xy(line[-1])
                if dist(start, end) <= tol:
                    error(feedback, f"Looped LineString detected (FID: {feature.id()})")

                lines.append(line)
                line_attrs.append(feature.attributes())
                line_elevations.append((self._point_z(line[0]), self._point_z(line[-1])))
                line_types.append(self._link_type(feature, link_type_field))
            read_count += 1
            self._set_progress(feedback, 0, PROGRESS_READ, read_count, total_features)

        info(feedback, "Input lines", len(lines))
        feedback.setProgress(PROGRESS_READ)

        # CONFIG
        def n_format(index):
            return tools.format_id(nini + index*ninc, nmask)

        def l_format(index):
            return tools.format_id(lini + index*linc, lmask)

        # CALCULATE NETWORK
        nodes, links = tools.net_from_linestrings(lines, tol)
        feedback.setProgress(PROGRESS_BUILD)
        node_ids = [n_format(index) for index in range(len(nodes))]
        link_records = [
            (l_format(index), node_ids[link[0]], node_ids[link[1]])
            for index, link in enumerate(links)
        ]
        node_elevations = self._elevations(
            elevation_source,
            nodes,
            links,
            line_elevations,
            tol,
            dem_layer,
            landxml_file,
            surface_name,
            feedback,
        )
        if node_elevations is None:
            return {}
        feedback.setProgress(PROGRESS_ELEVATION)
        node_degrees = graph.node_degrees_from_records(node_ids, link_records) if add_node_degree else {}
        link_topology = self._link_topology(link_records) if add_link_topology else {}

        # GENERATE NODE LAYER
        node_fields = QgsFields()
        node_fields.append(QgsField("id", QMetaType.QString))
        node_fields.append(QgsField("type", QMetaType.QString))
        node_fields.append(QgsField("elevation", QMetaType.Double))
        if add_node_degree:
            node_fields.append(QgsField("node_degree", QMetaType.Int))
        (node_sink, node_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_NODES,
            context,
            node_fields,
            QgsWkbTypes.Point,
            output_crs
            )
        if not self._category_outputs:
            set_output_layer_name(context, node_id, f'{layer_base_name(linelayer)}_nodes')

        # ADD NODE FEATURES (Bulk)
        node_features = []
        for ncnt, (x, y) in enumerate(nodes):
            nodeid = node_ids[ncnt]
            elevation = node_elevations.get(ncnt, 0.0)
            f = QgsFeature(node_fields)
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
            attrs = [nodeid, 'JUNCTION', elevation]
            if add_node_degree:
                attrs.append(node_degrees[nodeid])
            f.setAttributes(attrs)
            node_features.append(f)

            if len(node_features) >= 200:
                node_sink.addFeatures(node_features)
                node_features = []
            self._set_progress(feedback, PROGRESS_ELEVATION, PROGRESS_NODES, ncnt + 1, len(nodes))
            if feedback.isCanceled():
                return {}

        if node_features:
            node_sink.addFeatures(node_features)
        feedback.setProgress(PROGRESS_NODES)

        # GENERATE LINK LAYER
        link_fields = QgsFields()
        link_fields.append(QgsField("id", QMetaType.QString))
        link_fields.append(QgsField("start", QMetaType.QString))
        link_fields.append(QgsField("end", QMetaType.QString))
        link_fields.append(QgsField("type", QMetaType.QString))
        link_fields.append(QgsField("length", QMetaType.Double))
        if add_link_topology:
            link_fields.append(QgsField("topology", QMetaType.QString))
            link_fields.append(QgsField("zone", QMetaType.Int))
        used_field_names = set(link_fields.names())
        for source_field in linelayer.fields():
            source_name = source_field.name()
            output_name = source_name
            suffix = 1
            while output_name in used_field_names:
                suffix_text = "_src" if suffix == 1 else f"_src{suffix}"
                output_name = f"{source_name}{suffix_text}"
                suffix += 1
            copied_field = QgsField(source_field)
            copied_field.setName(output_name)
            link_fields.append(copied_field)
            used_field_names.add(output_name)
        (link_sink, link_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_LINES,
            context,
            link_fields,
            QgsWkbTypes.LineString,
            output_crs
            )
        if not self._category_outputs:
            set_output_layer_name(context, link_id, f'{layer_base_name(linelayer)}_links')

        # ADD LINK FEATURES (Bulk)
        link_features = []
        for lcnt, link in enumerate(links):
            linkid, start_id, end_id = link_records[lcnt]

            # Use points from the adjusted geometry (links[lcnt][2])
            poly = [QgsPointXY(x, y) for x, y in link[2]]
            length = tools.polyline_length(poly)

            attr = [linkid, start_id, end_id, line_types[lcnt], length]
            if add_link_topology:
                attr.extend(link_topology[linkid])
            attr.extend(line_attrs[lcnt])

            g = QgsFeature(link_fields)
            g.setGeometry(QgsGeometry.fromPolylineXY(poly))
            g.setAttributes(attr)
            link_features.append(g)
            if len(link_features) >= 200:
                link_sink.addFeatures(link_features)
                link_features = []
            self._set_progress(feedback, PROGRESS_NODES, PROGRESS_LINKS, lcnt + 1, len(links))
            if feedback.isCanceled():
                return {}

        if link_features:
            link_sink.addFeatures(link_features)
        feedback.setProgress(PROGRESS_LINKS)

        info(feedback, "Output nodes", len(nodes))
        info(feedback, "Output links", len(links))
        finish(feedback)
        feedback.setProgress(100)

        if feedback.isCanceled():
            return {}

        return self._category_outputs or {self.OUTPUT_NODES: node_id, self.OUTPUT_LINES: link_id}

    def _log_options(
            self,
            feedback,
            elevation_source,
            dem_layer,
            landxml_file,
            surface_name,
            link_type_field,
            add_node_degree,
            add_link_topology,
            linelayer):
        """Write selected processing options to the log."""
        elevation_label = (
            ELEVATION_OPTIONS[elevation_source]
            if 0 <= elevation_source < len(ELEVATION_OPTIONS)
            else "<unknown>"
        )
        info(feedback, "Node elevation source", elevation_label)
        if elevation_source == ELEVATION_DEM:
            info(feedback, "DEM raster layer", self._layer_name(dem_layer))
        elif elevation_source == ELEVATION_LANDXML:
            info(feedback, "LandXML file", landxml_file or "<not selected>")
            info(feedback, "LandXML surface", surface_name or "<first found>")
        info(feedback, "Link type field", link_type_field or "<default PIPE>")
        info(feedback, "Add node_degree", add_node_degree)
        info(feedback, "Add topology/zone", add_link_topology)
        base_name = layer_base_name(linelayer)
        info(feedback, "Output node layer name", f"{base_name}_nodes")
        info(feedback, "Output link layer name", f"{base_name}_links")

    @staticmethod
    def _layer_name(layer):
        """Return a readable layer name for logs."""
        if layer is None:
            return "<not selected>"
        for attribute in ('sourceName', 'name'):
            if hasattr(layer, attribute):
                value = getattr(layer, attribute)()
                if value:
                    return value
        return str(layer)

    @staticmethod
    def _set_progress(feedback, start, end, count, total):
        """Set progress within a bounded phase."""
        if total <= 0:
            return
        feedback.setProgress(start + (end - start) * count / total)

    @staticmethod
    def _link_type(feature, field_name):
        """Return the output link type for a source feature."""
        if not field_name:
            return 'PIPE'
        try:
            value = feature[field_name]
        except (KeyError, IndexError):
            return 'PIPE'
        return value if value not in (None, '') else 'PIPE'

    @staticmethod
    def _link_topology(link_records):
        """Return link topology attributes from output link records."""
        netg = graph.Graph()
        for link_id, start_id, end_id in link_records:
            netg.add_edge(link_id, start_id, end_id)
        classified = graph.unique_zone_classification(netg.classify())
        return {
            link_id: [TOPOLOGY_VALUES[topology], zone]
            for link_id, (topology, zone) in classified.items()
        }

    def _elevations(
            self,
            elevation_source,
            nodes,
            links,
            line_elevations,
            tol,
            dem_layer,
            landxml_file,
            surface_name,
            feedback):
        """Return node elevations from the selected optional source."""
        if elevation_source == ELEVATION_NONE:
            return {}
        if elevation_source == ELEVATION_LINE_Z:
            if any(start_z is None or end_z is None for start_z, end_z in line_elevations):
                error(feedback, "Line endpoint Z elevation source requires every input line endpoint to have a valid Z value")
                return None
            elevations = self._node_elevations(links, line_elevations, tol)
            if elevations is None:
                error(feedback, "Line endpoint elevations merged into a node differ more than tolerance")
            return elevations
        if elevation_source == ELEVATION_DEM:
            if dem_layer is None:
                error(feedback, "DEM raster layer is required for the selected elevation source")
                return None
            return self._dem_elevations(nodes, dem_layer, feedback)
        if elevation_source == ELEVATION_LANDXML:
            if not landxml_file:
                error(feedback, "LandXML file is required for the selected elevation source")
                return None
            return self._landxml_elevations(nodes, landxml_file, surface_name, feedback)
        error(feedback, "Unknown node elevation source")
        return None

    @staticmethod
    def _dem_elevations(nodes, dem_layer, feedback):
        """Return elevations sampled from a DEM raster layer."""
        elevations = {}
        provider = dem_layer.dataProvider()
        for index, (x, y) in enumerate(nodes):
            value, ok = provider.sample(QgsPointXY(x, y), 1)
            if not ok or not NetworkFromLinesAlgorithm._valid_elevation(value):
                error(feedback, "DEM raster does not provide a valid elevation for all network nodes")
                return None
            elevations[index] = float(value)
        info(feedback, "Node elevations added from DEM", len(elevations))
        return elevations

    @staticmethod
    def _landxml_elevations(nodes, landxml_file, surface_name, feedback):
        """Return elevations interpolated from a LandXML TIN surface."""
        surface = TIN()
        try:
            surface.from_landxml(landxml_file, surface_name)
        except Exception as exc:
            error(feedback, str(exc))
            return None
        values = surface.elevations(nodes)
        elevations = {}
        for index, value in enumerate(values):
            if not NetworkFromLinesAlgorithm._valid_elevation(value):
                error(feedback, "LandXML TIN does not provide a valid elevation for all network nodes")
                return None
            elevations[index] = float(value)
        info(feedback, "Node elevations added from LandXML TIN", len(elevations))
        info(feedback, "LandXML surface used", getattr(surface, "surface_name", surface_name or "<first found>"))
        return elevations

    @staticmethod
    def _valid_elevation(value):
        """Return True when value is a finite numeric elevation."""
        if value is None:
            return False
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return False
        return isfinite(numeric)

    @staticmethod
    def _line_parts(geometry):
        """Return single-part QGIS polylines from a line or multiline geometry."""
        if hasattr(geometry, 'constGet'):
            geometry_object = geometry.constGet()
            if hasattr(geometry_object, 'numGeometries'):
                return [
                    NetworkFromLinesAlgorithm._points_from_line(geometry_object.geometryN(index))
                    for index in range(geometry_object.numGeometries())
                ]
            return [NetworkFromLinesAlgorithm._points_from_line(geometry_object)]

        if hasattr(geometry, 'asMultiPolyline'):
            lines = geometry.asMultiPolyline()
            if lines:
                return lines
        return [geometry.asPolyline()]

    @staticmethod
    def _points_from_line(line):
        """Return QGIS points from a core line geometry."""
        if hasattr(line, 'numPoints') and hasattr(line, 'pointN'):
            return [line.pointN(index) for index in range(line.numPoints())]
        return list(line)

    @staticmethod
    def _point_z(point):
        """Return a point Z value when present and finite."""
        if not hasattr(point, 'z'):
            return None
        z_value = point.z()
        return z_value if isfinite(z_value) else None

    @staticmethod
    def _node_elevations(links, line_elevations, tol):
        """Return checked node elevations from line endpoint Z values."""
        samples = defaultdict(list)
        for link, (start_z, end_z) in zip(links, line_elevations):
            start_node, end_node, _ = link
            if start_z is not None:
                samples[start_node].append(start_z)
            if end_z is not None:
                samples[end_node].append(end_z)

        elevations = {}
        for node_index, values in samples.items():
            if max(values) - min(values) > tol:
                return None
            elevations[node_index] = sum(values) / len(values)
        return elevations
