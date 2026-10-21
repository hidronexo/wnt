"""Calculate node degrees for a network graph."""

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (QgsProcessing,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsWkbTypes
                       )
from .base import (OUTPUT_MODE_NEW, OUTPUT_MODE_UPDATE, OUTPUT_MODE_OPTIONS,
                   WntProcessingAlgorithm, add_missing_fields, feature_copy,
                   field_index, qfield, update_layer_attributes)
from ..utils import utils_graph as graph
from .messages import finish, info, start, error

class NodeDegreesAlgorithm(WntProcessingAlgorithm):
    """
    Build an epanet model file from node and link layers.
    """

    # DEFINE CONSTANTS
    INPUT_NODES = 'INPUT_NODES'
    INPUT_LINES = 'INPUT_LINES'
    OUTPUT_MODE = 'OUTPUT_MODE'
    OUTPUT_NODES = 'OUTPUT_NODES'


    def createInstance(self):
        """
        Create a instance and return a new copy of algorithm.
        """
        return NodeDegreesAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        return 'node_degrees'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Node degrees')

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
        return self.tr('''<p>Calculates the graph degree of each network node.</p>
<ul>
<li>The degree is the number of links connected to a node.</li>
<li>Orphan nodes have degree <code>0</code>.</li>
<li>Leaf nodes have degree <code>1</code>.</li>
<li>Continuity nodes have degree <code>2</code>.</li>
<li>Can create a new output layer or update the input node layer.</li>
</ul>
<p>Results are written to the <code>degree</code> field.</p>
        ''')

    def initAlgorithm(self, config=None):
        """
        Define the inputs and outputs of the algorithm.
        """

        # ADD THE INPUT NETWORK (NODES AND LINKS)
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_NODES,
                self.tr('Network node layer input'),
                [QgsProcessing.TypeVectorPoint]
                )
            )
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

        # ADD NODE AND LINK FEATURE SINK
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_NODES,
                self.tr('Node degree layer'),
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
            nodelay = self.parameterAsVectorLayer(parameters, self.INPUT_NODES, context)
        else:
            nodelay = self.parameterAsSource(parameters, self.INPUT_NODES, context)
        linklay = self.parameterAsSource(parameters, self.INPUT_LINES, context)

        # LOAD LAYERS
        node_features = list(nodelay.getFeatures())
        link_features = list(linklay.getFeatures())
        nofn = len(node_features)
        nofl = len(link_features)

        # ADD NODES
        node_ids = []
        for cnt, feature in enumerate(node_features, start=1):
            node_ids.append(feature['id'])
            if cnt % 100 == 0:
                feedback.setProgress(33 * cnt / nofn)

        # ADD LINKS
        links = []
        for cnt, feature in enumerate(link_features, start=1):
            links.append((feature['id'], feature['start'], feature['end']))
            if cnt % 100 == 0:
                feedback.setProgress(33 + 33 * cnt / nofl)

        # CALCULATE DEGREES
        degrees = graph.node_degrees_from_records(node_ids, links)

        field_def = qfield('degree', QMetaType.Int)
        if output_mode == OUTPUT_MODE_UPDATE:
            try:
                fields = add_missing_fields(nodelay, [field_def])
            except RuntimeError as exc:
                error(feedback, str(exc))
            degree_idx = field_index(fields, 'degree')
            updates = {}
            for cnt, feature in enumerate(node_features, start=1):
                updates[feature.id()] = {degree_idx: degrees[feature['id']]}
                if cnt % 100 == 0:
                    feedback.setProgress(67 + 33 * cnt / nofn)
            try:
                update_layer_attributes(nodelay, updates)
            except RuntimeError as exc:
                error(feedback, str(exc))
            node_id = getattr(nodelay, 'id', lambda: self.INPUT_NODES)()
        else:
            newfields = nodelay.fields()
            if field_index(newfields, 'degree') < 0:
                newfields.append(field_def)
            (node_sink, node_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT_NODES,
                context,
                newfields,
                QgsWkbTypes.Point,
                nodelay.sourceCrs()
                )
            for cnt, feature in enumerate(node_features, start=1):
                node_sink.addFeature(feature_copy(
                    feature,
                    newfields,
                    updates={'degree': degrees[feature['id']]},
                ))
                if cnt % 100 == 0:
                    feedback.setProgress(67 + 33 * cnt / nofn)

        # SHOW INFO
        start(feedback, self.displayName())
        info(feedback, "Input nodes", nofn)
        info(feedback, "Input links", nofl)
        info(feedback, "Output nodes", nofn)
        if degrees:
            info(feedback, "Minimum degree", min(degrees.values()))
            info(feedback, "Maximum degree", max(degrees.values()))
        info(feedback, "Output mode", OUTPUT_MODE_OPTIONS[output_mode])
        finish(feedback)

        # PROCESS CANCELED
        if feedback.isCanceled():
            return {}

        # OUTPUT
        return {self.OUTPUT_NODES: node_id}
