"""Export an EPANET demand scenario file."""

import io
import math
from ..utils.export_files import publish_files

from qgis.core import (QgsProcessing,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterField,
                       QgsProcessingParameterFileDestination)
from .base import WntProcessingAlgorithm, missing_fields, field_names
from .messages import error, finish, info, start

class DemandToEpanetScenarioAlgorithm(WntProcessingAlgorithm):
    """
    Build an EPANET scenary file from nodal demands.
    """

    # DEFINE CONSTANTS
    INPUT_JUNCTIONS = 'INPUT_JUNCTIONS'
    INPUT_NODES = INPUT_JUNCTIONS
    FIELD_DEMAND = 'FIELD_DEMAND'
    OUTPUT = 'OUTPUT'


    def createInstance(self):
        """
        Create a instance and return a new copy of algorithm.
        """
        return DemandToEpanetScenarioAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        return 'network_to_epanet_demand_scenario'

    def displayName(self):
        """
        Returns a localised short helper string for the algorithm.
        """
        return self.tr('Demand to epanet scenario file (.scn)')

    def group(self):
        """
         Returns the name of the group this algorithm belongs to.
        """
        return self.tr('Export')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to.
        """
        return 'export'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm.
        """
        return self.tr('''<p>Creates an EPANET demand scenario file.</p>
<ul>
<li>Each demand category must be stored in a field of the node layer.</li>
<li>EPANET patterns must use the same names as the selected demand fields.</li>
</ul>
<p>Import the generated file in EPANET using <b>File &gt; Import &gt; Scenario</b>.</p>
        ''')

    def initAlgorithm(self, config=None):
        """
        Define the inputs and outputs of the algorithm.
        """

        # ADD THE INPUT SOURCES
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_NODES,
                self.tr('Junctions layer'),
                [QgsProcessing.TypeVectorPoint]
                )
            )
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD_DEMAND,
                self.tr('Field containing demand'),
                'demand',
                self.INPUT_NODES,
                allowMultiple=True,
                optional=False
                )
            )
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT,
                self.tr('EPANET scenario file'),
                fileFilter='*.scn'
                )
            )

    def processAlgorithm(self, parameters, context, feedback):
        """
        RUN PROCESS
        """

        # INPUT
        nodes = self.parameterAsSource(parameters, self.INPUT_NODES, context)
        defields = self.parameterAsFields(parameters, self.FIELD_DEMAND, context)

        # IF NO FIELD WAS SELECTED RETURN {}
        if not defields:
            error(feedback, "Field containing demand is required")
        missing = missing_fields(nodes, ['id', *defields])
        if missing:
            error(feedback, "Node layer is missing required fields: " + ", ".join(missing))

        # WRITE FILE
        cnt = 0
        scnfn = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        try:
            with io.StringIO() as file:
                file.write('; File generated automatically by Water Network Tools \n')
                file.write('[DEMANDS] \n')
                file.write(';Node    Demand    Pattern \n')
                feedback.setProgress(5) # Update the progress bar

                for f in nodes.getFeatures():
                    for field in defields:
                        value = f[field]
                        node_type = str(f['type'] or '').upper() if 'type' in field_names(nodes) else 'JUNCTION'
                        if value not in (None, '') and node_type == 'JUNCTION':
                            if not math.isfinite(float(value)):
                                error(feedback, 'Demand must be finite: ' + str(f['id']))
                            cnt += 1
                            line = '{}  {}  {} \n'.format(f['id'], value, field)
                            file.write(line)
                if feedback.isCanceled():
                    return {}
                publish_files({scnfn: file.getvalue().encode('latin-1')})
        except UnicodeEncodeError as exc:
            error(feedback, "Output contains characters that cannot be written: " + str(exc))

        # SHOW INFO
        start(feedback, self.displayName())
        info(feedback, "Node demands", cnt)
        info(feedback, "Demand categories", len(defields))
        info(feedback, "Output file", scnfn)
        finish(feedback)

        # PROCESS CANCELED
        if feedback.isCanceled():
            return {}

        # OUTPUT
        return {self.OUTPUT: scnfn}
