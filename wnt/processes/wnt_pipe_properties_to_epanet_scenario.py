"""Export an EPANET pipe properties scenario file."""

import io
import math
from ..utils.export_files import publish_files

from qgis.core import (QgsProcessing,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterField,
                       QgsProcessingParameterFileDestination)
from .base import WntProcessingAlgorithm, missing_fields, field_names
from .messages import error, finish, info, start

class PipePropertiesToEpanetScenarioAlgorithm(WntProcessingAlgorithm):
    """
    Build an EPANET scenary file from pipe diameter and roughness.
    """

    # DEFINE CONSTANTS

    INPUT_PIPES = 'INPUT_PIPES'
    INPUT_LINES = INPUT_PIPES
    FIELD_DIAMETER = 'FIELD_DIAMETER'
    FIELD_ROUGHNESS = 'FIELD_ROUGHNESS'
    OUTPUT = 'OUTPUT'


    def createInstance(self):
        """
        Create a instance and return a new copy of algorithm.
        """
        return PipePropertiesToEpanetScenarioAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        # Keep the historical ID so saved Processing models remain compatible.
        return 'network_to_epanet_pipe_propierties_scenario'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Pipe properties to EPANET scenario file (.scn)')

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
        return self.tr('''<p>Creates an EPANET <code>.scn</code> scenario file with pipe diameters and roughness values.</p>
<ul>
<li>Diameters are read from the selected mandatory diameter field.</li>
<li>Roughness values are read from the selected mandatory roughness field.</li>
</ul>
<p>Import the generated file in EPANET using <b>File &gt; Import &gt; Scenario</b>.</p>
        ''')

    def initAlgorithm(self, config=None):
        """
        Define the inputs and outputs of the algorithm.
        """

        # ADD THE INPUT
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_LINES,
                self.tr('Pipes layer'),
                [QgsProcessing.TypeVectorLine]
                )
            )
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD_DIAMETER,
                self.tr('Diameter field'),
                'diameter',
                self.INPUT_LINES
                )
            )
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD_ROUGHNESS,
                self.tr('Roughness field'),
                'roughness',
                self.INPUT_LINES
                )
            )

        # ADD A FILE DESTINATION
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
        links = self.parameterAsSource(parameters, self.INPUT_LINES, context)
        dfield = self.parameterAsString(parameters, self.FIELD_DIAMETER, context)
        rfield = self.parameterAsString(parameters, self.FIELD_ROUGHNESS, context)

        missing = missing_fields(links, ['id', dfield, rfield])
        if missing:
            error(feedback, "Link layer is missing required fields: " + ", ".join(missing))

        # OUTPUT
        scnfile = self.parameterAsFileOutput(parameters, self.OUTPUT, context)

        # WRITE FILE
        cnt = 0
        pipe_features = [
            feature for feature in links.getFeatures()
            if 'type' not in field_names(links) or str(feature['type'] or '').upper() in ['PIPE', 'CVPIPE']
        ]
        for feature in pipe_features:
            for field in (dfield, rfield):
                if not math.isfinite(float(feature[field])) or float(feature[field]) <= 0:
                    error(feedback, 'Pipe diameter and roughness must be finite and positive: ' + str(feature['id']))
        try:
            with io.StringIO() as file:
                file.write('; File generated automatically by Water Network Tools \n')
                file.write('[DIAMETERS] \n')
                file.write(';Pipe    Diameter \n')

                for feature in pipe_features:
                    cnt += 1
                    file.write('{}    {} \n'.format(feature['id'], feature[dfield]))

                file.write(' \n')
                file.write('[ROUGHNESS] \n')
                file.write(';Pipe    Roughness \n')

                for feature in pipe_features:
                    file.write('{}    {} \n'.format(feature['id'], feature[rfield]))
                if feedback.isCanceled():
                    return {}
                publish_files({scnfile: file.getvalue().encode('latin-1')})
        except UnicodeEncodeError as exc:
            error(feedback, "Output contains characters that cannot be written: " + str(exc))

        # SHOW INFO
        start(feedback, self.displayName())
        info(feedback, "Pipes written", cnt)
        info(feedback, "Output file", scnfile)
        finish(feedback)

        # PROCESS CANCELED
        if feedback.isCanceled():
            return {}

        # OUTPUT
        return {self.OUTPUT: scnfile}
