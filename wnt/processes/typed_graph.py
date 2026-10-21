"""Six-category adapters for graph algorithms, retaining legacy entry points."""

from qgis.PyQt.QtCore import QMetaType
from qgis.core import (
    QgsFields, QgsProcessing, QgsProcessingException,
    QgsProcessingParameterDefinition, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource, QgsWkbTypes,
)

from .base import field_index, feature_copy, missing_fields, qfield, update_multiple_layer_fields_and_attributes
from ..utils.utils_epanet_model import NODE_SECTIONS, LINK_SECTIONS, PHYSICAL_SECTIONS
from ..utils import utils_graph as graph


def configure(algorithm):
    """Expose typed layers and keep old parameters only for saved callers."""
    for name in ('INPUT_NODES', 'INPUT_LINES', 'OUTPUT_NODES', 'OUTPUT_LINES'):
        parameter = algorithm.parameterDefinition(name)
        if parameter is not None:
            parameter.setFlags(parameter.flags() | QgsProcessingParameterDefinition.FlagHidden | QgsProcessingParameterDefinition.FlagOptional)
    categories = LINK_SECTIONS if algorithm.name() == 'classify' else PHYSICAL_SECTIONS
    for section in categories:
        geometry = QgsProcessing.TypeVectorPoint if section in NODE_SECTIONS else QgsProcessing.TypeVectorLine
        algorithm.addParameter(QgsProcessingParameterFeatureSource('INPUT_' + section, section, [geometry], optional=True))
        if algorithm.name() == 'network_to_graph':
            continue
        if algorithm.name() == 'node_degrees' and section in LINK_SECTIONS:
            continue
        algorithm.addParameter(QgsProcessingParameterFeatureSink('OUTPUT_' + section, section, optional=True))


def requested(parameters):
    return any('INPUT_' + section in parameters for section in PHYSICAL_SECTIONS)


def process(algorithm, parameters, context, feedback):
    """Evaluate the complete graph and return results to their original categories."""
    name = algorithm.name()
    updating = name != 'network_to_graph' and algorithm.parameterAsEnum(parameters, 'OUTPUT_MODE', context) == 1
    categories = LINK_SECTIONS if name == 'classify' else PHYSICAL_SECTIONS
    sources = {}
    features = {}
    for section in categories:
        key = 'INPUT_' + section
        if key not in parameters or parameters[key] is None or parameters[key] == '':
            continue
        source = (algorithm.parameterAsVectorLayer if updating else algorithm.parameterAsSource)(parameters, key, context)
        if source is None:
            raise QgsProcessingException('Invalid source: ' + section)
        missing = missing_fields(source, ['id'] if section in NODE_SECTIONS else ['id', 'start', 'end'])
        if missing:
            raise QgsProcessingException(section + ': missing fields: ' + ', '.join(missing))
        sources[section] = source
        features[section] = list(source.getFeatures())
    if not sources:
        raise QgsProcessingException('Select at least one EPANET model layer')
    node_ids = [str(f['id']) for section in NODE_SECTIONS for f in features.get(section, [])]
    links = [(str(f['id']), str(f['start']), str(f['end'])) for section in LINK_SECTIONS for f in features.get(section, [])]
    if name == 'classify':
        node_ids = list({node for _, start, end in links for node in (start, end)})
    problems = graph.validate_records(node_ids, links)
    if name != 'validate' and any(problems[key] for key in ('duplicate nodes', 'duplicate links', 'undefined node links', 'loops')):
        raise QgsProcessingException(str({key: sorted(value) for key, value in problems.items() if value}))
    if feedback.isCanceled():
        return {}
    if name == 'network_to_graph':
        path = algorithm.parameterAsFileOutput(parameters, algorithm.OUTPUT, context)
        graph.graph_from_records(node_ids, links, path)
        return {algorithm.OUTPUT: path}
    degrees = graph.node_degrees_from_records(node_ids, links)
    classified = {}
    if name == 'classify':
        network = graph.Graph()
        for identifier, start, end in links:
            network.add_edge(identifier, start, end)
        classified = graph.unique_zone_classification(network.classify())

    def updates(section, feature):
        identifier = str(feature['id'])
        if name == 'node_degrees':
            return {'degree': degrees[identifier]}
        if name == 'classify':
            from .wnt_classify import topology_value
            topology, zone = classified[identifier]
            return {'topology': topology_value(topology), 'zone': zone}
        applicable = ('orphan nodes', 'duplicate nodes') if section in NODE_SECTIONS else ('undefined node links', 'duplicate links', 'loops')
        return {'issues': '; '.join(key for key in applicable if identifier in problems[key])}

    field_defs = ([qfield('degree', QMetaType.Int)] if name == 'node_degrees' else
                  [qfield('topology'), qfield('zone', QMetaType.Int)] if name == 'classify' else [qfield('issues')])
    result = {}
    edits = []
    for section, source in sources.items():
        if name == 'node_degrees' and section in LINK_SECTIONS:
            continue
        output = 'OUTPUT_' + section
        if updating:
            def factory(fields, category=section):
                return {f.id(): {field_index(fields, key): value for key, value in updates(category, f).items()}
                        for f in features[category]}
            edits.append({'layer': source, 'field_defs': field_defs, 'updates_factory': factory})
            result[output] = source.id()
        else:
            fields = QgsFields(source.fields())
            for field in field_defs:
                if field_index(fields, field.name()) < 0:
                    fields.append(field)
            destinations = dict(parameters)
            destinations.setdefault(output, 'TEMPORARY_OUTPUT')
            geometry = QgsWkbTypes.Point if section in NODE_SECTIONS else QgsWkbTypes.LineString
            sink, result[output] = algorithm.parameterAsSink(destinations, output, context, fields, geometry, source.sourceCrs())
            for feature in features[section]:
                if feedback.isCanceled():
                    return {}
                if not sink.addFeature(feature_copy(feature, fields, updates(section, feature))):
                    raise QgsProcessingException('Could not write ' + section)
    if edits:
        update_multiple_layer_fields_and_attributes(edits)
    if name == 'validate':
        for issue, identifiers in problems.items():
            if identifiers:
                feedback.pushInfo(issue + ': ' + ', '.join(sorted(identifiers)))
    return result
