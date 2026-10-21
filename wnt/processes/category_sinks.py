"""Route generated model features into category-specific Processing outputs."""

from qgis.core import QgsFeature, QgsFields, QgsProcessingException, QgsProcessingParameterFeatureSink
from .base import field_index, qfield


NODE_TYPES = {'JUNCTION': 'JUNCTIONS', 'RESERVOIR': 'RESERVOIRS', 'TANK': 'TANKS'}
LINK_TYPES = {'PIPE': 'PIPES', 'CVPIPE': 'PIPES', 'PUMP': 'PUMPS',
              'PRV': 'VALVES', 'PSV': 'VALVES', 'PBV': 'VALVES',
              'FCV': 'VALVES', 'TCV': 'VALVES', 'GPV': 'VALVES', 'VALVE': 'VALVES'}


def add_outputs(algorithm, categories):
    for category in categories:
        algorithm.addParameter(QgsProcessingParameterFeatureSink('OUTPUT_' + category, category, optional=True))


class CategorySink:
    """Preserve common fields and expose check-valve state as status=CV."""

    def __init__(self, sinks, fields, point):
        self.sinks = sinks
        self.fields = fields
        self.point = point

    def addFeature(self, feature, *_args):
        index = field_index(self.fields, 'type')
        attributes = list(feature.attributes())
        kind = str(attributes[index]).upper() if index >= 0 else ('JUNCTION' if self.point else 'PIPE')
        category = (NODE_TYPES if self.point else LINK_TYPES).get(kind)
        if category not in self.sinks:
            raise QgsProcessingException('Unsupported model element type: ' + kind)
        sink, target_fields = self.sinks[category]
        result = QgsFeature(target_fields)
        result.setGeometry(feature.geometry())
        attributes.extend([None] * (len(target_fields) - len(attributes)))
        if kind == 'CVPIPE':
            status_index = field_index(target_fields, 'status')
            if attributes[status_index] not in (None, '', 'CV'):
                raise QgsProcessingException('Conflicting check-valve type and status')
            attributes[index] = 'PIPE'
            attributes[status_index] = 'CV'
        elif category == 'PIPES' and attributes[field_index(target_fields, 'status')] in (None, ''):
            attributes[field_index(target_fields, 'status')] = 'OPEN'
        elif category == 'VALVES':
            attributes[field_index(target_fields, 'valve_type')] = kind
        result.setAttributes(attributes)
        return sink.addFeature(result)

    def addFeatures(self, features, *_args):
        return all(self.addFeature(feature) for feature in features)


def create_sinks(algorithm, parameters, context, fields, geometry, crs, point, categories, factory):
    sinks = {}
    outputs = {}
    for category in categories:
        target_fields = QgsFields(fields)
        if category == 'PIPES' and field_index(target_fields, 'status') < 0:
            target_fields.append(qfield('status'))
        if category == 'VALVES' and field_index(target_fields, 'valve_type') < 0:
            target_fields.append(qfield('valve_type'))
        key = 'OUTPUT_' + category
        destinations = dict(parameters)
        destinations.setdefault(key, 'TEMPORARY_OUTPUT')
        sink, outputs[key] = factory(destinations, key, context, target_fields, geometry, crs)
        sinks[category] = sink, target_fields
    return CategorySink(sinks, fields, point), outputs
