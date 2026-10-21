"""EPANET analysis option inventory shared by forms and INP serialization."""

import math
import re


# key, English label, kind, default, choices/range, section, directive
OPTION_SPECS = (
    ('HYDRAULICS_MODE', 'Hydraulics — hydraulic results', 'enum', 0, ('Compute', 'Save', 'Use'), '', ''),
    ('HYDRAULICS_FILE', 'Hydraulics — hydraulic results file (.hyd)', 'string', '', (), '', ''),
    ('MAP_FILE', 'Hydraulics — external map file (optional)', 'string', '', (), 'OPTIONS', 'MAP'),
    ('ENERGY_PRICE', 'Energy — price per kWh', 'number', 0, (0, None), 'ENERGY', 'GLOBAL PRICE'),
    ('ENERGY_PATTERN', 'Energy — price pattern', 'string', '', (), 'ENERGY', 'GLOBAL PATTERN'),
    ('PUMP_EFFICIENCY', 'Energy — global pump efficiency (%)', 'number', 75, (0.001, 100), 'ENERGY', 'GLOBAL EFFIC'),
    ('DEMAND_CHARGE', 'Energy — demand charge per maximum kW', 'number', 0, (0, None), 'ENERGY', 'DEMAND CHARGE'),
    ('QUALITY_ANALYSIS', 'Quality — analysis type', 'enum', 0, ('None', 'Chemical', 'Age', 'Trace'), '', ''),
    ('CHEMICAL_NAME', 'Quality — chemical name', 'string', 'CHEMICAL', (), '', ''),
    ('MASS_UNITS', 'Quality — concentration mass units', 'enum', 0, ('mg/L', 'ug/L'), '', ''),
    ('TRACE_NODE', 'Quality — trace node', 'string', '', (), '', ''),
    ('QUALITY_TOLERANCE', 'Quality — tolerance', 'number', 0.01, (0, None), 'OPTIONS', 'TOLERANCE'),
    ('BULK_ORDER', 'Quality — bulk reaction order', 'number', 1, (None, None), 'REACTIONS', 'ORDER BULK'),
    ('WALL_ORDER', 'Quality — wall reaction order', 'enum', 1, ('Zero', 'First'), 'REACTIONS', 'ORDER WALL'),
    ('TANK_ORDER', 'Quality — tank reaction order', 'number', 1, (None, None), 'REACTIONS', 'ORDER TANK'),
    ('GLOBAL_BULK', 'Quality — global bulk reaction coefficient', 'number', 0, (None, None), 'REACTIONS', 'GLOBAL BULK'),
    ('GLOBAL_WALL', 'Quality — global wall reaction coefficient', 'number', 0, (None, None), 'REACTIONS', 'GLOBAL WALL'),
    ('LIMITING_CONCENTRATION', 'Quality — limiting concentration', 'number', 0, (0, None), 'REACTIONS', 'LIMITING POTENTIAL'),
    ('WALL_CORRELATION', 'Quality — wall coefficient correlation', 'number', 0, (None, None), 'REACTIONS', 'ROUGHNESS CORRELATION'),
    ('MAXIMUM_HEAD_ERROR', 'EPANET 2.2 — maximum head error', 'number', 0, (0, None), 'OPTIONS', 'HEADERROR'),
    ('MAXIMUM_FLOW_CHANGE', 'EPANET 2.2 — maximum flow change', 'number', 0, (0, None), 'OPTIONS', 'FLOWCHANGE'),
    ('UNBALANCED_TRIALS', 'Calculation stability — additional trials if unbalanced (0: none)', 'integer', 0, (0, None), '', ''),
    ('CHECK_FREQUENCY', 'Calculation stability — status check frequency', 'integer', 2, (1, None), 'OPTIONS', 'CHECKFREQ'),
    ('MAXIMUM_CHECKS', 'Calculation stability — maximum status checks', 'integer', 10, (0, None), 'OPTIONS', 'MAXCHECK'),
    ('DAMPING_LIMIT', 'Calculation stability — damping limit', 'number', 0, (0, None), 'OPTIONS', 'DAMPLIMIT'),
    ('DURATION', 'Times — total duration', 'time', '0:00', (), 'TIMES', 'DURATION'),
    ('HYDRAULIC_TIMESTEP', 'Times — hydraulic time step', 'time', '1:00', (), 'TIMES', 'HYDRAULIC TIMESTEP'),
    ('QUALITY_TIMESTEP', 'Times — quality time step', 'time', '0:05', (), 'TIMES', 'QUALITY TIMESTEP'),
    ('RULE_TIMESTEP', 'Times — rule time step', 'time', '0:06', (), 'TIMES', 'RULE TIMESTEP'),
    ('PATTERN_TIMESTEP', 'Times — pattern time step', 'time', '1:00', (), 'TIMES', 'PATTERN TIMESTEP'),
    ('PATTERN_START', 'Times — pattern start', 'time', '0:00', (), 'TIMES', 'PATTERN START'),
    ('REPORT_TIMESTEP', 'Times — report time step', 'time', '1:00', (), 'TIMES', 'REPORT TIMESTEP'),
    ('REPORT_START', 'Times — report start', 'time', '0:00', (), 'TIMES', 'REPORT START'),
    ('START_CLOCKTIME', 'Times — start clock time', 'string', '12:00 AM', (), 'TIMES', 'START CLOCKTIME'),
    ('STATISTIC', 'Times — statistic', 'enum', 0, ('NONE', 'AVERAGE', 'MINIMUM', 'MAXIMUM', 'RANGE'), 'TIMES', 'STATISTIC'),
    ('REPORT_PAGE_SIZE', 'Report — page size', 'integer', 0, (0, None), 'REPORT', 'PAGESIZE'),
    ('REPORT_FILE', 'Report — output file', 'string', '', (), 'REPORT', 'FILE'),
    ('REPORT_STATUS', 'Report — status', 'enum', 0, ('NO', 'YES', 'FULL'), 'REPORT', 'STATUS'),
    ('REPORT_SUMMARY', 'Report — summary', 'boolean', True, (), 'REPORT', 'SUMMARY'),
    ('REPORT_ENERGY', 'Report — energy', 'boolean', False, (), 'REPORT', 'ENERGY'),
    ('REPORT_NODES', 'Report — junctions, reservoirs and tanks', 'enum', 1, ('NONE', 'ALL', 'Selected IDs'), '', ''),
    ('REPORT_NODE_IDS', 'Report — selected junction, reservoir and tank IDs', 'string', '', (), '', ''),
    ('REPORT_LINKS', 'Report — pipes, pumps and valves', 'enum', 1, ('NONE', 'ALL', 'Selected IDs'), '', ''),
    ('REPORT_LINK_IDS', 'Report — selected pipe, pump and valve IDs', 'string', '', (), '', ''),
)

# EPANET report keywords are stable tokens, not translatable display labels.
REPORT_FIELDS = ('ELEVATION', 'DEMAND', 'HEAD', 'PRESSURE', 'QUALITY', 'LENGTH',
                 'DIAMETER', 'FLOW', 'VELOCITY', 'HEADLOSS', 'STATUS', 'SETTING',
                 'REACTION', 'F-FACTOR')


def report_field_lines(matrix):
    """Validate a five-column report table (field, YES/NO, precision, below, above)."""
    if not matrix:
        return []
    cells = list(matrix)
    if isinstance(cells[0], (tuple, list)):
        if any(len(row) != 5 for row in cells):
            raise ValueError('Report table requires five columns')
        cells = [value for row in cells for value in row]
    if len(cells) % 5:
        raise ValueError('Report table requires five columns')
    result = []
    seen = set()
    for offset in range(0, len(cells), 5):
        field, display, precision, below, above = [str(v).strip() if v is not None else '' for v in cells[offset:offset + 5]]
        field = field.upper()
        if field not in REPORT_FIELDS or field in seen:
            raise ValueError('Unknown or duplicate report field: ' + field)
        seen.add(field)
        if display:
            if display.upper() not in ('YES', 'NO'):
                raise ValueError('Report field visibility must be YES or NO')
            result.append(f'{field} {display.upper()}')
        if precision:
            if not precision.isdigit() or not 0 <= int(precision) <= 10:
                raise ValueError('Report precision must be an integer from 0 to 10')
            result.append(f'{field} PRECISION {int(precision)}')
        for keyword, value in (('BELOW', below), ('ABOVE', above)):
            if value:
                number = float(value)
                if not math.isfinite(number):
                    raise ValueError('Report filter must be finite')
                result.append(f'{field} {keyword} {number:g}')
        if below and above and float(above) >= float(below):
            raise ValueError('Report ABOVE limit must be less than BELOW limit')
    return result


def _filename(value):
    text = str(value).strip()
    if not text or any(char in text for char in '\r\n;"'):
        raise ValueError('Invalid INP file reference')
    return '"' + text + '"' if any(char.isspace() for char in text) else text


def time_hours(value):
    """Parse a nonnegative EPANET duration in decimal hours or H:MM[:SS]."""
    text = str(value).strip()
    if not re.fullmatch(r'\d+(?:\.\d+)?|\d+:[0-5]\d(?::[0-5]\d)?', text):
        raise ValueError('Invalid time: ' + text)
    parts = [float(part) for part in text.split(':')]
    return sum(part / 60 ** index for index, part in enumerate(parts))


def analysis_sections(values, version):
    """Validate and serialize the analysis inventory, without QGIS dependencies."""
    options = {key: default for key, _, _, default, _, _, _ in OPTION_SPECS}
    options.update(values)
    result = {}
    for key, label, kind, _, limits, section, directive in OPTION_SPECS:
        value = options[key]
        if kind in ('number', 'integer'):
            number = float(value)
            if not math.isfinite(number) or (kind == 'integer' and number != int(number)):
                raise ValueError(label + ': invalid number')
            if limits[0] is not None and number < limits[0] or limits[1] is not None and number > limits[1]:
                raise ValueError(label + ': out of range')
        elif kind == 'enum':
            if not isinstance(value, int) or not 0 <= value < len(limits):
                raise ValueError(label + ': invalid selection')
            value = value if key == 'WALL_ORDER' else limits[value]
        elif kind == 'boolean':
            value = 'YES' if value else 'NO'
        elif kind == 'time':
            hours = time_hours(value)
            if key.endswith('TIMESTEP') and hours <= 0:
                raise ValueError(label + ': must be positive')
        if key == 'START_CLOCKTIME':
            clock = str(value).strip().upper().split()
            if not clock:
                raise ValueError('Invalid start clock time')
            hours = time_hours(clock[0])
            if len(clock) > 2 or (len(clock) == 2 and (clock[1] not in ('AM', 'PM') or not 1 <= hours < 13)) or (len(clock) == 1 and hours >= 24):
                raise ValueError('Invalid start clock time')
        if '\n' in str(value) or '\r' in str(value) or ';' in str(value):
            raise ValueError(label + ': invalid line delimiter')
        if key in ('MAXIMUM_HEAD_ERROR', 'MAXIMUM_FLOW_CHANGE') and version != '2.2':
            continue
        if section == 'REACTIONS' and options['QUALITY_ANALYSIS'] != 1:
            continue
        if key == 'QUALITY_TOLERANCE' and options['QUALITY_ANALYSIS'] == 0:
            continue
        if key in ('REPORT_FILE', 'MAP_FILE') and str(value).strip():
            value = _filename(value)
        if section and str(value) != '':
            result.setdefault(section, []).append(f'{directive} {value}')
    if options['HYDRAULICS_MODE']:
        mode = ('', 'SAVE', 'USE')[options['HYDRAULICS_MODE']]
        result.setdefault('OPTIONS', []).append(f'HYDRAULICS {mode} {_filename(options["HYDRAULICS_FILE"])}')
    for kind, key in (('NODES', 'REPORT_NODE_IDS'), ('LINKS', 'REPORT_LINK_IDS')):
        selection = options['REPORT_' + kind]
        identifiers = str(options[key]).split()
        if selection == 2:
            if not identifiers or any(len(item) > 31 or any(char in item for char in ';"[]') for item in identifiers):
                raise ValueError('Invalid selected report IDs')
            # Short lines also work with the fixed line buffer in EPANET 2.0.
            result.setdefault('REPORT', []).extend(f'{kind} {item}' for item in identifiers)
        else:
            result.setdefault('REPORT', []).append(f'{kind} {("NONE", "ALL")[selection]}')
    quality = options['QUALITY_ANALYSIS']
    if quality == 1:
        name = str(options['CHEMICAL_NAME']).strip()
        if not name or any(char.isspace() for char in name) or name.upper() in ('NONE', 'AGE', 'TRACE'):
            raise ValueError('Invalid chemical name')
        units = ('mg/L', 'ug/L')[options['MASS_UNITS']]
        quality_text = f'{name} {units}'
    elif quality == 3:
        node = str(options['TRACE_NODE']).strip()
        if not node or any(char.isspace() for char in node):
            raise ValueError('A trace node is required')
        quality_text = 'TRACE ' + node
    else:
        quality_text = 'AGE' if quality == 2 else 'NONE'
    result.setdefault('OPTIONS', []).append('QUALITY ' + quality_text)
    if time_hours(options['REPORT_START']) > time_hours(options['DURATION']):
        raise ValueError('Report start exceeds simulation duration')
    return result
