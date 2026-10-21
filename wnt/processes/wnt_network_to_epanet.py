"""Export six typed EPANET model layers to an INP file."""

from collections import OrderedDict

from qgis.core import (
    QgsProcessing, QgsProcessingParameterEnum, QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFile, QgsProcessingParameterFileDestination,
    QgsProcessingParameterDefinition, QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterMatrix,
)

from .base import WntProcessingAlgorithm, missing_fields, problem_text
from .widgets import EpanetWorkflowWidgetWrapper
from .messages import crs as log_crs
from .messages import error, finish, info, start
from ..utils import utils_core as tools
from ..utils import utils_graph as graph
from ..utils.utils_epanet_model import (
    PHYSICAL_SECTIONS, read_sections, scratch_sections, write_sections, merge_model_sections,
)
from ..utils.utils_parser import format_tokens, parse_tokens
from ..utils.utils_epanet_options import OPTION_SPECS, REPORT_FIELDS, analysis_sections, report_field_lines
from ..utils.model_validation import validate_model


def _value(feature, name, default=None):
    try:
        value = feature[name]
    except (KeyError, TypeError):
        if name == 'status':
            return _value(feature, 'initial_status', default)
        return default
    if hasattr(value, 'isNull') and value.isNull():
        return default
    return default if value is None or value == "" else value


def _line(*values):
    """Format an EPANET row, omitting optional trailing null values."""
    values = list(values)
    while values and values[-1] in (None, ""):
        values.pop()
    return format_tokens(values)


def _point(feature):
    node = tools.WntNode("geometry")
    node.from_wkt(feature.geometry().asWkt())
    return node.get_geometry()


def _vertices(feature, link_id):
    link = tools.WntLink(str(link_id), "start", "end")
    link.from_wkt(feature.geometry().asWkt())
    geometry = link.get_geometry() or []
    return [_line(link_id, x, y) for x, y in geometry[1:-1]]


class NetworkToEpanetAlgorithm(WntProcessingAlgorithm):
    """Build an EPANET model from six typed model layers."""

    INPUT_JUNCTIONS = "INPUT_JUNCTIONS"
    INPUT_RESERVOIRS = "INPUT_RESERVOIRS"
    INPUT_TANKS = "INPUT_TANKS"
    INPUT_PIPES = "INPUT_PIPES"
    INPUT_PUMPS = "INPUT_PUMPS"
    INPUT_VALVES = "INPUT_VALVES"
    INPUTS = OrderedDict((
        ("JUNCTIONS", INPUT_JUNCTIONS), ("RESERVOIRS", INPUT_RESERVOIRS),
        ("TANKS", INPUT_TANKS), ("PIPES", INPUT_PIPES),
        ("PUMPS", INPUT_PUMPS), ("VALVES", INPUT_VALVES),
    ))
    INPUT_EPANET = "INPUT_EPANET"
    INPUT_TEMPLATE = INPUT_EPANET
    WORKFLOW = "WORKFLOW"
    EPANET_VERSION = "EPANET_VERSION"
    FLOW_UNITS = "FLOW_UNITS"
    HEADLOSS = "HEADLOSS"
    DEMAND_MODEL = "DEMAND_MODEL"
    DEFAULT_PATTERN = "DEFAULT_PATTERN"
    DEMAND_MULTIPLIER = "DEMAND_MULTIPLIER"
    EMITTER_EXPONENT = "EMITTER_EXPONENT"
    VISCOSITY = "VISCOSITY"
    DIFFUSIVITY = "DIFFUSIVITY"
    SPECIFIC_GRAVITY = "SPECIFIC_GRAVITY"
    TRIALS = "TRIALS"
    ACCURACY = "ACCURACY"
    UNBALANCED = "UNBALANCED"
    MINIMUM_PRESSURE = "MINIMUM_PRESSURE"
    REQUIRED_PRESSURE = "REQUIRED_PRESSURE"
    PRESSURE_EXPONENT = "PRESSURE_EXPONENT"
    OUTPUT = "OUTPUT"

    WORKFLOW_EXISTING = 0
    WORKFLOW_SCRATCH = 1
    WORKFLOW_OPTIONS = ("Update an existing EPANET model", "Create EPANET model from scratch")
    EPANET_VERSION_OPTIONS = ("2.0", "2.2")
    FLOW_UNIT_OPTIONS = ("CFS", "GPM", "MGD", "IMGD", "AFD", "LPS", "LPM", "MLD", "CMH", "CMD")
    HEADLOSS_OPTIONS = ("H-W", "D-W", "C-M")
    DEMAND_MODEL_OPTIONS = ("DDA", "PDA")
    UNBALANCED_OPTIONS = ("STOP", "CONTINUE")

    # Stable presentation contract, independent of locale and serialization order.
    OPTION_GROUPS = (
        ('Hydraulics', ('EPANET_VERSION', 'FLOW_UNITS', 'HEADLOSS',
              'DEMAND_MULTIPLIER', 'DEFAULT_PATTERN', 'INPUT_DEFINITIONS',
              'VISCOSITY', 'SPECIFIC_GRAVITY', 'HYDRAULICS_MODE', 'HYDRAULICS_FILE', 'MAP_FILE')),
        ('Emitters', ('EMITTER_EXPONENT',)),
        ('Energy', ('ENERGY_PRICE', 'ENERGY_PATTERN', 'PUMP_EFFICIENCY', 'DEMAND_CHARGE')),
        ('Quality', ('QUALITY_ANALYSIS', 'CHEMICAL_NAME', 'MASS_UNITS', 'DIFFUSIVITY',
                     'TRACE_NODE', 'QUALITY_TOLERANCE')),
        ('Reactions', ('BULK_ORDER', 'WALL_ORDER', 'TANK_ORDER', 'GLOBAL_BULK', 'GLOBAL_WALL',
                     'LIMITING_CONCENTRATION', 'WALL_CORRELATION')),
        ('Calculation stability', ('TRIALS', 'ACCURACY', 'UNBALANCED', 'UNBALANCED_TRIALS',
                                   'CHECK_FREQUENCY', 'MAXIMUM_CHECKS', 'DAMPING_LIMIT')),
        ('EPANET 2.2', ('DEMAND_MODEL', 'MINIMUM_PRESSURE', 'REQUIRED_PRESSURE',
                        'PRESSURE_EXPONENT', 'MAXIMUM_HEAD_ERROR', 'MAXIMUM_FLOW_CHANGE')),
        ('Times', ('DURATION', 'HYDRAULIC_TIMESTEP', 'QUALITY_TIMESTEP', 'RULE_TIMESTEP',
                   'PATTERN_TIMESTEP', 'PATTERN_START', 'REPORT_TIMESTEP', 'REPORT_START',
                   'START_CLOCKTIME', 'STATISTIC')),
        ('Report', ('REPORT_PAGE_SIZE', 'REPORT_FILE', 'REPORT_STATUS', 'REPORT_SUMMARY',
                    'REPORT_ENERGY', 'REPORT_NODES', 'REPORT_NODE_IDS',
                    'REPORT_LINKS', 'REPORT_LINK_IDS', 'REPORT_FIELDS')),
    )

    def createInstance(self):
        return NetworkToEpanetAlgorithm()

    def name(self):
        return "network_to_epanet"

    def displayName(self):
        return self.tr("Export EPANET model to INP file")

    def group(self):
        return self.tr("Export")

    def groupId(self):
        return "export"

    def shortHelpString(self):
        return self.tr(
            "<p>Exports junctions, reservoirs, tanks, pipes, pumps and valves to an "
            "EPANET INP file.</p><p>Output mode: update selected objects in an existing INP "
            "while preserving other objects and global settings. "
            "When creating a model from scratch, EPANET options are editable.</p>"
        ) + self.tr(
            '<p>Expand Advanced parameters to edit Hydraulics, Emitters, Energy, Quality, '
            'Reactions, Calculation stability, EPANET 2.2, Times and Report. '
            'These options apply when creating a new model; updating an existing INP preserves its settings.</p>'
            '<p>Element-specific values come from the six layers: emitter_coefficient in JUNCTIONS; '
            'initial_quality and source fields in node layers; mixing_model and mixing_fraction in TANKS; '
            'energy_price, energy_pattern and efficiency_curve in PUMPS. '
            'The report table accepts EPANET field keywords, YES/NO, precision (0-10), BELOW and ABOVE limits; '
            'blank cells retain the engine defaults. File references are used later by EPANET, not created by this exporter.</p>'
        )

    def initAlgorithm(self, config=None):
        self._scratch_parameters = {}
        for section, parameter in self.INPUTS.items():
            geometry = (
                QgsProcessing.TypeVectorPoint
                if section in ("JUNCTIONS", "RESERVOIRS", "TANKS")
                else QgsProcessing.TypeVectorLine
            )
            self.addParameter(QgsProcessingParameterFeatureSource(
                parameter, self.tr(section.title()), [geometry], optional=True,
            ))
        workflow_parameter = QgsProcessingParameterEnum(
            self.WORKFLOW, self.tr("Output mode"),
            options=[self.tr(value) for value in self.WORKFLOW_OPTIONS], defaultValue=self.WORKFLOW_EXISTING,
        )
        workflow_parameter.setMetadata({
            "widget_wrapper": {"class": EpanetWorkflowWidgetWrapper},
        })
        self.addParameter(workflow_parameter)
        existing_parameter = QgsProcessingParameterFile(
            self.INPUT_EPANET, self.tr("Existing EPANET model file"), extension="inp", optional=True,
        )
        existing_parameter.setMetadata({"epanet_existing_only": True})
        self.addParameter(existing_parameter)
        self._add_scratch_parameter(QgsProcessingParameterEnum(
            self.EPANET_VERSION, self.tr("EPANET version"), options=list(self.EPANET_VERSION_OPTIONS), defaultValue=1,
        ))
        self._add_scratch_parameter(QgsProcessingParameterEnum(
            self.FLOW_UNITS, self.tr("Flow units"), options=list(self.FLOW_UNIT_OPTIONS),
            defaultValue=self.FLOW_UNIT_OPTIONS.index("LPS"),
        ))
        self._add_scratch_parameter(QgsProcessingParameterEnum(
            self.HEADLOSS, self.tr("Headloss formula"), options=list(self.HEADLOSS_OPTIONS), defaultValue=0,
        ))
        self._add_scratch_parameter(QgsProcessingParameterEnum(
            self.DEMAND_MODEL, self.tr("Demand model (EPANET 2.2)"), options=list(self.DEMAND_MODEL_OPTIONS), defaultValue=0,
        ))
        self._add_scratch_parameter(QgsProcessingParameterString(
            self.DEFAULT_PATTERN, self.tr("Default demand pattern"), defaultValue="", optional=True,
        ))
        self._add_scratch_parameter(QgsProcessingParameterFile(
            'INPUT_DEFINITIONS', self.tr('INP pattern and curve definitions'), extension='inp', optional=True,
        ))
        self._number(self.DEMAND_MULTIPLIER, "Demand multiplier", 1.0)
        self._number(self.EMITTER_EXPONENT, "Emitter exponent", 0.5)
        self._number(self.VISCOSITY, "Relative viscosity", 1.0)
        self._number(self.DIFFUSIVITY, "Relative diffusivity", 1.0)
        self._number(self.SPECIFIC_GRAVITY, "Specific gravity", 1.0)
        self._add_scratch_parameter(QgsProcessingParameterNumber(
            self.TRIALS, self.tr("Maximum trials"), type=QgsProcessingParameterNumber.Integer, defaultValue=40, minValue=1,
        ))
        self._number(self.ACCURACY, "Hydraulic accuracy", 0.001, 0.0)
        self._add_scratch_parameter(QgsProcessingParameterEnum(
            self.UNBALANCED, self.tr("If unbalanced"), options=list(self.UNBALANCED_OPTIONS), defaultValue=0,
        ))
        self._number(self.MINIMUM_PRESSURE, "Minimum pressure (EPANET 2.2)", 0.0)
        self._number(self.REQUIRED_PRESSURE, "Required pressure (EPANET 2.2)", 0.1)
        self._number(
            self.PRESSURE_EXPONENT, "Pressure exponent (EPANET 2.2)",
            0.5, 0.0,
        )
        for key, label, kind, default, choices, _section, _directive in OPTION_SPECS:
            if kind == 'enum':
                parameter = QgsProcessingParameterEnum(
                    key, self.tr(label), options=[self.tr(item) for item in choices], defaultValue=default)
            elif kind == 'boolean':
                parameter = QgsProcessingParameterBoolean(key, self.tr(label), defaultValue=default)
            elif kind in ('number', 'integer'):
                arguments = {'defaultValue': default}
                if choices[0] is not None:
                    arguments['minValue'] = choices[0]
                if choices[1] is not None:
                    arguments['maxValue'] = choices[1]
                if kind == 'integer':
                    arguments['type'] = QgsProcessingParameterNumber.Integer
                parameter = QgsProcessingParameterNumber(key, self.tr(label), **arguments)
            else:
                parameter = QgsProcessingParameterString(key, self.tr(label), defaultValue=default, optional=default == '')
            self._add_scratch_parameter(parameter)
        self._add_scratch_parameter(QgsProcessingParameterMatrix(
            'REPORT_FIELDS', self.tr('Report — field visibility, precision and filters'),
            headers=[self.tr('EPANET field'), self.tr('Show (YES/NO)'), self.tr('Decimal places'),
                     self.tr('Below'), self.tr('Above')],
            defaultValue=[cell for field in REPORT_FIELDS for cell in (field, '', '', '', '')],
            optional=True,
        ))
        family_labels = {
            'Hydraulics': self.tr('Hydraulics'),
            'Emitters': self.tr('Emitters'),
            'Quality': self.tr('Quality'),
            'Reactions': self.tr('Reactions'),
            'EPANET 2.2': self.tr('EPANET 2.2'),
            'Calculation stability': self.tr('Calculation stability'),
        }
        for family, names in self.OPTION_GROUPS:
            for name in names:
                parameter = self._scratch_parameters.pop(name)
                if family in family_labels:
                    label = parameter.description().split(' — ', 1)[-1]
                    parameter.setDescription(family_labels[family] + ' — ' + label)
                self.addParameter(parameter)
        if self._scratch_parameters:
            raise ValueError('EPANET parameters missing from presentation groups')
        self.addParameter(QgsProcessingParameterFileDestination(
            self.OUTPUT, self.tr("EPANET model file"), fileFilter="*.inp",
        ))

    def _add_scratch_parameter(self, parameter):
        parameter.setMetadata({"epanet_scratch_only": True})
        parameter.setFlags(parameter.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self._scratch_parameters[parameter.name()] = parameter

    def _number(self, name, label, default, minimum=None):
        kwargs = {"defaultValue": default}
        if minimum is not None:
            kwargs["minValue"] = minimum
        self._add_scratch_parameter(
            QgsProcessingParameterNumber(name, self.tr(label), **kwargs),
        )

    def checkParameterValues(self, parameters, context):
        workflow = self.parameterAsEnum(parameters, self.WORKFLOW, context)
        if workflow == self.WORKFLOW_EXISTING and not self.parameterAsFile(parameters, self.INPUT_EPANET, context):
            return False, self.tr("Existing EPANET model file is required for this output mode")
        if not any(self.parameterAsSource(parameters, value, context) for value in self.INPUTS.values()):
            return False, self.tr("Select at least one EPANET model layer")
        return super().checkParameterValues(parameters, context)

    def _options(self, parameters, context):
        return {
            "version": self.EPANET_VERSION_OPTIONS[self.parameterAsEnum(parameters, self.EPANET_VERSION, context)],
            "flow_units": self.FLOW_UNIT_OPTIONS[self.parameterAsEnum(parameters, self.FLOW_UNITS, context)],
            "headloss": self.HEADLOSS_OPTIONS[self.parameterAsEnum(parameters, self.HEADLOSS, context)],
            "demand_model": self.DEMAND_MODEL_OPTIONS[self.parameterAsEnum(parameters, self.DEMAND_MODEL, context)],
            "default_pattern": self.parameterAsString(parameters, self.DEFAULT_PATTERN, context),
            "demand_multiplier": self.parameterAsDouble(parameters, self.DEMAND_MULTIPLIER, context),
            "emitter_exponent": self.parameterAsDouble(parameters, self.EMITTER_EXPONENT, context),
            "viscosity": self.parameterAsDouble(parameters, self.VISCOSITY, context),
            "diffusivity": self.parameterAsDouble(parameters, self.DIFFUSIVITY, context),
            "specific_gravity": self.parameterAsDouble(parameters, self.SPECIFIC_GRAVITY, context),
            "trials": self.parameterAsInt(parameters, self.TRIALS, context),
            "accuracy": self.parameterAsDouble(parameters, self.ACCURACY, context),
            "unbalanced": self.UNBALANCED_OPTIONS[self.parameterAsEnum(parameters, self.UNBALANCED, context)],
            "unbalanced_trials": self.parameterAsInt(parameters, 'UNBALANCED_TRIALS', context) if 'UNBALANCED_TRIALS' in parameters else 0,
            "minimum_pressure": self.parameterAsDouble(parameters, self.MINIMUM_PRESSURE, context),
            "required_pressure": self.parameterAsDouble(parameters, self.REQUIRED_PRESSURE, context),
            "pressure_exponent": self.parameterAsDouble(parameters, self.PRESSURE_EXPONENT, context),
        }

    def processAlgorithm(self, parameters, context, feedback):
        sources = {section: self.parameterAsSource(parameters, name, context) for section, name in self.INPUTS.items()}
        sources = {section: source for section, source in sources.items() if source is not None}
        from .legacy_layers import split_legacy
        for legacy, canonical, point in (('INPUT_NODES', 'JUNCTIONS', True), ('INPUT_LINES', 'PIPES', False)):
            if legacy in parameters:
                split = split_legacy(sources.pop(canonical, None), point)
                if any(category in sources for category in split):
                    error(feedback, 'Conflicting legacy and typed EPANET layers')
                sources.update(split)
        if not sources:
            error(feedback, "Select at least one EPANET model layer")

        crs_values = [source.sourceCrs() for source in sources.values()]
        crs = crs_values[0]
        if any(value != crs for value in crs_values[1:]):
            error(feedback, "Layers have different CRS")
        start(feedback, self.displayName())
        log_crs(feedback, crs)
        for section, source in sources.items():
            required = {
                'JUNCTIONS': ('id', 'elevation'), 'RESERVOIRS': ('id', 'total_head'),
                'TANKS': ('id', 'elevation', 'initial_level', 'min_level', 'max_level', 'diameter'),
                'PIPES': ('id', 'start', 'end', 'length', 'diameter', 'roughness'),
                'PUMPS': ('id', 'start', 'end'),
                'VALVES': ('id', 'start', 'end', 'diameter', 'valve_type', 'valve_setting'),
            }[section]
            missing = missing_fields(source, required)
            if missing:
                error(feedback, f"Missing required fields in {section.title()}: " + ", ".join(missing))

        workflow = self.parameterAsEnum(parameters, self.WORKFLOW, context)
        existing = self.parameterAsFile(parameters, self.INPUT_EPANET, context)
        options = self._options(parameters, context) if workflow == self.WORKFLOW_SCRATCH else {}
        sections = read_sections(existing) if workflow == self.WORKFLOW_EXISTING else scratch_sections(options)
        if workflow == self.WORKFLOW_EXISTING:
            from .legacy_layers import existing_defaults
            sources = existing_defaults(sources, existing, sections)
        if workflow == self.WORKFLOW_SCRATCH:
            definitions = self.parameterAsFile(parameters, 'INPUT_DEFINITIONS', context) if 'INPUT_DEFINITIONS' in parameters else ''
            if definitions:
                definitions_sections = read_sections(definitions)
                for name in ('PATTERNS', 'CURVES'):
                    sections[name] = definitions_sections.get(name, [])
            values = {}
            readers = {
                'enum': self.parameterAsEnum, 'number': self.parameterAsDouble,
                'integer': self.parameterAsInt, 'boolean': self.parameterAsBool,
                'string': self.parameterAsString, 'time': self.parameterAsString,
            }
            for key, _label, kind, default, _choices, _section, _directive in OPTION_SPECS:
                values[key] = readers[kind](parameters, key, context) if key in parameters else default
            try:
                for section, lines in analysis_sections(values, options['version']).items():
                    sections.setdefault(section, []).extend(lines)
                matrix = self.parameterAsMatrix(parameters, 'REPORT_FIELDS', context) if 'REPORT_FIELDS' in parameters else []
                sections.setdefault('REPORT', []).extend(report_field_lines(matrix))
            except ValueError as exc:
                error(feedback, str(exc))
        generated, node_ids, link_records = self._serialize_sources(sources)
        sections = merge_model_sections(sections, generated)
        node_ids = [parse_tokens(row)[0] for name in ('JUNCTIONS', 'RESERVOIRS', 'TANKS') for row in sections.get(name, [])]
        link_records = [parse_tokens(row)[:3] for name in ('PIPES', 'PUMPS', 'VALVES') for row in sections.get(name, [])]
        problems = graph.validate_records(node_ids, link_records)
        if any(problems.values()):
            error(feedback, "EPANET network is not valid: " + problem_text(problems))
        try:
            validate_model(sections)
        except (ValueError, IndexError) as exc:
            error(feedback, 'Invalid EPANET model: ' + str(exc))

        output = self.parameterAsFileOutput(parameters, self.OUTPUT, context)
        if feedback.isCanceled():
            return {}
        write_sections(output, sections)
        info(feedback, "Output mode", self.WORKFLOW_OPTIONS[workflow])
        if workflow == self.WORKFLOW_SCRATCH:
            info(feedback, "EPANET version", options["version"])
        info(feedback, "Output file", output)
        finish(feedback)
        return {} if feedback.isCanceled() else {self.OUTPUT: output}

    @staticmethod
    def _serialize_sources(sources):
        result = {name: [] for name in PHYSICAL_SECTIONS + ("COORDINATES", "VERTICES")}
        node_ids = []
        link_records = []
        seen_nodes = set()
        seen_links = set()
        for section in ("JUNCTIONS", "RESERVOIRS", "TANKS"):
            for feature in sources.get(section, ()).getFeatures() if section in sources else ():
                node_id = str(_value(feature, "id"))
                if node_id in seen_nodes:
                    raise ValueError(f"Duplicated node id: {node_id}")
                seen_nodes.add(node_id)
                node_ids.append(node_id)
                if section == "JUNCTIONS":
                    result[section].append(_line(node_id, _value(feature, "elevation", 0), _value(feature, "base_demand", 0), _value(feature, "demand_pattern")))
                elif section == "RESERVOIRS":
                    result[section].append(_line(node_id, _value(feature, "total_head", 0), _value(feature, "head_pattern")))
                else:
                    result[section].append(_line(
                        node_id, _value(feature, "elevation", 0), _value(feature, "initial_level", 0),
                        _value(feature, "min_level", 0), _value(feature, "max_level", 0),
                        _value(feature, "diameter", 0), _value(feature, "min_volume", 0),
                        _value(feature, "volume_curve"),
                    ))
                x, y = _point(feature)
                result["COORDINATES"].append(_line(node_id, x, y))
                NetworkToEpanetAlgorithm._node_supplemental(result, feature, node_id, section)

        for section in ("PIPES", "PUMPS", "VALVES"):
            for feature in sources.get(section, ()).getFeatures() if section in sources else ():
                link_id = str(_value(feature, "id"))
                if link_id in seen_links:
                    raise ValueError(f"Duplicated link id: {link_id}")
                seen_links.add(link_id)
                start_id = str(_value(feature, "start"))
                end_id = str(_value(feature, "end"))
                link_records.append((link_id, start_id, end_id))
                if section == "PIPES":
                    status = str(_value(feature, 'status', 'OPEN')).upper()
                    if str(_value(feature, 'type', '')).upper() == 'CVPIPE':
                        explicit_status = _value(feature, 'status')
                        if explicit_status is not None and status != 'CV':
                            raise ValueError('Conflicting CVPIPE type and status: ' + link_id)
                        status = 'CV'
                    if status not in ('OPEN', 'CLOSED', 'CV'):
                        raise ValueError('Invalid pipe status: ' + link_id)
                    result[section].append(_line(
                        link_id, start_id, end_id, _value(feature, "length", 0),
                        _value(feature, "diameter", 0), _value(feature, "roughness", 0),
                        _value(feature, "minor_loss", 0), status,
                    ))
                elif section == "PUMPS":
                    values = [link_id, start_id, end_id]
                    if (_value(feature, 'pump_power') is not None) == bool(_value(feature, 'head_curve')):
                        raise ValueError('Specify exactly one pump power or head curve: ' + link_id)
                    if _value(feature, "pump_power") is not None:
                        values.extend(("POWER", _value(feature, "pump_power")))
                    elif _value(feature, "head_curve"):
                        values.extend(("HEAD", _value(feature, "head_curve")))
                    if _value(feature, "pump_speed") is not None:
                        values.extend(("SPEED", _value(feature, "pump_speed")))
                    if _value(feature, "pump_pattern"):
                        values.extend(("PATTERN", _value(feature, "pump_pattern")))
                    result[section].append(_line(*values))
                else:
                    result[section].append(_line(
                        link_id, start_id, end_id, _value(feature, "diameter", 0),
                        _value(feature, "valve_type", "PRV"), _value(feature, "valve_setting", 0),
                        _value(feature, "minor_loss", 0),
                    ))
                result["VERTICES"].extend(_vertices(feature, link_id))
                NetworkToEpanetAlgorithm._link_supplemental(result, feature, link_id, section)
        return result, node_ids, link_records

    @staticmethod
    def _node_supplemental(result, feature, node_id, section):
        if section == 'JUNCTIONS':
            try:
                demands = feature['demand_categories']
            except KeyError:
                demands = None
            else:
                result.setdefault('_DEMAND_IDS', []).append(node_id)
            if demands is not None and not (hasattr(demands, 'isNull') and demands.isNull()):
                for line in str(demands).splitlines():
                    tokens = parse_tokens(line)
                    if not tokens:
                        continue
                    if len(tokens) > 2:
                        raise ValueError('Demand category requires demand and optional pattern: ' + node_id)
                    float(tokens[0])
                    result.setdefault('DEMANDS', []).append(node_id + ' ' + line)
        if _value(feature, "emitter_coefficient") is not None:
            result.setdefault("EMITTERS", []).append(_line(node_id, _value(feature, "emitter_coefficient")))
        if _value(feature, "initial_quality") is not None:
            result.setdefault("QUALITY", []).append(_line(node_id, _value(feature, "initial_quality")))
        if _value(feature, "source_type") and _value(feature, "source_quality") is not None:
            result.setdefault("SOURCES", []).append(_line(node_id, _value(feature, "source_type"), _value(feature, "source_quality"), _value(feature, "source_pattern")))
        if section == "TANKS" and _value(feature, "mixing_model"):
            result.setdefault("MIXING", []).append(_line(node_id, _value(feature, "mixing_model"), _value(feature, "mixing_fraction")))
        if section == "TANKS" and _value(feature, "tank_reaction_coeff") is not None:
            result.setdefault("REACTIONS", []).append(_line("TANK", node_id, _value(feature, "tank_reaction_coeff")))
        if _value(feature, "tag"):
            result.setdefault("TAGS", []).append(_line("NODE", node_id, _value(feature, "tag")))

    @staticmethod
    def _link_supplemental(result, feature, link_id, section):
        if section != 'PIPES' and _value(feature, "status"):
            result.setdefault("STATUS", []).append(_line(link_id, _value(feature, "status")))
        if _value(feature, "bulk_reaction_coeff") is not None:
            result.setdefault("REACTIONS", []).append(_line("BULK", link_id, _value(feature, "bulk_reaction_coeff")))
        if _value(feature, "wall_reaction_coeff") is not None:
            result.setdefault("REACTIONS", []).append(_line("WALL", link_id, _value(feature, "wall_reaction_coeff")))
        if section == "PUMPS":
            for key, field in (("PRICE", "energy_price"), ("PATTERN", "energy_pattern"), ("EFFIC", "efficiency_curve")):
                if _value(feature, field) is not None:
                    result.setdefault("ENERGY", []).append(_line("PUMP", link_id, key, _value(feature, field)))
        if _value(feature, "tag"):
            result.setdefault("TAGS", []).append(_line("LINK", link_id, _value(feature, "tag")))

    @classmethod
    def _minimal_template_text(cls, version, flow_units):
        """Compatibility helper retained for callers and tests."""
        normalised = "2.2" if str(version).startswith("2.2") else "2.0"
        options = {
            "version": normalised, "flow_units": flow_units, "headloss": "H-W",
            "demand_model": "DDA", "default_pattern": "", "demand_multiplier": 1.0,
            "emitter_exponent": 0.5, "viscosity": 1.0, "diffusivity": 1.0,
            "specific_gravity": 1.0, "trials": 40, "accuracy": 0.001,
            "unbalanced": "STOP", "minimum_pressure": 0.0,
            "required_pressure": 0.1, "pressure_exponent": 0.5,
        }
        sections = scratch_sections(options)
        text = ""
        for name, lines in sections.items():
            text += f"[{name}]\n" + "\n".join(' '.join(parse_tokens(line)) for line in lines) + "\n"
        return text + "[END]\n"
