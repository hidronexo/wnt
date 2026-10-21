"""Category adapters at the boundary of the generic WNT XML model."""

from qgis.core import QgsFeature, QgsGeometry, QgsProcessingException, QgsWkbTypes
from .base import set_output_layer_name
from .category_sinks import NODE_TYPES, LINK_TYPES
from ..utils.utils_epanet_model import LAYER_SCHEMAS, NODE_SECTIONS
from ..utils import utils_core as tools


PROPERTY_ALIASES = {
    'base_demand': 'demand', 'demand_pattern': 'pattern', 'total_head': 'head',
    'head_pattern': 'pattern', 'initial_level': 'init_level',
    'head_curve': 'pump_head', 'valve_setting': 'setting',
}


def to_network(sources):
    from .wnt_network_to_epanet import _value
    network = tools.WntNetwork()
    crs = next(iter(sources.values())).sourceCrs()
    for category, source in sources.items():
        if source.sourceCrs() != crs:
            raise ValueError('Layers have different CRS')
        for feature in source.getFeatures():
            identifier = str(_value(feature, 'id', ''))
            if not identifier:
                raise ValueError('Missing element identifier')
            if category in NODE_SECTIONS:
                element = tools.WntNode(identifier)
                kind = next(kind for kind, section in NODE_TYPES.items() if section == category)
                element.set_elevation(_value(feature, 'total_head' if category == 'RESERVOIRS' else 'elevation', 0))
            else:
                element = tools.WntLink(identifier, str(_value(feature, 'start', '')), str(_value(feature, 'end', '')))
                kind = 'PUMP' if category == 'PUMPS' else str(_value(feature, 'valve_type', 'PRV')) if category == 'VALVES' else 'PIPE'
                if category == 'PIPES' and str(_value(feature, 'status', '')).upper() == 'CV':
                    kind = 'CVPIPE'
                if _value(feature, 'length') is not None:
                    element.set_length(_value(feature, 'length'))
            element.set_type(kind)
            element.from_wkt(feature.geometry().asWkt())
            for field, _field_type in LAYER_SCHEMAS[category]:
                if field in ('id', 'start', 'end', 'inp_source', 'epanet_version'):
                    continue
                value = _value(feature, field)
                if value is not None:
                    element.epanet[PROPERTY_ALIASES.get(field, field)] = value
            known = {field for field, _kind in LAYER_SCHEMAS[category]}
            for field in feature.fields().names():
                if field not in known and field != 'type':
                    value = _value(feature, field)
                    if value is not None:
                        element.get_properties('custom')[field] = value
            (network.add_node if category in NODE_SECTIONS else network.add_link)(element)
    node_ids = {node.name() for node in network.nodes()}
    for link in network.links():
        if link.start() not in node_ids or link.end() not in node_ids:
            raise ValueError('Link references undefined nodes: ' + link.name())
    return network, crs


def import_network(algorithm, network, parameters, context, feedback, first=True):
    from .wnt_network_from_epanet import _fields, _attributes, _node_values, _link_values
    from .wnt_network_from_xml import output_crs, add_memory_layer
    crs = output_crs(network)
    features = {category: [] for category in LAYER_SCHEMAS}
    for point, elements in ((True, network.nodes()), (False, network.links())):
        for element in elements:
            if feedback.isCanceled():
                return {}
            category = (NODE_TYPES if point else LINK_TYPES).get(element.get_type())
            if category is None:
                raise QgsProcessingException('Unsupported EPANET type: ' + element.get_type())
            values = (_node_values if point else _link_values)(element, {}, '', '2.2')
            for field, _kind in LAYER_SCHEMAS[category]:
                if field in element.epanet:
                    values[field] = element.epanet[field]
            if element.get_type() == 'CVPIPE':
                values['status'] = 'CV'
            feature = QgsFeature(_fields(LAYER_SCHEMAS[category]))
            feature.setGeometry(QgsGeometry.fromWkt(element.to_wkt()))
            feature.setAttributes(_attributes(LAYER_SCHEMAS[category], values))
            features[category].append(feature)
    result = {}
    for category in LAYER_SCHEMAS:
        fields = _fields(LAYER_SCHEMAS[category])
        name = str(network.xml_network_id) + '_' + category.lower()
        if not first:
            add_memory_layer(name, 'Point' if category in NODE_SECTIONS else 'LineString', fields, crs, features[category], context)
            continue
        key = 'OUTPUT_' + category
        destination = dict(parameters)
        destination.setdefault(key, 'TEMPORARY_OUTPUT')
        geometry = QgsWkbTypes.Point if category in NODE_SECTIONS else QgsWkbTypes.LineString
        sink, result[key] = algorithm.parameterAsSink(destination, key, context, fields, geometry, crs)
        set_output_layer_name(context, result[key], name)
        for feature in features[category]:
            if not sink.addFeature(feature):
                raise QgsProcessingException('Could not write ' + category)
    return result
