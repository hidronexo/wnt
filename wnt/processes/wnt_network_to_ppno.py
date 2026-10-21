"""Export PPNO sizing input from network layers."""

from pathlib import Path

from qgis.core import (QgsProcessing,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterField,
                       QgsProcessingParameterFile,
                       QgsProcessingParameterFileDestination)
from .base import WntProcessingAlgorithm, missing_fields
from ..utils import utils_parser as parser
from .messages import error, finish, info, start, warning

class NetworkToPpnoAlgorithm(WntProcessingAlgorithm):
    """
    Build a ppno data file (.ext) from node and link data.
    """

    # DEFINE CONSTANTS
    INPUT_JUNCTIONS = 'INPUT_JUNCTIONS'
    INPUT_NODES = INPUT_JUNCTIONS
    FIELD_PRESSURE = 'FIELD_PRESSURE'
    INPUT_PIPES = 'INPUT_PIPES'
    INPUT_LINES = INPUT_PIPES
    FIELD_SERIES = 'FIELD_SERIES'
    INPUT_ALGORITHMS = 'INPUT_ALGORITHMS'
    INPUT_EPANET = 'INPUT_EPANET'
    INPUT_CATALOG = 'INPUT_CATALOG'
    INPUT_TEMPLATE = INPUT_CATALOG
    OUTPUT = 'OUTPUT'
    ALGORITHMS = ('DE', 'DA', 'NSGA2', 'MOEAD', 'MACO', 'PSO')


    def createInstance(self):
        """
        Create a instance and return a new copy of algorithm.
        """
        return NetworkToPpnoAlgorithm()

    @staticmethod
    def _catalog_has_section_header(catalog_bytes):
        text = catalog_bytes.decode('latin-1')
        for line in text.splitlines():
            clean_line = line.partition(';')[0].strip()
            if clean_line.startswith('[') and clean_line.endswith(']'):
                return True
        return False
    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        return 'network_to_ppno'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Network to pressure pipe optimization data file (.ext)')

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
        return self.tr('''<p>Creates a PPNO <code>.ext</code> data file for pipe sizing.</p>
<ul>
<li>The required pressure must be stored in a node layer field.</li>
<li>The pipe group must be stored in a link layer field.</li>
<li>The EPANET <code>.inp</code> file must contain the model to optimize.</li>
<li>The pipe catalog is selected directly as an external <code>.cat</code> file.</li>
<li>PPNO runs EPANET simulations, applies minimum pressure constraints, and optionally runs global optimization algorithms.</li>
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
                self.tr('Junctions layer'),
                [QgsProcessing.TypeVectorPoint]
                )
            )
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD_PRESSURE,
                self.tr('Required pressure field'),
                'Required pressure',
                self.INPUT_NODES,
                allowMultiple=False,
                optional=False
                )
            )
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_LINES,
                self.tr('Pipes layer'),
                [QgsProcessing.TypeVectorLine]
                )
            )
        self.addParameter(
            QgsProcessingParameterField(
                self.FIELD_SERIES,
                self.tr('Pipe group field'),
                'Pipe group',
                self.INPUT_LINES,
                allowMultiple=False,
                optional=False
                )
            )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.INPUT_ALGORITHMS,
                self.tr('Algorithms'),
                options=list(self.ALGORITHMS),
                allowMultiple=True,
                optional=True
                )
            )
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_EPANET,
                self.tr('EPANET file'),
                extension='inp'
                )
            )
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT_CATALOG,
                self.tr('PPNO pipe catalog file'),
                extension='cat'
                )
            )

        # ADD A FILE DESTINATION FOR RESULTS
        self.addParameter(
            QgsProcessingParameterFileDestination(
                self.OUTPUT,
                self.tr('Output ppno file'),
                fileFilter='*.ext'
                )
            )
    def processAlgorithm(self, parameters, context, feedback):
        """
        RUN PROCESS
        """

        # INPUT
        nodes = self.parameterAsSource(parameters, self.INPUT_NODES, context)
        pfield = self.parameterAsFields(parameters, self.FIELD_PRESSURE, context)
        pfield = pfield[0]
        links = self.parameterAsSource(parameters, self.INPUT_LINES, context)
        sfield = self.parameterAsFields(parameters, self.FIELD_SERIES, context)
        sfield = sfield[0]
        selected_algorithm_indexes = self.parameterAsEnums(parameters, self.INPUT_ALGORITHMS, context) or []
        selected_algorithms = [self.ALGORITHMS[index] for index in selected_algorithm_indexes]
        epanet_file = self.parameterAsFile(parameters, self.INPUT_EPANET, context)
        catalog_input_file = self.parameterAsFile(parameters, self.INPUT_CATALOG, context)

        # OUTPUT
        extfile = self.parameterAsFileOutput(
            parameters,
            self.OUTPUT,
            context
            )

        # CHECK CRS
        if nodes.sourceCrs() != links.sourceCrs():
            error(feedback, "Layers have different CRS")
        missing = missing_fields(nodes, ['id', pfield]) + missing_fields(links, ['id', sfield])
        if missing:
            error(feedback, "Missing required fields: " + ", ".join(missing))

        # PIPE CATALOG SECTION
        catalog_source = Path(catalog_input_file)
        if not catalog_source.exists():
            error(feedback, 'PPNO pipe catalog file not found: ' + catalog_input_file)

        catalog_bytes = catalog_source.read_bytes()
        if self._catalog_has_section_header(catalog_bytes):
            error(feedback, 'PPNO pipe catalog must not contain section headers')

        catalog_file = Path(extfile).with_suffix('.cat')
        if catalog_file.exists():
            warning(feedback, f"Existing pipe catalog will be overwritten: {catalog_file}")
        from ..utils.export_files import catalog_groups, publish_files, ModelReferences, pressure_value
        groups = catalog_groups(catalog_bytes, 4, encoding='latin-1')
        references = ModelReferences(epanet_file)

        # BUILD EXT FILE
        ppnof = parser.SectionedText()
        ppnof.sections['TITLE'] = ['; File generated automatically by Water Network Tools']
        ppnof.sections['INP'] = [epanet_file]
        ppnof.sections['OPTIONS'] = []
        if selected_algorithms:
            ppnof.sections['OPTIONS'].append(parser.format_tokens(('Algorithm', *selected_algorithms)))
        ppnof.sections['PIPE_CATALOG'] = [catalog_file.name]
        ppnof.sections['PRESSURES'] = []
        ppnof.sections['PIPES'] = []

        # PRESSURES SECTION
        ncnt = 0
        for feature in nodes.getFeatures():
            if feature[pfield] is not None and feature[pfield] != '':
                references.require('JUNCTIONS', feature['id'])
                pressure_value(feature[pfield])
                ncnt += 1
                line = feature['id']+' '*4 + str(feature[pfield])
                ppnof.sections['PRESSURES'].append(line)

        # PIPES SECTION
        pcnt = 0
        for feature in links.getFeatures():
            if feature[sfield]:
                if str(feature[sfield]) not in groups:
                    error(feedback, 'Pipes reference unknown catalog groups: ' + str(feature[sfield]))
                references.require('PIPES', feature['id'])
                pcnt += 1
                line = (feature['id']+' '*4 + str(feature[sfield]))
                ppnof.sections['PIPES'].append(line)

        # WRITE EXT FILE
        try:
            text = ''.join('[' + name + ']\n' + '\n'.join(lines) + '\n\n'
                           for name, lines in ppnof.sections.items()) + '[END]\n'
            if feedback.isCanceled():
                return {}
            publish_files({extfile: text.encode('latin-1'), catalog_file: catalog_bytes},
                          inputs=(epanet_file, catalog_input_file))
        except UnicodeEncodeError as exc:
            error(feedback, "Output contains characters that cannot be written with PPNO latin-1 encoding: " + str(exc))

        # SHOW INFO
        start(feedback, self.displayName())
        info(feedback, "Nodes with minimum pressure", ncnt)
        info(feedback, "Pipes to size", pcnt)
        info(feedback, "Pipe catalog file", catalog_file)
        info(feedback, "Output file", extfile)
        finish(feedback)
        # PROCESS CANCELED
        if feedback.isCanceled():
            return {}

        # OUTPUT
        return {self.OUTPUT: extfile}
