"""Export network topology to Trivial Graph Format."""

from qgis.core import (QgsProcessing,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFileDestination
                       )
from .base import WntProcessingAlgorithm, missing_fields
from ..utils import utils_graph as graph
from .messages import error, finish, info, start


class NetworkToGraphAlgorithm(WntProcessingAlgorithm):
    """
    Set the node elevation from a DEM in raster format.
    """

    # DEFINE CONSTANTS
    INPUT_NODES = 'INPUT_NODES'
    INPUT_LINES = 'INPUT_LINES'
    OUTPUT = 'OUTPUT'


    def createInstance(self):
        """
        Create a instance and return a new copy of algorithm.
        """
        return NetworkToGraphAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        return 'network_to_graph'

    def displayName(self):
        """
        Returns the translated algorithm name.
        """
        return self.tr('Network to graph file')

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
        Returns a localised short help string for the algorithm.
        """
        return self.tr('''<p>Exports the network topology to a Trivial Graph Format file.</p>
<ul>
<li>Input node and link layers must contain valid network identifiers.</li>
<li>The output <code>.tgf</code> file can be opened in graph tools such as yEd.</li>
</ul>
        ''')

    def initAlgorithm(self, config=None):
        """
        Define the inputs and outputs of the algorithm.
        """

        # ADD THE INPUT SOURCES
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_NODES,
                self.tr('Input node vector layer'),
                types=[QgsProcessing.TypeVectorPoint]
                )
            )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_LINES,
                self.tr('Input link vector layer'),
                types=[QgsProcessing.TypeVectorLine]
                )
            )

        #ADD THE OUTPUT SINK
        # ADD A FILE DESTINATION
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT,
                self.tr('Trivial Graph Format file'),
                fileFilter='*.tgf'
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
        if feedback.isCanceled():
            return {}

        # INPUT
        nodes = self.parameterAsSource(parameters, self.INPUT_NODES, context)
        links = self.parameterAsSource(parameters, self.INPUT_LINES, context)

        node_missing = missing_fields(nodes, ['id'])
        if node_missing:
            error(feedback, "Node layer is missing required fields: " + ", ".join(node_missing))
        link_missing = missing_fields(links, ['id', 'start', 'end'])
        if link_missing:
            error(feedback, "Link layer is missing required fields: " + ", ".join(link_missing))

        node_ids = [feature['id'] for feature in nodes.getFeatures()]
        link_records = [
            (feature['id'], feature['start'], feature['end'])
            for feature in links.getFeatures()
        ]
        problems = graph.validate_records(node_ids, link_records)
        for problem_name in ('duplicate nodes', 'undefined node links', 'duplicate links', 'loops'):
            values = sorted(problems[problem_name])
            if values:
                error(feedback, "%s: %s" % (problem_name, ", ".join(str(value) for value in values)))

        # OUTPUT
        graphfile = self.parameterAsFileOutput(parameters, self.OUTPUT, context)

        # GENERATE GRAPH
        graph.graph_from_records(node_ids, link_records, graphfile)

        # SHOW INFO
        start(feedback, self.displayName())
        info(feedback, "Nodes", nodes.featureCount())
        info(feedback, "Edges", links.featureCount())
        info(feedback, "Output file", graphfile)
        finish(feedback)

        # OUTPUT
        return {self.OUTPUT: graphfile}
