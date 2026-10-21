"""Split line features at point locations."""

from math import floor, hypot
from qgis.core import (Qgis,
                       QgsCoordinateTransform,
                       QgsFeature,
                       QgsGeometry,
                       QgsWkbTypes,
                       QgsPointXY,
                       QgsProcessing,
                       QgsProcessingParameterCrs,
                       QgsProcessingParameterDistance,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsProject,
                       QgsSpatialIndex,
                       QgsUnitTypes
                       )
from .base import (OUTPUT_MODE_NEW, OUTPUT_MODE_UPDATE, OUTPUT_MODE_OPTIONS,
                   WntProcessingAlgorithm, replace_layer_features, require_projected_crs, set_progress)
from .messages import crs as log_crs
from .messages import error, finish, info, start


def _splitter_for_point(geometry, point, tolerance):
    sqr_dist, nearest, next_vertex, _ = geometry.closestSegmentWithContext(point)
    if sqr_dist < 0 or sqr_dist > tolerance * tolerance:
        return None

    vertices = list(geometry.vertices())
    if next_vertex <= 0 or next_vertex >= len(vertices):
        return None

    previous = vertices[next_vertex - 1]
    following = vertices[next_vertex]
    dx = following.x() - previous.x()
    dy = following.y() - previous.y()
    length = hypot(dx, dy)
    if length == 0:
        return None

    offset = max(tolerance * 2, length * 1e-6, 1e-9)
    nx = -dy / length * offset
    ny = dx / length * offset
    return [
        QgsPointXY(nearest.x() - nx, nearest.y() - ny),
        QgsPointXY(nearest.x() + nx, nearest.y() + ny),
    ]


def _split_geometry_at_points(geometry, points, tolerance):
    parts = [QgsGeometry(geometry)]
    for point in points:
        point_xy = QgsPointXY(point[0], point[1])
        point_geometry = QgsGeometry.fromPointXY(point_xy)
        new_parts = []
        for part in parts:
            if part.distance(point_geometry) > tolerance:
                new_parts.append(part)
                continue

            splitter = _splitter_for_point(part, point_xy, tolerance)
            if splitter is None:
                new_parts.append(part)
                continue

            result, split_parts, _ = part.splitGeometry(splitter, False)
            if result == Qgis.GeometryOperationResult.Success and split_parts:
                new_parts.append(part)
                new_parts.extend(split_parts)
            else:
                new_parts.append(part)
        parts = new_parts

    return parts if len(parts) > 1 else None


def _feature_with_geometry(feature, geometry):
    try:
        new_feature = QgsFeature(feature)
    except TypeError:
        new_feature = feature
    new_feature.setGeometry(geometry)
    return new_feature


def _transformed_geometry(feature, transform):
    geometry = feature.geometry()
    if transform is None:
        return geometry
    geometry = QgsGeometry(geometry)
    geometry.transform(transform)
    return geometry


def _line_geometries(geometry):
    if QgsWkbTypes.isMultiType(geometry.wkbType()):
        return [
            QgsGeometry.fromPolylineXY(part)
            for part in geometry.asMultiPolyline()
            if len(part) >= 2
        ]
    return [QgsGeometry(geometry)]


def _deduplicated_points(features, tolerance, feedback, transform=None):
    cell_size = max(tolerance, 1e-12)
    tolerance2 = tolerance * tolerance
    grid = {}
    points = []
    overlapped = 0

    for feature in features:
        if feedback.isCanceled():
            return None, overlapped

        point = _transformed_geometry(feature, transform).asPoint()
        x, y = point.x(), point.y()
        grid_x = floor(x / cell_size)
        grid_y = floor(y / cell_size)
        duplicated = False

        for nx in range(grid_x - 1, grid_x + 2):
            for ny in range(grid_y - 1, grid_y + 2):
                for existing in grid.get((nx, ny), ()):  # nearby cells cover tolerance borders
                    dx = x - existing[0]
                    dy = y - existing[1]
                    if dx * dx + dy * dy <= tolerance2:
                        duplicated = True
                        break
                if duplicated:
                    break
            if duplicated:
                break

        if duplicated:
            overlapped += 1
            continue

        point_tuple = (x, y)
        points.append(point_tuple)
        grid.setdefault((grid_x, grid_y), []).append(point_tuple)

    return points, overlapped


def _spatial_index_for_points(points):
    index = QgsSpatialIndex()
    for fid, point in enumerate(points):
        feature = QgsFeature()
        feature.setId(fid)
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(point[0], point[1])))
        index.addFeature(feature)
    return index


class SplitLinesAtPointsAlgorithm(WntProcessingAlgorithm):
    """
    Split lines at points.
    """

    # DEFINE CONSTANTS
    INPUT_POINTS = 'INPUT_POINTS'
    INPUT_LINES = 'INPUT_LINES'
    CRS = 'CRS'
    TOLERANCE = 'TOLERANCE'
    OUTPUT_MODE = 'OUTPUT_MODE'
    OUTPUT = 'OUTPUT'


    def createInstance(self):
        """
        Create a instance and return a new copy of algorithm.
        """
        return SplitLinesAtPointsAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        return 'split_lines_at_points'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Split lines at points')

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
        return self.tr('''<p>Splits line features at point positions.</p>
<ul>
<li>Use this algorithm to insert junctions or intermediate nodes into line layers.</li>
<li>Points are matched to lines using the tolerance in the selected output CRS units.</li>
<li>Can create a new output layer or replace the input line layer features.</li>
</ul>
        ''')

    def initAlgorithm(self, config=None):
        """
        Define the inputs and outputs of the algorithm.
        """

        #   DEFINE INPUT
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_POINTS,
                self.tr('Input point layer'),
                [QgsProcessing.TypeVectorPoint]
                )
            )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_LINES,
                self.tr('Input line layer'),
                [QgsProcessing.TypeVectorLine]
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
            minValue=0.0001,
            maxValue=1.0,
            parentParameterName=self.CRS
            )
        tolerance_parameter.setDefaultUnit(QgsUnitTypes.DistanceMeters)
        self.addParameter(tolerance_parameter)
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OUTPUT_MODE,
                self.tr('Output mode'),
                options=[self.tr(option) for option in OUTPUT_MODE_OPTIONS],
                defaultValue=OUTPUT_MODE_NEW,
                optional=False
                )
            )

        # DEFINE OUTPUT
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Split line layer'),
                optional=True
                )
            )

    def processAlgorithm(self, parameters, context, feedback):
        """
        RUN PROCESS
        """
        # INPUT
        output_mode = self.parameterAsEnum(parameters, self.OUTPUT_MODE, context)
        pntlayer = self.parameterAsSource(parameters, self.INPUT_POINTS, context)
        if output_mode == OUTPUT_MODE_UPDATE:
            linlayer = self.parameterAsVectorLayer(parameters, self.INPUT_LINES, context)
        else:
            linlayer = self.parameterAsSource(parameters, self.INPUT_LINES, context)
        output_crs = self.parameterAsCrs(parameters, self.CRS, context)
        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)

        # CHECK CRS
        crs = pntlayer.sourceCrs()
        if crs == linlayer.sourceCrs():

            # SEND INFORMATION TO THE USER
            require_projected_crs(output_crs, feedback)
            start(feedback, self.displayName())
            log_crs(feedback, output_crs)
        else:
            error(feedback, "Layers have different CRS")

        from .base import field_names
        fields = field_names(linlayer)
        hydraulic_device = bool(fields.intersection(('pump_power', 'head_curve', 'valve_type')))
        if 'type' in fields:
            hydraulic_device = hydraulic_device or any(str(feature['type']).upper() in (
                'PUMP', 'VALVE', 'PRV', 'PSV', 'PBV', 'FCV', 'TCV', 'GPV') for feature in linlayer.getFeatures())
        if hydraulic_device:
            error(feedback, 'Pumps and valves cannot be split; select PIPES for an EPANET model')
        if output_mode == OUTPUT_MODE_UPDATE and output_crs != linlayer.sourceCrs():
            error(feedback, "Update input layer requires the selected CRS to match the input line layer CRS")

        if output_mode == OUTPUT_MODE_NEW:
            # OUTPUT
            (sink, dest_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT,
                context,
                linlayer.fields(),
                QgsWkbTypes.LineString,
                output_crs
                )
        else:
            sink = None
            dest_id = getattr(linlayer, 'id', lambda: self.INPUT_LINES)()

        transform = None
        if crs != output_crs:
            transform = QgsCoordinateTransform(crs, output_crs, QgsProject.instance())

        # LOAD AND FILTER OVERLAPPED POINTS
        points, overlapped = _deduplicated_points(pntlayer.getFeatures(), tolerance, feedback, transform)
        if feedback.isCanceled() or points is None:
            return {}
        point_index = _spatial_index_for_points(points)
        points_by_id = dict(enumerate(points))

        # SHOW PROGRESS
        info(feedback, "Splitting points", len(points))
        info(feedback, "Overlapped points", overlapped)

        # LOAD AND SPLIT LINES
        cnt = 0                         # output link counter
        tot = linlayer.featureCount()
        processed = 0                   # input feature counter
        replacement_features = []
        # LINES LOOP
        for f in linlayer.getFeatures():
            if feedback.isCanceled():
                return {}

            for geometry in _line_geometries(_transformed_geometry(f, transform)):
                bbox = geometry.boundingBox()
                bbox.grow(tolerance)
                fpoints = [points_by_id[fid] for fid in point_index.intersects(bbox)
                           if fid in points_by_id]

                # SPLIT
                if fpoints:
                    splitted = _split_geometry_at_points(geometry, fpoints, tolerance)
                    if splitted:

                        # ADD NEW LINESTRINGS
                        for part in splitted:
                            feature = _feature_with_geometry(f, part)
                            if output_mode == OUTPUT_MODE_UPDATE:
                                replacement_features.append(feature)
                            else:
                                sink.addFeature(feature)
                            cnt += 1
                    else:

                        # KEEP ORIGINAL FEATURE
                        feature = _feature_with_geometry(f, geometry)
                        if output_mode == OUTPUT_MODE_UPDATE:
                            replacement_features.append(feature)
                        else:
                            sink.addFeature(feature)
                        cnt += 1
                else:

                    # KEEP ORIGINAL FEATURE
                    feature = _feature_with_geometry(f, geometry)
                    if output_mode == OUTPUT_MODE_UPDATE:
                        replacement_features.append(feature)
                    else:
                        sink.addFeature(feature)
                    cnt += 1

            processed += 1
            # SHOW PROGRESS
            set_progress(feedback, 0, 100, processed, tot)

        if output_mode == OUTPUT_MODE_UPDATE:
            try:
                replace_layer_features(linlayer, replacement_features)
            except RuntimeError as exc:
                error(feedback, str(exc))

        info(feedback, "Input lines", tot)
        info(feedback, "Output lines", cnt)
        info(feedback, "Output mode", OUTPUT_MODE_OPTIONS[output_mode])
        finish(feedback)

        # OUTPUT

        return {self.OUTPUT: dest_id}
