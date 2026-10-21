"""Classify network links into branched and meshed areas."""

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (QgsProcessing,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsWkbTypes
                       )
from .base import (OUTPUT_MODE_NEW, OUTPUT_MODE_UPDATE, OUTPUT_MODE_OPTIONS,
                   WntProcessingAlgorithm, feature_copy,
                   field_index, missing_fields, qfield, update_layer_fields_and_attributes)
from ..utils import utils_graph as gr
from .messages import error, finish, info, start

class ClassifyAlgorithm(WntProcessingAlgorithm):
    """
    Build an epanet model file from node and link layers.
    """

    # DEFINE CONSTANTS
    INPUT_LINES = 'INPUT_LINES'
    OUTPUT_MODE = 'OUTPUT_MODE'
    OUTPUT_LINES = 'OUTPUT_LINES'



    def createInstance(self):
        """
        Create a instance and return a new copy of algorithm.
        """
        return ClassifyAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        return 'classify'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Classify')

    def group(self):
        """
         Returns the name of the group this algorithm belongs to.
        """
        return self.tr('Graph')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to.
        """
        return 'graph'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm.
        """
        return self.tr('''<p>Classifies network links into branched and meshed areas.</p>
<ul>
<li>Adds or updates <code>topology</code>: <code>branched</code> or <code>mesh</code>.</li>
<li>Adds or updates <code>zone</code>: subnetwork identifier.</li>
<li>Can create a new output layer or update the input link layer.</li>
</ul>
<p>Use this algorithm to support network sectorization.</p>
        ''')

    def initAlgorithm(self, config=None):
        """
        Define the inputs and outputs of the algorithm.
        """

        # ADD THE INPUT NETWORK LINKS
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_LINES,
                self.tr('Network links layer input'),
                [QgsProcessing.TypeVectorLine]
                )
            )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.OUTPUT_MODE,
                self.tr('Output mode'),
                options=[self.tr(option) for option in OUTPUT_MODE_OPTIONS],
                defaultValue=OUTPUT_MODE_NEW,
                optional=False
                )
            )

        # ADD LINK FEATURE SINK
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LINES,
                self.tr('Subnetwork link layer'),
                optional=True
                )
            )

        from .typed_graph import configure
        configure(self)

    def processAlgorithm(self, parameters, context, feedback):
        from .typed_graph import requested, process
        if requested(parameters):
            return process(self, parameters, context, feedback)
        """
        RUN PROCESS
        """
        # INPUT
        output_mode = self.parameterAsEnum(parameters, self.OUTPUT_MODE, context)
        if output_mode == OUTPUT_MODE_UPDATE:
            links = self.parameterAsVectorLayer(parameters, self.INPUT_LINES, context)
        else:
            links = self.parameterAsSource(parameters, self.INPUT_LINES, context)

        missing = missing_fields(links, ['id', 'start', 'end'])
        if missing:
            error(feedback, "Input link layer is missing required fields: " + ", ".join(missing))

        # CREATE NETWORK
        netg = gr.Graph()
        link_features = list(links.getFeatures())
        nofl = len(link_features)
        seen_ids = set()
        for cnt, feature in enumerate(link_features, start=1):
            link_id = feature['id']
            if link_id in seen_ids:
                error(feedback, "Duplicate link id: " + str(link_id))
            seen_ids.add(link_id)
            netg.add_edge(link_id, feature['start'], feature['end'])
            if cnt % 100 == 0:
                feedback.setProgress(25 * cnt / nofl)

        # GENERATE SUBNETWORKS
        classified = gr.unique_zone_classification(netg.classify())

        field_defs = [qfield('topology', QMetaType.QString), qfield('zone', QMetaType.Int)]
        if output_mode == OUTPUT_MODE_UPDATE:
            def updates_factory(fields):
                topology_idx = field_index(fields, 'topology')
                zone_idx = field_index(fields, 'zone')
                updates = {}
                cnt = 0
                for feature in link_features:
                    cnt += 1
                    topology, zone = classified[feature['id']]
                    updates[feature.id()] = {topology_idx: topology_value(topology), zone_idx: zone}
                    if cnt % 100 == 0:
                        feedback.setProgress(75 + 25 * cnt / nofl)
                return updates
            try:
                update_layer_fields_and_attributes(
                    links,
                    field_defs,
                    updates_factory,
                    delete_field_names=['zones'],
                )
            except RuntimeError as exc:
                error(feedback, str(exc))
            link_id = getattr(links, 'id', lambda: self.INPUT_LINES)()
        else:
            newfields = links.fields()
            zones_idx = field_index(newfields, 'zones')
            if zones_idx >= 0:
                try:
                    newfields.remove(zones_idx)
                except (TypeError, ValueError):
                    del newfields[zones_idx]
            for field in field_defs:
                if field_index(newfields, field.name()) < 0:
                    newfields.append(field)
            (link_sink, link_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT_LINES,
                context,
                newfields,
                QgsWkbTypes.LineString,
                crs=links.sourceCrs()
                )
            cnt = 0
            for feature in link_features:
                cnt += 1
                topology, zone = classified[feature['id']]
                link_sink.addFeature(feature_copy(
                    feature,
                    newfields,
                    updates={'topology': topology_value(topology), 'zone': zone},
                ))
                if cnt % 100 == 0:
                    feedback.setProgress(75 + 25 * cnt / nofl)

        # SHOW INFO
        start(feedback, self.displayName())
        info(feedback, "Input links", nofl)
        info(feedback, "Classified links", nofl)
        info(feedback, "Output mode", OUTPUT_MODE_OPTIONS[output_mode])
        finish(feedback)

        # PROCESS CANCELED
        if feedback.isCanceled():
            return {}

        # OUTPUT
        return {self.OUTPUT_LINES: link_id}


def topology_value(value):
    """Return public topology labels for graph classifications."""
    return {
        "BRANCHED": "branched",
        "MESHED": "mesh",
    }.get(value, str(value).lower())
