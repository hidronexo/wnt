"""Update demand assignments after editing connection lines."""

from qgis.core import (QgsProcessing,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource,
                       QgsWkbTypes
                       )
from .base import (WntProcessingAlgorithm, missing_fields, numeric_value,
                   require_projected_crs)
from .messages import crs as log_crs
from .messages import error, finish, info, message, start

POS_TOLERANCE = 1e-4

class UpdateAssignmentAlgorithm(WntProcessingAlgorithm):
    """
    Update demands.
    """

    # DEFINE CONSTANTS
    INPUT_SOURCE = 'INPUT_SOURCE'
    INPUT_TARGET = 'INPUT_TARGET'
    INPUT_ASSIGNMENTS = 'INPUT_ASSIGNMENTS'
    OUTPUT_TARGETS = 'OUTPUT_TARGETS'
    OUTPUT_ASSIGNMENTS = 'OUTPUT_ASSIGNMENTS'


    def createInstance(self):
        """
        Create a instance and return a new copy of algorithm.
        """
        return UpdateAssignmentAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        return 'update_assignment'

    def displayName(self):
        """
        Returns the translated algorithm name.
        """
        return self.tr('Update assignment')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to.
        """
        return self.tr('Demand')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to.
        """
        return 'demand'

    def shortHelpString(self):
        """
        Returns a localised short help string for the algorithm.
        """
        return self.tr('''<p>Updates demand assignments after editing assignment lines.</p>
<ul>
<li>Recalculates demand values in the target node layer.</li>
<li>Only the target endpoint of an assignment line can be moved.</li>
<li>The source endpoint must remain on the original source feature.</li>
</ul>
        ''')

    def initAlgorithm(self, config=None):
        """
        Define the inputs and outputs of the algorithm.
        """

        # INPUT
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_SOURCE,
                self.tr('Source layer'),
                types=[QgsProcessing.TypeVectorPoint]
                )
            )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_TARGET,
                self.tr('Target junctions layer (JUNCTIONS)'),
                types=[QgsProcessing.TypeVectorPoint]
                )
            )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_ASSIGNMENTS,
                self.tr('Edited assignment layer'),
                types=[QgsProcessing.TypeVectorLine]
                )
            )

        # ADD FEATURE SINKS
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_TARGETS,
                self.tr('Updated target layer')
                )
            )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_ASSIGNMENTS,
                self.tr('Updated assignment layer')
                )
            )


    def processAlgorithm(self, parameters, context, feedback):
        """
        RUN PROCESS
        """
        # INPUT
        slayer = self.parameterAsSource(parameters, self.INPUT_SOURCE, context)
        tlayer = self.parameterAsSource(parameters, self.INPUT_TARGET, context)
        alayer = self.parameterAsSource(parameters, self.INPUT_ASSIGNMENTS, context)

        # CHECK CRS
        crs = slayer.sourceCrs()
        if crs == tlayer.sourceCrs() == alayer.sourceCrs():
            require_projected_crs(crs, feedback)

            # SEND INFORMATION TO THE USER
            start(feedback, self.displayName())
            log_crs(feedback, crs)
        else:
            error(feedback, "Layers have different CRS")

        assignment_missing = missing_fields(alayer, ['source', 'target'])
        if assignment_missing:
            error(feedback, "Assignment layer is missing required fields: " + ", ".join(assignment_missing))
        source_missing = missing_fields(slayer, ['id'])
        if source_missing:
            error(feedback, "Source layer is missing required fields: " + ", ".join(source_missing))
        target_missing = missing_fields(tlayer, ['id'])
        if target_missing:
            error(feedback, "Target layer is missing required fields: " + ", ".join(target_missing))

        # OUTPUT LAYERS
        (assign_sink, assign_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_ASSIGNMENTS,
            context,
            alayer.fields(),
            QgsWkbTypes.LineString,
            crs
            )
        (target_sink, target_layer_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_TARGETS,
            context,
            tlayer.fields(),
            QgsWkbTypes.Point,
            crs
            )

        # CHECK SOURCE POSITION AND READ SOURCE VALUES
        field_names = alayer.fields().names()
        field_names = [name for name in field_names if name not in ("source", "target")]
        if not field_names:
            error(feedback, "Assignment layer must contain at least one demand field")
        source_missing = missing_fields(slayer, field_names)
        if source_missing:
            error(feedback, "Source layer is missing required fields: " + ", ".join(source_missing))
        target_missing = missing_fields(tlayer, field_names)
        if target_missing:
            error(feedback, "Target layer is missing required fields: " + ", ".join(target_missing))

        def assignment_endpoints(feature):
            geometry = feature.geometry()
            try:
                polyline = geometry.asPolyline()
            except (AttributeError, TypeError):
                polyline = []
            if len(polyline) < 2:
                try:
                    multi = geometry.asMultiPolyline()
                except (AttributeError, TypeError):
                    multi = []
                if len(multi) == 1 and len(multi[0]) >= 2:
                    polyline = multi[0]
            if len(polyline) < 2:
                raise ValueError("Assignment geometry must be a LineString with at least two vertices")
            return polyline[0], polyline[-1]

        src_pos = {}
        src_fds = {}
        assignments = []
        for f in slayer.getFeatures():
            src_pos[f["id"]] = f.geometry().asPoint()
            for name in field_names:
                try:
                    src_fds[(f["id"], name)] = numeric_value(f[name], name)
                except ValueError as exc:
                    error(feedback, str(exc))
        for f in alayer.getFeatures():
            source_id = f["source"]
            if source_id not in src_pos:
                error(feedback, f"Assignment references unknown source: {source_id}")
            try:
                start_point, _ = assignment_endpoints(f)
            except ValueError as exc:
                error(feedback, str(exc))
            if start_point.distance(src_pos[source_id]) > POS_TOLERANCE:
                msg = f'Source point misplaced: {source_id}'
                error(feedback, msg)
            for name in field_names:
                f[name] = src_fds[(source_id, name)]
            assignments.append(f)

        # SHOW PROGRESS
        message(feedback, "All sources are placed correctly")
        feedback.setProgress(50)

        # UPDATE TARGET IDS AND RECOMPUTE
        tar_pos = {}
        values = {}
        cnt = 0
        for f in tlayer.getFeatures():
            tar_pos[f["id"]] = f.geometry().asPoint()
            for name in field_names:
                values[(f["id"], name)] = 0
        for f in assignments:
            target_id = f["target"]
            if target_id not in tar_pos:
                error(feedback, f"Assignment references unknown target: {target_id}")
            try:
                _, end_point = assignment_endpoints(f)
            except ValueError as exc:
                error(feedback, str(exc))
            if end_point.distance(tar_pos[target_id]) > POS_TOLERANCE:
                for id_, point in tar_pos.items():
                    if end_point.distance(point) <= POS_TOLERANCE:
                        msg = f'Updated position of target from: {target_id}'
                        msg += f' to: {id_}'
                        f["target"] = id_
                        target_id = id_
                        cnt += 1
                        message(feedback, msg)
                        break
                else:
                    msg = f'Misassignment. Source: {f["source"]}'
                    msg += f' target: {target_id}'
                    error(feedback, msg)
            for name in field_names:
                try:
                    values[(target_id, name)] += numeric_value(f[name], name)
                except ValueError as exc:
                    error(feedback, str(exc))
        info(feedback, "Updated targets", cnt)
        # WRITE ASSIGNMENT LAYER
        for f in assignments:
            assign_sink.addFeature(f)

        # WRITE TARGET LAYER
        for f in tlayer.getFeatures():
            for name in field_names:
                f[name] = values[f['id'], name]
            target_sink.addFeature(f)

        # SHOW PROGRESS
        feedback.setProgress(100)

        # SHOW PROGRESS
        info(feedback, "Source features", slayer.featureCount())
        info(feedback, "Target features", tlayer.featureCount())
        info(feedback, "Assignment features", alayer.featureCount())
        finish(feedback)

        # PROCESS CANCELED
        if feedback.isCanceled():
            return {}

        # OUTPUT
        return {self.OUTPUT_ASSIGNMENTS: assign_id, self.OUTPUT_TARGETS: target_layer_id}
