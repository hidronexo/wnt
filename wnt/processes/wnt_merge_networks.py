"""Merge two network layer pairs."""

from qgis.core import (QgsCoordinateTransform,
                       QgsFeature,
                       QgsGeometry,
                       QgsPointXY,
                       QgsWkbTypes,
                       QgsProcessing,
                       QgsProcessingParameterCrs,
                       QgsProcessingParameterDistance,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource,
                       QgsProject,
                       QgsSpatialIndex,
                       QgsUnitTypes
                       )
from .base import (WntProcessingAlgorithm, missing_fields, problem_text,
                   require_projected_crs, set_progress)
from ..utils import utils_graph as graph
from .messages import crs as log_crs
from .messages import error, finish, info, start, warning

NEAR_MERGE_FACTOR = 10


def feature_value(feature, field_name):
    """Return a feature attribute, or None when a lightweight test fake lacks it."""
    try:
        return feature[field_name]
    except KeyError:
        return None


def point_xy(point):
    """Return a QgsPointXY from a Qgs/Fake point-like object."""
    return QgsPointXY(point.x(), point.y())


def point_distance(point_a, point_b):
    """Return planar point distance without depending on concrete point classes."""
    dx = point_a.x() - point_b.x()
    dy = point_a.y() - point_b.y()
    return (dx * dx + dy * dy) ** 0.5


def points_within(point_a, point_b, tolerance):
    return point_distance(point_a, point_b) <= tolerance


def line_endpoints(geometry):
    """Return first/last line points, supporting simple and multipart lines."""
    try:
        polyline = geometry.asPolyline()
    except (AttributeError, TypeError):
        polyline = []
    if len(polyline) >= 2:
        return polyline[0], polyline[-1]

    try:
        multi = geometry.asMultiPolyline()
    except (AttributeError, TypeError):
        multi = []
    for part in multi:
        if len(part) >= 2:
            return part[0], part[-1]
    return None


def link_endpoints(feature, nodes_by_id):
    """Return link endpoints from geometry, falling back to start/end node IDs."""
    endpoints = line_endpoints(feature.geometry())
    if endpoints is not None:
        return endpoints

    start_node = nodes_by_id.get(feature_value(feature, 'start'))
    end_node = nodes_by_id.get(feature_value(feature, 'end'))
    if start_node is None or end_node is None:
        return None
    return start_node.geometry().asPoint(), end_node.geometry().asPoint()


def links_overlap(link_1, link_2, nodes_1_by_id, nodes_2_by_id, tolerance):
    endpoints_1 = link_endpoints(link_1, nodes_1_by_id)
    endpoints_2 = link_endpoints(link_2, nodes_2_by_id)
    if endpoints_1 is None or endpoints_2 is None:
        return False

    start_1, end_1 = endpoints_1
    start_2, end_2 = endpoints_2
    same_direction = points_within(start_1, start_2, tolerance) and points_within(end_1, end_2, tolerance)
    reverse_direction = points_within(start_1, end_2, tolerance) and points_within(end_1, start_2, tolerance)
    return same_direction or reverse_direction


def snapped_line_geometry(geometry, start_point=None, end_point=None):
    """Return a geometry with its first/last vertex snapped when requested."""
    if start_point is None and end_point is None:
        return geometry

    endpoints = line_endpoints(geometry)
    if endpoints is None:
        return geometry

    try:
        polyline = geometry.asPolyline()
    except (AttributeError, TypeError):
        polyline = []
    if len(polyline) >= 2:
        points = [point_xy(point) for point in polyline]
        if start_point is not None:
            points[0] = point_xy(start_point)
        if end_point is not None:
            points[-1] = point_xy(end_point)
        return QgsGeometry.fromPolylineXY(points)

    try:
        multi = geometry.asMultiPolyline()
    except (AttributeError, TypeError):
        multi = []
    if not multi:
        return geometry

    snapped = []
    for index, part in enumerate(multi):
        points = [point_xy(point) for point in part]
        if index == 0 and len(points) >= 2 and start_point is not None:
            points[0] = point_xy(start_point)
        if index == len(multi) - 1 and len(points) >= 2 and end_point is not None:
            points[-1] = point_xy(end_point)
        snapped.append(points)
    return QgsGeometry.fromMultiPolylineXY(snapped)


def aligned_feature(feature, fields, updates=None, geometry=None):
    """Return a copy of feature with attributes aligned to fields by name."""
    updates = updates or {}
    new_feature = QgsFeature(fields)
    new_feature.setGeometry(geometry if geometry is not None else feature.geometry())
    attributes = []
    fields_source = feature.fields()
    for field in fields:
        field_name = field.name()
        if field_name in updates:
            attributes.append(updates[field_name])
            continue
        index = fields_source.lookupField(field_name)
        attributes.append(feature.attributes()[index] if index >= 0 else None)
    new_feature.setAttributes(attributes)
    return new_feature


def spatial_index(features):
    """Return a spatial index for real QGIS features, or None for lightweight fakes."""
    try:
        return QgsSpatialIndex(iter(features)), {feature.id(): feature for feature in features}
    except (AttributeError, TypeError, RuntimeError):
        return None, {}


def transformed_feature(feature, transform):
    """Return feature with geometry transformed when requested."""
    if transform is None:
        return feature
    copied = QgsFeature(feature)
    geometry = QgsGeometry(feature.geometry())
    geometry.transform(transform)
    copied.setGeometry(geometry)
    return copied


def transformed_features(layer, transform):
    """Return all layer features, transformed to the output CRS when needed."""
    return [transformed_feature(feature, transform) for feature in layer.getFeatures()]


def nearest_node(point, nodes, index=None, by_feature_id=None):
    """Return (feature, distance) for the nearest node in a node feature list."""
    candidates = nodes
    if index is not None:
        nearest_ids = index.nearestNeighbor(point_xy(point), 1)
        indexed_candidates = [by_feature_id[fid] for fid in nearest_ids if fid in by_feature_id]
        if indexed_candidates:
            candidates = indexed_candidates

    nearest_feature = None
    nearest_distance = None
    for feature in candidates:
        distance = point_distance(point, feature.geometry().asPoint())
        if nearest_distance is None or distance < nearest_distance:
            nearest_feature = feature
            nearest_distance = distance
    return nearest_feature, nearest_distance


class MergeNetworksAlgorithm(WntProcessingAlgorithm):
    """
    Merge two WNT network layer pairs.
    """

    # DEFINE CONSTANTS
    INPUT_NODES_1 = 'INPUT_NODES_1'
    INPUT_LINES_1 = 'INPUT_LINES_1'
    INPUT_NODES_2 = 'INPUT_NODES_2'
    INPUT_LINES_2 = 'INPUT_LINES_2'
    CRS = 'CRS'
    TOLERANCE = 'TOLERANCE'
    OUTPUT_NODES = 'OUTPUT_NODES'
    OUTPUT_LINES = 'OUTPUT_LINES'


    def createInstance(self):
        """
        Create a instance and return a new copy of algorithm.
        """
        return MergeNetworksAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        return 'merge_networks'

    def displayName(self):
        """
        Returns the translated algorithm name.
        """
        return self.tr('Merge networks')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to.
        """
        return self.tr('Modify')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to.
        """
        return 'modify'

    def shortHelpString(self):
        """
        Returns a localised short help string for the algorithm.
        """
        return self.tr('''<p>Merges two networks from their node and link layers.</p>
<ul>
<li>Nodes from the second network are connected to nodes from the first network when they are within the tolerance distance in the selected output CRS units.</li>
<li>Connected nodes keep the <code>id</code> and position of the first network node.</li>
<li>Incident links from the second network are renamed and their endpoints are snapped to connected first-network nodes.</li>
<li>Links from the second network must not already exist in the first network by <code>id</code> or by matching endpoints within the tolerance distance.</li>
<li>Near misses are reported when second-network nodes are closer than the configured near-merge factor times the tolerance.</li>
<li>Output node and link layers are written in the selected CRS.</li>
</ul>
        ''')

    def initAlgorithm(self, config=None):
        """
        Define the inputs and outputs of the algorithm.
        """

        # INPUT
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_NODES_1,
                self.tr('First node layer input'),
                types=[QgsProcessing.TypeVectorPoint]
                )
            )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_LINES_1,
                self.tr('First link layer input'),
                types=[QgsProcessing.TypeVectorLine]
                )
            )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_NODES_2,
                self.tr('Second node layer input'),
                types=[QgsProcessing.TypeVectorPoint]
                )
            )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_LINES_2,
                self.tr('Second link layer input'),
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
            self.tr('Tolerance'),
            defaultValue=0.001,
            minValue=0.0,
            parentParameterName=self.CRS
            )
        tolerance_parameter.setDefaultUnit(QgsUnitTypes.DistanceMeters)
        self.addParameter(tolerance_parameter)

        # ADD NODE AND LINK FEATURE SINK
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_NODES,
                self.tr('Merged node layer'),
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LINES,
                self.tr('Merged link layer')
            )
        )

        from .typed_merge import configure
        configure(self)

    def processAlgorithm(self, parameters, context, feedback):
        from .typed_merge import requested, process
        if requested(parameters):
            return process(self, parameters, context, feedback)
        """
        RUN PROCESS
        """
        # INPUT
        n1lay = self.parameterAsSource(parameters, self.INPUT_NODES_1, context)
        l1lay = self.parameterAsSource(parameters, self.INPUT_LINES_1, context)
        n2lay = self.parameterAsSource(parameters, self.INPUT_NODES_2, context)
        l2lay = self.parameterAsSource(parameters, self.INPUT_LINES_2, context)
        output_crs = self.parameterAsCrs(parameters, self.CRS, context)
        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)

        # CHECK CRS
        crs = n1lay.sourceCrs()
        if crs == l1lay.sourceCrs() == n2lay.sourceCrs() == l2lay.sourceCrs():

            # SEND INFORMATION TO THE USER
            require_projected_crs(output_crs, feedback)
            start(feedback, self.displayName())
            log_crs(feedback, output_crs)
        else:
            error(feedback, "Layers have different CRS")

        if feedback.isCanceled():
            return {}
        if tolerance < 0:
            error(feedback, "Tolerance distance must be zero or greater")

        for layer, layer_name, required_fields in (
            (n1lay, "First node layer", ['id']),
            (n2lay, "Second node layer", ['id']),
            (l1lay, "First link layer", ['id', 'start', 'end']),
            (l2lay, "Second link layer", ['id', 'start', 'end']),
        ):
            missing = missing_fields(layer, required_fields)
            if missing:
                error(feedback, layer_name + " is missing required fields: " + ", ".join(missing))

        transform = None
        if crs != output_crs:
            transform = QgsCoordinateTransform(crs, output_crs, QgsProject.instance())

        nodes_1 = transformed_features(n1lay, transform)
        nodes_2 = transformed_features(n2lay, transform)
        links_1 = transformed_features(l1lay, transform)
        links_2 = transformed_features(l2lay, transform)
        nodes_1_by_id = {feature_value(feature, 'id'): feature for feature in nodes_1}
        nodes_2_by_id = {feature_value(feature, 'id'): feature for feature in nodes_2}
        index_1, nodes_1_by_feature_id = spatial_index(nodes_1)

        link_ids_1 = {feature_value(feature, 'id') for feature in links_1}
        duplicate_link_ids = sorted(
            str(feature_value(feature, 'id'))
            for feature in links_2
            if feature_value(feature, 'id') in link_ids_1
        )
        if duplicate_link_ids:
            error(feedback, "Second network link ids already exist in first network: " + ", ".join(duplicate_link_ids))

        overlaps = []
        for link_2 in links_2:
            for link_1 in links_1:
                if links_overlap(link_1, link_2, nodes_1_by_id, nodes_2_by_id, tolerance):
                    overlaps.append("%s overlaps %s" % (feature_value(link_2, 'id'), feature_value(link_1, 'id')))
                    break
        if overlaps:
            error(feedback, "Second network links overlap first network links: " + ", ".join(overlaps))

        # Resolve second-network node connections before creating sinks.
        node_id_map = {}
        near_nodes = []
        nearest_near = None
        for node in nodes_2:
            nearest, distance = nearest_node(node.geometry().asPoint(), nodes_1, index_1, nodes_1_by_feature_id)
            if nearest is None or distance is None:
                continue
            if distance <= tolerance:
                node_id_map[feature_value(node, 'id')] = feature_value(nearest, 'id')
            elif distance < tolerance * NEAR_MERGE_FACTOR:
                record = (distance, feature_value(node, 'id'), feature_value(nearest, 'id'))
                near_nodes.append(record)
                if nearest_near is None or distance < nearest_near[0]:
                    nearest_near = record

        final_node_ids = [feature_value(feature, 'id') for feature in nodes_1]
        final_node_ids.extend(
            feature_value(feature, 'id')
            for feature in nodes_2
            if feature_value(feature, 'id') not in node_id_map
        )
        final_links = [
            (feature_value(feature, 'id'), feature_value(feature, 'start'), feature_value(feature, 'end'))
            for feature in links_1
        ]
        for feature in links_2:
            start_id = feature_value(feature, 'start')
            end_id = feature_value(feature, 'end')
            final_links.append((
                feature_value(feature, 'id'),
                node_id_map.get(start_id, start_id),
                node_id_map.get(end_id, end_id),
            ))
        problems = graph.validate_records(final_node_ids, final_links)
        validation_text = problem_text(problems)
        if validation_text:
            error(feedback, "Merged network is not valid: " + validation_text)

        # GENERATE MERGED NODE LAYER
        node_fields = n1lay.fields()
        for field in n2lay.fields():
            if node_fields.lookupField(field.name()) < 0:
                node_fields.append(field)
        (node_sink, node_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_NODES,
            context,
            node_fields,
            QgsWkbTypes.Point,
            output_crs
            )

        # GENERATE MERGED LINK LAYER
        link_fields = l1lay.fields()
        for field in l2lay.fields():
            if link_fields.lookupField(field.name()) < 0:
                link_fields.append(field)
        (link_sink, link_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_LINES,
            context,
            link_fields,
            QgsWkbTypes.LineString,
            output_crs
            )

        # ADD NODES FROM FIRST NODE LAYER
        total_nodes = len(nodes_1) + len(nodes_2)
        output_node_count = 0
        for count, feature in enumerate(nodes_1, start=1):
            if feedback.isCanceled():
                return {}
            node_sink.addFeature(aligned_feature(feature, node_fields))
            output_node_count += 1
            set_progress(feedback, 0, 50, count, total_nodes)

        # ADD UNCONNECTED NODES FROM SECOND NODE LAYER
        count = len(nodes_1)
        for feature in nodes_2:
            if feedback.isCanceled():
                return {}
            count += 1
            if feature_value(feature, 'id') not in node_id_map:
                node_sink.addFeature(aligned_feature(feature, node_fields))
                output_node_count += 1
            set_progress(feedback, 0, 50, count, total_nodes)

        # ADD LINKS FROM FIRST NETWORK
        total_links = len(links_1) + len(links_2)
        output_link_count = 0
        for count, feature in enumerate(links_1, start=1):
            if feedback.isCanceled():
                return {}
            link_sink.addFeature(aligned_feature(feature, link_fields))
            output_link_count += 1
            set_progress(feedback, 50, 100, count, total_links)

        # ADD LINKS FROM SECOND NETWORK, RENAMING CONNECTED ENDPOINTS
        count = len(links_1)
        for feature in links_2:
            if feedback.isCanceled():
                return {}
            count += 1
            start_id = feature_value(feature, 'start')
            end_id = feature_value(feature, 'end')
            new_start_id = node_id_map.get(start_id, start_id)
            new_end_id = node_id_map.get(end_id, end_id)
            start_snap = nodes_1_by_id[new_start_id].geometry().asPoint() if start_id in node_id_map else None
            end_snap = nodes_1_by_id[new_end_id].geometry().asPoint() if end_id in node_id_map else None
            geometry = snapped_line_geometry(feature.geometry(), start_snap, end_snap)
            link_sink.addFeature(aligned_feature(
                feature,
                link_fields,
                updates={'start': new_start_id, 'end': new_end_id},
                geometry=geometry,
            ))
            output_link_count += 1
            set_progress(feedback, 50, 100, count, total_links)

        # SHOW INFO
        info(feedback, "First network nodes", len(nodes_1))
        info(feedback, "Second network nodes", len(nodes_2))
        info(feedback, "Output nodes", output_node_count)
        info(feedback, "First network links", len(links_1))
        info(feedback, "Second network links", len(links_2))
        info(feedback, "Output links", output_link_count)
        info(feedback, "Connected nodes", len(node_id_map))
        info(feedback, "Near merge nodes", len(near_nodes))
        if nearest_near is not None:
            distance, node_2_id, node_1_id = nearest_near
            warning(feedback, "Closest near merge node %s to %s distance is %s" % (node_2_id, node_1_id, distance))
        finish(feedback)

        # OUTPUT
        return {self.OUTPUT_NODES: node_id, self.OUTPUT_LINES: link_id}
