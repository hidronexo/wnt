"""Explicit compatibility adapter for saved two-layer EPANET workflows."""

import json
from qgis.core import QgsFields
from .base import qfield
from .category_sinks import NODE_TYPES, LINK_TYPES
from ..utils.utils_epanet_model import LAYER_SCHEMAS


ALIASES = {'base_demand': 'demand', 'demand_pattern': 'pattern', 'total_head': 'head',
           'head_pattern': 'pattern', 'initial_level': 'init_level', 'head_curve': 'pump_head',
           'valve_type': 'type', 'valve_setting': 'setting', 'status': 'initial_status'}


class LegacyFeature:
    def __init__(self, feature, values):
        self.feature = feature
        self.values = values

    def __getitem__(self, key):
        return self.values[key]

    def geometry(self):
        return self.feature.geometry()


class LegacySource:
    def __init__(self, source, category, features):
        self.source = source
        self.category = category
        self.features = features

    def sourceCrs(self):
        return self.source.sourceCrs()

    def getFeatures(self):
        return iter(self.features)

    def fields(self):
        fields = QgsFields()
        for name, _kind in LAYER_SCHEMAS[self.category]:
            fields.append(qfield(name))
        fields.append(qfield('type'))
        return fields


class DefaultSource:
    """Fill absent (not explicitly null) columns from the existing typed model."""

    def __init__(self, source, defaults):
        self.source = source
        self.defaults = defaults

    def fields(self):
        return self.source.fields()

    def sourceCrs(self):
        return self.source.sourceCrs()

    def getFeatures(self):
        from .base import field_names
        names = field_names(self.source)
        for feature in self.source.getFeatures():
            values = dict(self.defaults.get(str(feature['id']), {}))
            for name in names:
                try:
                    values[name] = feature[name]
                except KeyError:
                    pass
            yield LegacyFeature(feature, values)


def existing_defaults(sources, path, sections):
    from ..utils.utils_core import WntNetwork
    from .wnt_network_from_epanet import _node_values, _link_values, _supplemental_properties
    model = WntNetwork()
    model.from_epanet(path)
    node_extra, link_extra = _supplemental_properties(sections)
    defaults = {}
    for point, elements in ((True, model.nodes()), (False, model.links())):
        for element in elements:
            category = (NODE_TYPES if point else LINK_TYPES).get(element.get_type())
            values = (_node_values if point else _link_values)(element, node_extra if point else link_extra, '', '2.2')
            defaults.setdefault(category, {})[element.name()] = values
    return {category: DefaultSource(source, defaults.get(category, {})) for category, source in sources.items()}


def split_legacy(source, point):
    if source is None:
        return {}
    from .base import field_names
    names = field_names(source)
    groups = {}
    for feature in source.getFeatures():
        values = {name: feature[name] for name in names}
        kind = str(values.get('type') or ('JUNCTION' if point else 'PIPE')).upper()
        category = (NODE_TYPES if point else LINK_TYPES).get(kind)
        if category is None:
            raise ValueError('Unsupported legacy EPANET type: ' + kind)
        raw = values.get('epanet')
        if raw and not (hasattr(raw, 'isNull') and raw.isNull()):
            properties = raw if isinstance(raw, dict) else json.loads(str(raw))
            if not isinstance(properties, dict):
                raise ValueError('Legacy EPANET properties must be an object')
            values = {**properties, **{key: value for key, value in values.items() if key != 'epanet'}}
        for current, old in ALIASES.items():
            if current not in values and old in values:
                values[current] = values[old]
        if category == 'RESERVOIRS' and 'total_head' not in values:
            values['total_head'] = values.get('elevation', 0)
        groups.setdefault(category, []).append(LegacyFeature(feature, values))
    return {category: LegacySource(source, category, features) for category, features in groups.items()}
