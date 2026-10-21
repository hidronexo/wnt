"""Assign demand sources to target network nodes."""

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (QgsFeature,
                       QgsField,
                       QgsFields,
                       QgsPoint,
                       QgsLineString,
                       QgsProcessing,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterField,
                       QgsWkbTypes,
                       QgsSpatialIndex
                      )
from .base import (WntProcessingAlgorithm, missing_fields, numeric_value,
                   require_projected_crs, set_progress)
from .messages import crs as log_crs
from .messages import error, finish, info, start

class AssignDemandAlgorithm(WntProcessingAlgorithm):
    """
    Assignate demands.
    """

    # DEFINE CONSTANTS
    INPUT_SOURCE = 'INPUT_SOURCE'
    FIELDS_SOURCE = 'FIELDS_SOURCE'
    INPUT_TARGET = 'INPUT_TARGET'
    OUTPUT_ASSIGNMENTS = 'OUTPUT_ASSIGNMENTS'
    OUTPUT_NODES = 'OUTPUT_NODES'


    def createInstance(self):
        """
        Create a instance and return a new copy of algorithm.
        """
        return AssignDemandAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        return 'assign_demand'

    def displayName(self):
        """
        Returns the translated algorithm name.
        """
        return self.tr('Assign demand')

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
        return self.tr('''<p>Assigns demand from a <b>source layer</b> to a <b>target node layer</b> using the nearest target feature.</p>
<ul>
<li>Both input layers must contain an <code>id</code> field.</li>
<li>The selected source demand fields are copied and accumulated in the target layer.</li>
<li>The output assignment layer stores the connection lines between source and target features.</li>
</ul>
<p>Use <b>Update assignment</b> after editing assignment lines.</p>
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
            QgsProcessingParameterField(
                self.FIELDS_SOURCE,
                self.tr('Source demand fields'),
                None,
                self.INPUT_SOURCE,
                type=QgsProcessingParameterField.Numeric,
                allowMultiple=True
                )
            )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_TARGET,
                self.tr('Target junctions layer (JUNCTIONS)'),
                types=[QgsProcessing.TypeVectorPoint]
                )
            )

        # ADD PAIRS FEATURE SINK
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_ASSIGNMENTS,
                self.tr('Assignment layer')
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_NODES,
                self.tr('Junctions with demands layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        RUN PROCESS
        """
        # INPUT
        slayer = self.parameterAsSource(parameters, self.INPUT_SOURCE, context)
        sfields = list(self.parameterAsFields(parameters, self.FIELDS_SOURCE, context) or [])
        tlayer = self.parameterAsSource(parameters, self.INPUT_TARGET, context)

        # CHECK CRS
        crs = slayer.sourceCrs()
        if crs != tlayer.sourceCrs():
            error(feedback, "Layers have different CRS")
        require_projected_crs(crs, feedback)

        if not sfields:
            error(feedback, "At least one source demand field is required")

        source_missing = missing_fields(slayer, ['id', *sfields])
        if source_missing:
            error(feedback, "Source layer is missing required fields: " + ", ".join(source_missing))
        target_missing = missing_fields(tlayer, ['id'])
        if target_missing:
            error(feedback, "Target layer is missing required fields: " + ", ".join(target_missing))

        # SEND INFORMATION TO THE USER
        start(feedback, self.displayName())
        log_crs(feedback, crs)

        # OUTPUT LAYERS DEFINITION
        fields = QgsFields()
        fields.append(QgsField('source', QMetaType.QString))
        fields.append(QgsField('target', QMetaType.QString))
        for field in sfields:
            fields.append(QgsField(field, QMetaType.Double))

        (assignment_sink, assignment_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_ASSIGNMENTS,
            context,
            fields,
            QgsWkbTypes.LineString,
            crs
        )

        tfields = tlayer.fields()
        node_fields = QgsFields(tfields)
        existing_node_fields = set(tfields.names())
        for field in sfields:
            if field not in existing_node_fields:
                node_fields.append(QgsField(field, QMetaType.Double))

        (node_sink, node_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT_NODES,
            context,
            node_fields,
            QgsWkbTypes.Point,
            crs
        )

        # FETCH FIELD INDICES
        t_id_idx = tlayer.fields().lookupField('id')
        s_id_idx = slayer.fields().lookupField('id')
        s_field_indices = {field: slayer.fields().lookupField(field) for field in sfields}

        def source_value(feature, field):
            value = feature.attributes()[s_field_indices[field]]
            try:
                return numeric_value(value, field)
            except ValueError as exc:
                error(feedback, str(exc))
                return None

        # SPATIAL INDEX FOR TARGET LAYER
        feedback.pushInfo("Building spatial index for target layer...")
        t_index = QgsSpatialIndex(tlayer.getFeatures())

        # MAP FOR TARGET FEATURES (to avoid re-fetching)
        t_features = {f.id(): f for f in tlayer.getFeatures()}
        target_ids = [feature.attributes()[t_id_idx] for feature in t_features.values()]
        seen_ids = set()
        duplicate_ids = set()
        for target_id in target_ids:
            if target_id in seen_ids:
                duplicate_ids.add(target_id)
            seen_ids.add(target_id)
        duplicate_ids = sorted(duplicate_ids, key=str)
        if duplicate_ids:
            error(feedback, "Target layer contains duplicate ids: " + ", ".join(map(str, duplicate_ids)))

        # ASSIGN, ACCUMULATE AND WRITE ASSIGNMENT LAYER
        values = {} # key: (target_id, field_name)
        for tfeature in t_features.values():
            t_id = tfeature.attributes()[t_id_idx]
            for field in sfields:
                values[(t_id, field)] = 0.0

        assignment_features = []
        total_s = slayer.featureCount()
        for cnt, sfeature in enumerate(slayer.getFeatures(), start=1):
            if feedback.isCanceled():
                return {}

            s_geom = sfeature.geometry()
            if hasattr(s_geom, 'isMultipart') and s_geom.isMultipart():
                error(feedback, f"Source feature {sfeature.id()} has multipart geometry")
            sxy = s_geom.asPoint()

            # Use spatial index to find the nearest neighbor
            nearest_ids = t_index.nearestNeighbor(sxy, 1)
            if not nearest_ids or nearest_ids[0] not in t_features:
                set_progress(feedback, 0, 50, cnt, total_s)
                continue

            cfeature = t_features[nearest_ids[0]]
            c_id = cfeature.attributes()[t_id_idx]
            s_id = sfeature.attributes()[s_id_idx]

            f = QgsFeature(fields)
            spoint = QgsPoint(sxy)
            cpoint = QgsPoint(cfeature.geometry().asPoint())
            f.setGeometry(QgsLineString([spoint, cpoint]))

            attr = [s_id, c_id]
            for field in sfields:
                s_val = source_value(sfeature, field)
                if s_val is None:
                    return {}
                attr.append(s_val)
                values[(c_id, field)] += s_val

            f.setAttributes(attr)
            assignment_features.append(f)

            if len(assignment_features) >= 200:
                assignment_sink.addFeatures(assignment_features)
                assignment_features = []

            # SHOW PROGRESS
            if cnt % 100 == 0 or cnt == total_s:
                set_progress(feedback, 0, 50, cnt, total_s)

        if assignment_features:
            assignment_sink.addFeatures(assignment_features)

        # WRITE NODE LAYER
        node_features = []
        total_t = tlayer.featureCount()
        for cnt, tfeature in enumerate(t_features.values(), start=1):
            if feedback.isCanceled():
                return {}

            t_id = tfeature.attributes()[t_id_idx]
            attr = list(tfeature.attributes())
            if len(attr) < len(node_fields):
                attr.extend([None] * (len(node_fields) - len(attr)))
            for field in sfields:
                index = node_fields.lookupField(field)
                if index >= 0:
                    attr[index] = values[(t_id, field)]

            f = QgsFeature(node_fields)
            f.setGeometry(tfeature.geometry())
            f.setAttributes(attr)
            node_features.append(f)

            if len(node_features) >= 200:
                node_sink.addFeatures(node_features)
                node_features = []

            # SHOW PROGRESS
            if cnt % 100 == 0 or cnt == total_t:
                set_progress(feedback, 50, 100, cnt, total_t)

        if node_features:
            node_sink.addFeatures(node_features)

        # SHOW PROGRESS
        info(feedback, "Source features", total_s)
        info(feedback, "Target features", total_t)
        nncnt = sum(1 for value in values.values() if abs(value) > 0)
        info(feedback, "Non-zero assignments", nncnt)
        finish(feedback)

        # OUTPUT
        return {self.OUTPUT_ASSIGNMENTS: assignment_id, self.OUTPUT_NODES: node_id}
