"""Import hydraulic results from EPANET toolkit runs."""

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (QgsFeature,
                       QgsField,
                       QgsFields,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFile)
from qgis.core import QgsProcessingParameterDefinition
from .base import WntProcessingAlgorithm
from .messages import error, finish, info, message, start
from ..utils.utils_epanet_api import (
    EpanetConfigurationError,
    EpanetError,
    EpanetToolkit,
)
from ..utils.utils_epanet_model import PHYSICAL_SECTIONS, NODE_SECTIONS, read_sections
from ..utils.utils_parser import parse_tokens


class ResultsFromEpanetAlgorithm(WntProcessingAlgorithm):
    """
    Import EPANET result from EPANET toolkit.
    """

    # DEFINE CONSTANTS
    INPUT = 'INPUT'
    RESULT_TYPE = 'RESULT_TYPE'
    OUTPUT_NODES = 'OUTPUT_NODES'
    OUTPUT_LINES = 'OUTPUT_LINES'
    OUTPUT_NODE_QUALITY = 'OUTPUT_NODE_QUALITY'
    OUTPUT_LINK_QUALITY = 'OUTPUT_LINK_QUALITY'
    RESULT_HYDRAULIC = 0
    RESULT_QUALITY = 1
    RESULT_BOTH = 2
    RESULT_OPTIONS = (
        'Hydraulic results',
        'Quality results',
        'Hydraulic and quality results',
    )

    def createInstance(self):
        """
        createInstance must return a new copy of algorithm.
        """
        return ResultsFromEpanetAlgorithm()

    def name(self):
        """
        Returns the unique algorithm name, used for identifying the algorithm.
        """
        return 'results_from_epanet'

    def displayName(self):
        """
        Returns the translated algorithm name.
        """
        return self.tr('Results from EPANET')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to.
        """
        return self.tr('Import')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to.
        """
        return 'import'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm.
        """
        return self.tr('''<p>Imports hydraulic and quality results from an EPANET simulation.</p>
<ul>
<li>Node results: <code>time</code>, <code>demand</code>, <code>head</code>, <code>pressure</code>.</li>
<li>Link results: <code>time</code>, <code>flow</code>, <code>velocity</code>, <code>headloss</code>, <code>status</code>, <code>setting</code>, <code>energy</code>.</li>
<li>Quality results: <code>time</code>, <code>id</code>, <code>quality</code>.</li>
</ul>
<p>Configure the EPANET toolkit library before running this algorithm.</p>
        ''')

    def initAlgorithm(self, config=None):
        """
         Define the inputs and outputs of the algorithm.
        """

        # ADD INPUT FILE
        self.addParameter(
            QgsProcessingParameterFile(
                self.INPUT,
                self.tr('EPANET file'),
                extension='inp'
            )
        )
        self.addParameter(
            QgsProcessingParameterEnum(
                self.RESULT_TYPE,
                self.tr('Result type'),
                options=[self.tr(option) for option in self.RESULT_OPTIONS],
                defaultValue=self.RESULT_HYDRAULIC,
                optional=False
            )
        )

        # ADD NODE AND LINK SINKS
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_NODES,
                self.tr('Node results')
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LINES,
                self.tr('Link results'),
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_NODE_QUALITY,
                self.tr('Node quality results'),
                optional=True
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_LINK_QUALITY,
                self.tr('Link quality results'),
                optional=True
            )
        )
        for name in (self.OUTPUT_NODES, self.OUTPUT_LINES, self.OUTPUT_NODE_QUALITY, self.OUTPUT_LINK_QUALITY):
            definition = self.parameterDefinition(name)
            definition.setFlags(definition.flags() | QgsProcessingParameterDefinition.FlagHidden | QgsProcessingParameterDefinition.FlagOptional)
        for section in PHYSICAL_SECTIONS:
            for quality in (False, True):
                suffix = '_QUALITY' if quality else ''
                parameter = QgsProcessingParameterFeatureSink(
                    'OUTPUT_' + section + suffix,
                    section + ' — ' + self.tr('Quality results' if quality else 'Hydraulic results'), optional=True)
                parameter.setMetadata({'wnt_enabled_when': [('RESULT_TYPE', (1, 2) if quality else (0, 2))]})
                self.addParameter(parameter)

    def processAlgorithm(self, parameters, context, feedback):
        """
        RUN PROCESS
        """

        legacy_outputs = (self.OUTPUT_NODES, self.OUTPUT_LINES, self.OUTPUT_NODE_QUALITY, self.OUTPUT_LINK_QUALITY)
        if self.parameterDefinition('OUTPUT_JUNCTIONS') is not None and not any(name in parameters for name in legacy_outputs):
            return self._process_categories(parameters, context, feedback)

        # INPUT
        epanet_file = self.parameterAsFile(parameters, self.INPUT, context)
        result_type = self.parameterAsEnum(parameters, self.RESULT_TYPE, context)
        include_hydraulic = result_type in (self.RESULT_HYDRAULIC, self.RESULT_BOTH)
        include_quality = result_type in (self.RESULT_QUALITY, self.RESULT_BOTH)

        start(feedback, self.displayName())

        # LOAD EPANET TOOLKIT
        try:
            toolkit = EpanetToolkit.from_config()
            toolkit_info = toolkit.info()
            max_label_len = toolkit.constants.max_label_len
        except EpanetConfigurationError as exc:
            error(feedback, str(exc))
        except EpanetError as exc:
            error(feedback, exc.message)

        node_sink = link_sink = None
        nodes_id = links_id = None
        if include_hydraulic:
            node_sink, nodes_id = self.parameterAsSink(
                parameters, self.OUTPUT_NODES, context,
                self._hydraulic_node_fields(max_label_len)
            )
            link_sink, links_id = self.parameterAsSink(
                parameters, self.OUTPUT_LINES, context,
                self._hydraulic_link_fields(max_label_len)
            )

        node_quality_sink = link_quality_sink = None
        node_quality_id = link_quality_id = None
        if include_quality:
            quality_fields = self._quality_fields(max_label_len)
            node_quality_sink, node_quality_id = self.parameterAsSink(
                parameters, self.OUTPUT_NODE_QUALITY, context, quality_fields
            )
            link_quality_sink, link_quality_id = self.parameterAsSink(
                parameters, self.OUTPUT_LINK_QUALITY, context, quality_fields
            )

        # SHOW TOOLKIT INFORMATION
        info(feedback, "EPANET toolkit library", toolkit_info.library_path)
        info(feedback, "Platform", f"{toolkit_info.platform} {toolkit_info.architecture}")
        info(feedback, "EPANET toolkit version", toolkit_info.version)
        info(feedback, "EPANET toolkit API", toolkit_info.api)
        info(feedback, "Input file", epanet_file)

        result_map = {}
        if include_hydraulic:
            try:
                results = toolkit.read_hydraulic_results(epanet_file)
            except EpanetError as exc:
                error(feedback, exc.message)

            for node_result in results.node_rows:
                f = QgsFeature()
                f.setAttributes(node_result)
                node_sink.addFeature(f)

            for link_result in results.link_rows:
                f = QgsFeature()
                f.setAttributes(link_result)
                link_sink.addFeature(f)
            result_map[self.OUTPUT_NODES] = nodes_id
            result_map[self.OUTPUT_LINES] = links_id
            info(feedback, "Hydraulic time steps", results.step_count)
            info(feedback, "Nodes", results.node_count)
            info(feedback, "Links", results.link_count)

        if include_quality:
            try:
                quality_results = toolkit.read_quality_results(epanet_file)
            except EpanetConfigurationError as exc:
                error(feedback, str(exc))
            except EpanetError as exc:
                error(feedback, exc.message)

            for node_result in quality_results.node_rows:
                f = QgsFeature()
                f.setAttributes(node_result)
                node_quality_sink.addFeature(f)

            for link_result in quality_results.link_rows:
                f = QgsFeature()
                f.setAttributes(link_result)
                link_quality_sink.addFeature(f)
            result_map[self.OUTPUT_NODE_QUALITY] = node_quality_id
            result_map[self.OUTPUT_LINK_QUALITY] = link_quality_id
            info(feedback, "Quality time steps", quality_results.step_count)
            info(feedback, "Quality nodes", quality_results.node_count)
            info(feedback, "Quality links", quality_results.link_count)

        # SHOW NODES AND LINKS PROCESSED
        message(feedback, "Results loaded successfully")
        info(feedback, "Result type", self.RESULT_OPTIONS[result_type])
        finish(feedback)

        # PROCESS CANCELED
        if feedback.isCanceled():
            return {}

        # OUTPUT
        return result_map

    def _process_categories(self, parameters, context, feedback):
        path = self.parameterAsFile(parameters, self.INPUT, context)
        selection = self.parameterAsEnum(parameters, self.RESULT_TYPE, context)
        sections = read_sections(path)
        lookup = {}
        for section in PHYSICAL_SECTIONS:
            for row in sections.get(section, []):
                tokens = parse_tokens(row)
                if tokens:
                    lookup[(section in NODE_SECTIONS, tokens[0])] = section
        try:
            toolkit = EpanetToolkit.from_config()
            size = toolkit.constants.max_label_len
            result = {}
            for quality in (False, True):
                if selection != self.RESULT_BOTH and quality != (selection == self.RESULT_QUALITY):
                    continue
                if feedback.isCanceled():
                    return {}
                rows = toolkit.read_quality_results(path) if quality else toolkit.read_hydraulic_results(path)
                sinks = {}
                for section in PHYSICAL_SECTIONS:
                    fields = self._quality_fields(size) if quality else (
                        self._hydraulic_node_fields(size) if section in NODE_SECTIONS else self._hydraulic_link_fields(size))
                    name = 'OUTPUT_' + section + ('_QUALITY' if quality else '')
                    destination_parameters = dict(parameters)
                    destination_parameters.setdefault(name, 'TEMPORARY_OUTPUT')
                    sinks[section], result[name] = self.parameterAsSink(destination_parameters, name, context, fields)
                for point, records in ((True, rows.node_rows), (False, rows.link_rows)):
                    for row in records:
                        if feedback.isCanceled():
                            return {}
                        section = lookup.get((point, str(row[1])))
                        if section is None:
                            error(feedback, 'Result ID is missing from the model: ' + str(row[1]))
                        feature = QgsFeature()
                        feature.setAttributes(row)
                        if not sinks[section].addFeature(feature):
                            error(feedback, 'Could not write result: ' + str(row[1]))
            return result
        except (EpanetConfigurationError, EpanetError, OSError, ValueError) as exc:
            error(feedback, str(exc))

    @staticmethod
    def _hydraulic_node_fields(max_label_len):
        fields = QgsFields()
        fields.append(QgsField("time", QMetaType.QString))
        fields.append(QgsField("id", QMetaType.QString, len=max_label_len))
        fields.append(QgsField("demand", QMetaType.Double))
        fields.append(QgsField("head", QMetaType.Double))
        fields.append(QgsField("pressure", QMetaType.Double))
        return fields

    @staticmethod
    def _hydraulic_link_fields(max_label_len):
        fields = QgsFields()
        fields.append(QgsField("time", QMetaType.QString))
        fields.append(QgsField("id", QMetaType.QString, len=max_label_len))
        fields.append(QgsField("flow", QMetaType.Double))
        fields.append(QgsField("velocity", QMetaType.Double))
        fields.append(QgsField("headloss", QMetaType.Double))
        fields.append(QgsField("status", QMetaType.QString, len=6))
        fields.append(QgsField("setting", QMetaType.Double))
        fields.append(QgsField("energy", QMetaType.Double))
        return fields

    @staticmethod
    def _quality_fields(max_label_len):
        fields = QgsFields()
        fields.append(QgsField("time", QMetaType.QString))
        fields.append(QgsField("id", QMetaType.QString, len=max_label_len))
        fields.append(QgsField("quality", QMetaType.Double))
        return fields
