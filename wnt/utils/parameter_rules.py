"""Declarative Processing form dependencies, independent of Qt."""

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=8)
def _steady_file(path, modified, size):
    from .export_files import ModelReferences
    return not ModelReferences(path).extended_period()


def parameter_rules(algorithm, name, metadata):
    """Return controller/allowed-value pairs, combined with logical AND."""
    rules = []
    if metadata.get('epanet_scratch_only'):
        rules.append(('WORKFLOW', (1,)))
    if metadata.get('epanet_existing_only'):
        rules.append(('WORKFLOW', (0,)))
    if algorithm == 'network_to_epanet':
        if name in ('DEMAND_MODEL', 'MINIMUM_PRESSURE', 'REQUIRED_PRESSURE', 'PRESSURE_EXPONENT', 'MAXIMUM_HEAD_ERROR', 'MAXIMUM_FLOW_CHANGE'):
            rules.append(('EPANET_VERSION', (1,)))
        if name in ('MINIMUM_PRESSURE', 'REQUIRED_PRESSURE', 'PRESSURE_EXPONENT'):
            rules.append(('DEMAND_MODEL', (1,)))
        if name in ('CHEMICAL_NAME', 'MASS_UNITS', 'DIFFUSIVITY', 'BULK_ORDER', 'WALL_ORDER', 'TANK_ORDER', 'GLOBAL_BULK', 'GLOBAL_WALL', 'LIMITING_CONCENTRATION', 'WALL_CORRELATION'):
            rules.append(('QUALITY_ANALYSIS', (1,)))
        if name == 'TRACE_NODE':
            rules.append(('QUALITY_ANALYSIS', (3,)))
        if name in ('QUALITY_TOLERANCE', 'QUALITY_TIMESTEP'):
            rules.append(('QUALITY_ANALYSIS', (1, 2, 3)))
        if name in ('HYDRAULIC_TIMESTEP', 'QUALITY_TIMESTEP', 'RULE_TIMESTEP', 'PATTERN_TIMESTEP', 'PATTERN_START', 'REPORT_TIMESTEP', 'REPORT_START', 'STATISTIC'):
            rules.append(('DURATION', 'positive_time'))
    if algorithm == 'network_from_lines':
        if name == 'INPUT_DEM':
            rules.append(('ELEVATION_SOURCE', (2,)))
        if name in ('INPUT_LANDXML', 'SURFACE_NAME'):
            rules.append(('ELEVATION_SOURCE', (3,)))
    if algorithm == 'network_to_xml':
        if name in ('INPUT_NODES', 'INPUT_LINES', 'WNT_MODEL_TYPE'):
            rules.append(('LAYER_INPUT_MODE', (1,)))
        if name in ('INPUT_JUNCTIONS', 'INPUT_RESERVOIRS', 'INPUT_TANKS', 'INPUT_PIPES', 'INPUT_PUMPS', 'INPUT_VALVES'):
            rules.append(('LAYER_INPUT_MODE', (0,)))
        if name == 'WNT_MODEL_TYPE':
            rules.append(('OUTPUT_FORMAT', (0,)))
        if name == 'LANDXML_NETWORK_TYPE':
            rules.append(('OUTPUT_FORMAT', (1,)))
    if algorithm in ('classify', 'node_degrees', 'elevation_from_raster', 'elevation_from_tin', 'split_lines_at_points', 'validate'):
        if name.startswith('OUTPUT') and name != 'OUTPUT_MODE':
            rules.append(('OUTPUT_MODE', (0,)))
        if algorithm == 'split_lines_at_points' and name == 'CRS':
            rules.append(('OUTPUT_MODE', (0,)))
    if algorithm == 'results_from_epanet':
        if name in ('OUTPUT_NODES', 'OUTPUT_LINES'):
            rules.append(('RESULT_TYPE', (0, 2)))
        if name in ('OUTPUT_NODE_QUALITY', 'OUTPUT_LINK_QUALITY'):
            rules.append(('RESULT_TYPE', (1, 2)))
    if algorithm == 'network_to_pipesizing' and name in ('FIELD_FIRE_FLOW', 'FIRE_FLOW', 'FIRE_FLOW_2'):
        rules.append(('INPUT_FIRE_SCENARIOS', 'present'))
    if algorithm == 'network_to_pipesizing' and name in ('INPUT_FIRE_SCENARIOS', 'FIELD_FIRE_FLOW', 'FIRE_FLOW', 'FIRE_FLOW_2', 'FIRE_FACTOR', 'FIELD_PRESSURE_FIRE'):
        rules.append(('INPUT_EPANET', 'steady_inp'))
    return rules


def enabled(rules, values):
    """Evaluate a dependency set without changing any stored parameter value."""
    for controller, allowed in rules:
        value = values.get(controller)
        if allowed == 'positive_time':
            from .utils_epanet_options import time_hours
            try:
                if time_hours(value) <= 0:
                    return False
            except ValueError:
                return False
        elif allowed == 'steady_inp':
            try:
                path = Path(str(value))
                stat = path.stat()
                if not _steady_file(str(path), stat.st_mtime_ns, stat.st_size):
                    return False
            except (OSError, ValueError, IndexError):
                return False
        elif allowed == 'present':
            if value is None or value == '':
                return False
        elif value not in allowed:
            return False
    return True
