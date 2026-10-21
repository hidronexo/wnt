"""Validate basic network topology."""

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (QgsProcessing,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource,
                       QgsWkbTypes
                       )
from .base import (OUTPUT_MODE_NEW, OUTPUT_MODE_UPDATE, OUTPUT_MODE_OPTIONS,
                   WntProcessingAlgorithm, feature_copy,
                   field_index, qfield, update_multiple_layer_fields_and_attributes)
from ..utils import utils_graph as graph
from .messages import error, finish, info, message, start

class ValidateAlgorithm(WntProcessingAlgorithm):
    """
    Validate a network.
    """

    # DEFINE CONSTANTS
    INPUT_NODES = 'INPUT_NODES'
    INPUT_LINES = 'INPUT_LINES'
    OUTPUT_MODE = 'OUTPUT_MODE'
    OUTPUT_NODES = 'OUTPUT_NODES'
    OUTPUT_LINES = 'OUTPUT_LINES'


    def createInstance(self):
        """
        Create a instance and return a new copy of algorithm.
        """
        return ValidateAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        return 'validate'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Validate')

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
        return self.tr('''<p>Analyses the network graph and reports topology problems.</p>
<ul>
<li>Orphan nodes.</li>
<li>Duplicate nodes.</li>
<li>Links with undefined endpoints.</li>
<li>Duplicate links.</li>
<li>Loops, where start and end node are the same.</li>
<li>Can create new output layers or update the input node and link layers.</li>
</ul>
<p>Detected problems are written to the <code>problems</code> field.</p>
        ''')

    def initAlgorithm(self, config=None):
        """
        Define the inputs and outputs of the algorithm.
        """

        # ADD THE INPUT
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_NODES,
                self.tr('Input nodes layer'),
                [QgsProcessing.TypeVectorPoint]
                )
            )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_LINES,
                self.tr('Input links layer'),
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
                self.tr('Audited node layer'),
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LINES,
                self.tr('Audited Link layer'),
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
            linklay = self.parameterAsVectorLayer(parameters, self.INPUT_LINES, context)
        else:
            nodelay = self.parameterAsSource(parameters, self.INPUT_NODES, context)
            linklay = self.parameterAsSource(parameters, self.INPUT_LINES, context)

        node_features = list(nodelay.getFeatures())
        link_features = list(linklay.getFeatures())

        # LOAD NODES
        node_ids = []
        for ncnt, feature in enumerate(node_features, start=1):
            node_ids.append(feature['id'])
            if ncnt % 100 == 0:
                feedback.setProgress(25 * ncnt / nodelay.featureCount())

        # LOAD LINKS
        links = []
        for lcnt, feature in enumerate(link_features, start=1):
            links.append((feature['id'], feature['start'], feature['end']))
            if lcnt % 100 == 0:
                feedback.setProgress(25 + 25 * lcnt / linklay.featureCount())

        # VALIDATE
        problems = graph.validate_records(node_ids, links)
        start(feedback, self.displayName())

        node_problem_messages = {}
        for ncnt, feature in enumerate(node_features, start=1):
            msg = ''
            if feature['id'] in problems['orphan nodes']:
                msg = 'Orphan.'
            if feature['id'] in problems['duplicate nodes']:
                msg += ' ' if msg else ''
                msg += 'Duplicated.'
            node_problem_messages[feature.id()] = msg
            if ncnt % 100 == 0:
                feedback.setProgress(50 + 25 * ncnt / nodelay.featureCount())

        link_problem_messages = {}
        for lcnt, feature in enumerate(link_features, start=1):
            msg = ''
            if feature['id'] in problems['undefined node links']:
                msg = 'Undefined node links.'
            if feature['id'] in problems['duplicate links']:
                msg += ' ' if msg else ''
                msg += 'Duplicate link.'
            if feature['id'] in problems['loops']:
                msg += ' ' if msg else ''
                msg += 'Loop.'
            link_problem_messages[feature.id()] = msg
            if lcnt % 100 == 0:
                feedback.setProgress(75 + 25 * lcnt / linklay.featureCount())

        problems_field = qfield('problems', QMetaType.QString)
        if output_mode == OUTPUT_MODE_UPDATE:
            def node_updates_factory(fields):
                node_idx = field_index(fields, 'problems')
                return {fid: {node_idx: msg} for fid, msg in node_problem_messages.items()}

            def link_updates_factory(fields):
                link_idx = field_index(fields, 'problems')
                return {fid: {link_idx: msg} for fid, msg in link_problem_messages.items()}

            try:
                update_multiple_layer_fields_and_attributes([
                    {
                        'layer': nodelay,
                        'field_defs': [problems_field],
                        'updates_factory': node_updates_factory,
                    },
                    {
                        'layer': linklay,
                        'field_defs': [problems_field],
                        'updates_factory': link_updates_factory,
                    },
                ])
            except RuntimeError as exc:
                error(feedback, str(exc))
            node_id = getattr(nodelay, 'id', lambda: self.INPUT_NODES)()
            link_id = getattr(linklay, 'id', lambda: self.INPUT_LINES)()
        else:
            node_fields = nodelay.fields()
            if field_index(node_fields, 'problems') < 0:
                node_fields.append(problems_field)
            (node_sink, node_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT_NODES,
                context,
                node_fields,
                QgsWkbTypes.Point,
                nodelay.sourceCrs()
                )
            link_fields = linklay.fields()
            if field_index(link_fields, 'problems') < 0:
                link_fields.append(qfield('problems', QMetaType.QString))
            (link_sink, link_id) = self.parameterAsSink(
                parameters,
                self.OUTPUT_LINES,
                context,
                link_fields,
                QgsWkbTypes.LineString,
                linklay.sourceCrs()
                )
            for feature in node_features:
                node_sink.addFeature(feature_copy(
                    feature,
                    node_fields,
                    updates={'problems': node_problem_messages[feature.id()]},
                ))
            for feature in link_features:
                link_sink.addFeature(feature_copy(
                    feature,
                    link_fields,
                    updates={'problems': link_problem_messages[feature.id()]},
                ))

        # SHOW INFO
        info(feedback, "Input nodes", len(node_features))
        info(feedback, "Input links", len(link_features))
        pcnt = 0
        for k, v in problems.items():
            pcnt += len(v)
            info(feedback, k.title(), len(v))

        if pcnt:
            msg = '{} problems detected. Check the network.'.format(pcnt)
        else:
            msg = "Network is valid."
        message(feedback, msg)
        info(feedback, "Output mode", OUTPUT_MODE_OPTIONS[output_mode])
        finish(feedback)

        # PROCESS CANCELED
        if feedback.isCanceled():
            return {}

        # OUTPUT
        return {self.OUTPUT_NODES: node_id, self.OUTPUT_LINES: link_id}
