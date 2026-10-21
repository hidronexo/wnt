"""Merge categorized networks without merging unlike hydraulic node types."""

from qgis.core import (QgsCoordinateTransform, QgsFields, QgsProcessing,
                       QgsProcessingException, QgsProcessingParameterDefinition,
                       QgsProcessingParameterFeatureSource, QgsWkbTypes)
from .base import missing_fields, require_projected_crs
from .category_sinks import add_outputs
from ..utils.utils_epanet_model import PHYSICAL_SECTIONS, NODE_SECTIONS, LINK_SECTIONS
from ..utils.utils_graph import validate_records


def configure(algorithm):
    for key in ('INPUT_NODES_1', 'INPUT_NODES_2', 'INPUT_LINES_1', 'INPUT_LINES_2', 'OUTPUT_NODES', 'OUTPUT_LINES'):
        parameter = algorithm.parameterDefinition(key)
        parameter.setFlags(parameter.flags() | QgsProcessingParameterDefinition.FlagHidden | QgsProcessingParameterDefinition.FlagOptional)
    for network in (1, 2):
        for category in PHYSICAL_SECTIONS:
            geometry = QgsProcessing.TypeVectorPoint if category in NODE_SECTIONS else QgsProcessing.TypeVectorLine
            algorithm.addParameter(QgsProcessingParameterFeatureSource(
                f'INPUT_{category}_{network}', f'{category} ({network})', [geometry], optional=True))
    add_outputs(algorithm, PHYSICAL_SECTIONS)


def requested(parameters):
    return any(f'INPUT_{category}_{network}' in parameters for network in (1, 2) for category in PHYSICAL_SECTIONS)


def process(algorithm, parameters, context, feedback):
    from .wnt_merge_networks import transformed_feature, aligned_feature, point_distance, snapped_line_geometry
    crs = algorithm.parameterAsCrs(parameters, algorithm.CRS, context)
    require_projected_crs(crs, feedback)
    tolerance = algorithm.parameterAsDouble(parameters, algorithm.TOLERANCE, context)
    if tolerance < 0:
        raise QgsProcessingException('Tolerance must be nonnegative')
    fields = {category: QgsFields() for category in PHYSICAL_SECTIONS}
    networks = []
    for network in (1, 2):
        features = {}
        for category in PHYSICAL_SECTIONS:
            key = f'INPUT_{category}_{network}'
            if key not in parameters or not parameters[key]:
                continue
            source = algorithm.parameterAsSource(parameters, key, context)
            if source is None:
                raise QgsProcessingException('Invalid source: ' + key)
            required = ['id'] if category in NODE_SECTIONS else ['id', 'start', 'end']
            if missing_fields(source, required):
                raise QgsProcessingException('Missing identifiers: ' + key)
            for field in source.fields():
                index = fields[category].lookupField(field.name())
                if index < 0:
                    fields[category].append(field)
                elif fields[category][index].type() != field.type():
                    raise QgsProcessingException('Incompatible field types: ' + category + '/' + field.name())
            transform = None if source.sourceCrs() == crs else QgsCoordinateTransform(source.sourceCrs(), crs, context.transformContext())
            features[category] = [transformed_feature(feature, transform) for feature in source.getFeatures()]
        nodes = [str(f['id']) for category in NODE_SECTIONS for f in features.get(category, [])]
        links = [(str(f['id']), str(f['start']), str(f['end'])) for category in LINK_SECTIONS for f in features.get(category, [])]
        problems = validate_records(nodes, links)
        if any(problems[key] for key in ('duplicate nodes', 'duplicate links', 'undefined node links', 'loops')):
            raise QgsProcessingException('Invalid network ' + str(network) + ': ' + str(problems))
        if not features:
            raise QgsProcessingException('Select layers for network ' + str(network))
        networks.append(features)
    merged = {category: [] for category in PHYSICAL_SECTIONS}
    used_nodes, used_links = set(), set()

    def unused(identifier, used):
        candidate = identifier
        suffix = 2
        while candidate in used:
            ending = '_' + str(suffix)
            candidate = identifier[:31 - len(ending)] + ending
            suffix += 1
        used.add(candidate)
        return candidate

    for number, network in enumerate(networks):
        remap, points = {}, {}
        for category in NODE_SECTIONS:
            for feature in network.get(category, []):
                identifier = str(feature['id'])
                target = None
                # Only identical hydraulic attributes may be coalesced; storage
                # and supply elements are never coalesced by proximity alone.
                if number and category == 'JUNCTIONS':
                    candidate_feature = aligned_feature(feature, fields[category])
                    compared = [field.name() for field in fields[category]
                                if field.name() not in ('id', 'inp_source', 'epanet_version')]
                    for existing in merged[category]:
                        if (point_distance(feature.geometry().asPoint(), existing.geometry().asPoint()) <= tolerance
                                and all(candidate_feature[key] == existing[key] for key in compared)):
                            target = existing
                            break
                if target is None:
                    target = aligned_feature(feature, fields[category], {'id': unused(identifier, used_nodes)})
                    merged[category].append(target)
                remap[identifier] = str(target['id'])
                points[identifier] = target.geometry().asPoint()
        for category in LINK_SECTIONS:
            for feature in network.get(category, []):
                start, end = str(feature['start']), str(feature['end'])
                if remap[start] == remap[end]:
                    raise QgsProcessingException('Merge would collapse a link: ' + str(feature['id']))
                updates = {'id': unused(str(feature['id']), used_links), 'start': remap[start], 'end': remap[end]}
                geometry = snapped_line_geometry(feature.geometry(), points[start], points[end])
                merged[category].append(aligned_feature(feature, fields[category], updates, geometry))
    result = {}
    for category in PHYSICAL_SECTIONS:
        if not fields[category]:
            continue
        key = 'OUTPUT_' + category
        destinations = dict(parameters)
        destinations.setdefault(key, 'TEMPORARY_OUTPUT')
        geometry = QgsWkbTypes.Point if category in NODE_SECTIONS else QgsWkbTypes.LineString
        sink, result[key] = algorithm.parameterAsSink(destinations, key, context, fields[category], geometry, crs)
        for feature in merged[category]:
            if feedback.isCanceled():
                return {}
            if not sink.addFeature(feature):
                raise QgsProcessingException('Could not write ' + category)
    return result
