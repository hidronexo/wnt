"""Typed EPANET layer schemas and INP option helpers."""

from collections import OrderedDict
from pathlib import Path
import os
import tempfile
import math

from .utils_parser import SectionedText, format_tokens, parse_tokens


PROVENANCE_FIELDS = ("inp_source", "epanet_version")

LAYER_SCHEMAS = OrderedDict((
    ("JUNCTIONS", (
        ("id", "string"), ("elevation", "double"),
        ("base_demand", "double"), ("demand_pattern", "string"),
        ("demand_categories", "string"),
        ("emitter_coefficient", "double"), ("initial_quality", "double"),
        ("source_type", "string"), ("source_quality", "double"),
        ("source_pattern", "string"), ("tag", "string"),
        ("inp_source", "string"), ("epanet_version", "string"),
    )),
    ("RESERVOIRS", (
        ("id", "string"), ("total_head", "double"),
        ("head_pattern", "string"), ("initial_quality", "double"),
        ("source_type", "string"), ("source_quality", "double"),
        ("source_pattern", "string"), ("tag", "string"),
        ("inp_source", "string"), ("epanet_version", "string"),
    )),
    ("TANKS", (
        ("id", "string"), ("elevation", "double"),
        ("initial_level", "double"), ("min_level", "double"),
        ("max_level", "double"), ("diameter", "double"),
        ("min_volume", "double"), ("volume_curve", "string"),
        ("initial_quality", "double"), ("source_type", "string"),
        ("source_quality", "double"), ("source_pattern", "string"),
        ("mixing_model", "string"), ("mixing_fraction", "double"),
        ("tank_reaction_coeff", "double"), ("tag", "string"),
        ("inp_source", "string"), ("epanet_version", "string"),
    )),
    ("PIPES", (
        ("id", "string"), ("start", "string"), ("end", "string"),
        ("length", "double"), ("diameter", "double"),
        ("roughness", "double"), ("minor_loss", "double"),
        ("status", "string"), ("bulk_reaction_coeff", "double"),
        ("wall_reaction_coeff", "double"), ("tag", "string"),
        ("inp_source", "string"), ("epanet_version", "string"),
    )),
    ("PUMPS", (
        ("id", "string"), ("start", "string"), ("end", "string"),
        ("pump_power", "double"), ("head_curve", "string"),
        ("pump_speed", "double"), ("pump_pattern", "string"),
        ("status", "string"), ("energy_price", "double"),
        ("energy_pattern", "string"), ("efficiency_curve", "string"),
        ("tag", "string"), ("inp_source", "string"),
        ("epanet_version", "string"),
    )),
    ("VALVES", (
        ("id", "string"), ("start", "string"), ("end", "string"),
        ("diameter", "double"), ("valve_type", "string"),
        ("valve_setting", "string"), ("minor_loss", "double"),
        ("status", "string"), ("tag", "string"),
        ("inp_source", "string"), ("epanet_version", "string"),
    )),
))

NODE_SECTIONS = ("JUNCTIONS", "RESERVOIRS", "TANKS")
LINK_SECTIONS = ("PIPES", "PUMPS", "VALVES")
PHYSICAL_SECTIONS = NODE_SECTIONS + LINK_SECTIONS

EPANET_22_OPTION_PREFIXES = (
    "HEADERROR",
    "FLOWCHANGE",
    "DEMAND MODEL",
    "MINIMUM PRESSURE",
    "REQUIRED PRESSURE",
    "PRESSURE EXPONENT",
)


def read_sections(path):
    """Read an INP file and return its parsed sections."""
    document = SectionedText()
    document.read(path)
    # Demand category names are comments with user-visible meaning.
    active = ''
    demands = []
    for line in Path(path).read_text(encoding='latin-1').splitlines():
        text = line.strip()
        if text.startswith('['):
            active = text.partition(']')[0].lstrip('[').upper()
        elif active == 'DEMANDS' and parse_tokens(text):
            demands.append(text)
    if 'DEMANDS' in document.sections:
        document.sections['DEMANDS'] = demands
    return document.sections


def detect_epanet_version(sections):
    """Return the minimum EPANET version implied by known option syntax."""
    for line in sections.get("OPTIONS", []):
        option = " ".join(parse_tokens(line)).upper()
        if option.startswith(EPANET_22_OPTION_PREFIXES):
            return "2.2"
    return "2.0"


def normalise_source(path):
    """Return a stable absolute source path for provenance fields."""
    return str(Path(path).resolve())


def option_lines(options):
    """Serialize typed scratch-model options to EPANET option lines."""
    extra_trials = options.get('unbalanced_trials', 0)
    if options['unbalanced'] == 'CONTINUE':
        if not math.isfinite(float(extra_trials)) or float(extra_trials) < 0 or float(extra_trials) != int(extra_trials):
            raise ValueError('Additional trials must be a nonnegative integer')
    for key in ('demand_multiplier', 'emitter_exponent', 'viscosity', 'diffusivity',
                'specific_gravity', 'trials', 'accuracy', 'minimum_pressure',
                'required_pressure', 'pressure_exponent'):
        value = float(options[key])
        if not math.isfinite(value) or value < 0:
            raise ValueError('Invalid hydraulic option: ' + key)
        if key in ('emitter_exponent', 'viscosity', 'specific_gravity', 'accuracy', 'pressure_exponent') and value == 0:
            raise ValueError('Hydraulic option must be positive: ' + key)
    if float(options['trials']) < 1 or float(options['trials']) != int(options['trials']):
        raise ValueError('Maximum trials must be a positive integer')
    if options['version'] == '2.2' and options['demand_model'] == 'PDA' and options['required_pressure'] <= options['minimum_pressure']:
        raise ValueError('Required pressure must exceed minimum pressure')
    lines = [
        format_tokens(("UNITS", options["flow_units"])),
        format_tokens(("HEADLOSS", options["headloss"])),
        format_tokens(("DEMAND MULTIPLIER", options["demand_multiplier"])),
        format_tokens(("EMITTER EXPONENT", options["emitter_exponent"])),
        format_tokens(("VISCOSITY", options["viscosity"])),
        format_tokens(("DIFFUSIVITY", options["diffusivity"])),
        format_tokens(("SPECIFIC GRAVITY", options["specific_gravity"])),
        format_tokens(("TRIALS", options["trials"])),
        format_tokens(("ACCURACY", options["accuracy"])),
        format_tokens(("UNBALANCED", options["unbalanced"] + (f' {int(extra_trials)}' if options['unbalanced'] == 'CONTINUE' and extra_trials else ''))),
    ]
    if options.get('default_pattern'):
        lines.append(format_tokens(('PATTERN', options['default_pattern'])))
    if options["version"] == "2.2":
        lines.extend((
            format_tokens(("DEMAND MODEL", options["demand_model"])),
            format_tokens(("MINIMUM PRESSURE", options["minimum_pressure"])),
            format_tokens(("REQUIRED PRESSURE", options["required_pressure"])),
            format_tokens(("PRESSURE EXPONENT", options["pressure_exponent"])),
        ))
    return lines


def scratch_sections(options):
    """Return ordered sections for a new EPANET model."""
    sections = OrderedDict()
    sections["TITLE"] = ["; File generated automatically by Water Network Tools"]
    for name in PHYSICAL_SECTIONS:
        sections[name] = []
    sections["COORDINATES"] = []
    sections["VERTICES"] = []
    sections["BACKDROP"] = ["DIMENSIONS 0 0 0 0"]
    sections["OPTIONS"] = option_lines(options)
    return sections


def write_sections(path, sections):
    """Write ordered EPANET sections using the repository's INP encoding."""
    document = SectionedText()
    document.sections = sections
    destination = Path(path)
    fd, temporary = tempfile.mkstemp(prefix='.wnt-', suffix='.inp', dir=destination.parent)
    os.close(fd)
    try:
        document.write(temporary)
        os.replace(temporary, destination)
    finally:
        Path(temporary).unlink(missing_ok=True)


def merge_model_sections(existing, generated):
    """Update supplied objects, preserving unrelated model rows and global settings."""
    result = OrderedDict((key, list(value)) for key, value in existing.items())
    nodes = {parse_tokens(row)[0] for name in NODE_SECTIONS for row in generated.get(name, [])}
    links = {parse_tokens(row)[0] for name in LINK_SECTIONS for row in generated.get(name, [])}

    def replaced(name, tokens):
        if not tokens:
            return False
        if name in NODE_SECTIONS or name in ('COORDINATES', 'EMITTERS', 'QUALITY', 'SOURCES', 'MIXING'):
            return tokens[0] in nodes
        if name in LINK_SECTIONS or name in ('VERTICES', 'STATUS'):
            return tokens[0] in links
        if name == 'DEMANDS':
            return tokens[0] in generated.get('_DEMAND_IDS', [])
        if name == 'REACTIONS' and len(tokens) > 1:
            return tokens[0].upper() in ('BULK', 'WALL', 'TANK') and tokens[1] in (nodes if tokens[0].upper() == 'TANK' else links)
        if name == 'ENERGY' and len(tokens) > 1:
            return tokens[0].upper() == 'PUMP' and tokens[1] in links
        if name == 'TAGS' and len(tokens) > 1:
            return tokens[1] in (nodes if tokens[0].upper() == 'NODE' else links)
        return False

    affected = PHYSICAL_SECTIONS + ('COORDINATES', 'VERTICES', 'DEMANDS', 'EMITTERS', 'QUALITY', 'SOURCES', 'MIXING', 'REACTIONS', 'STATUS', 'ENERGY', 'TAGS')
    for name in affected:
        rows = [row for row in result.get(name, []) if not replaced(name, parse_tokens(row))]
        rows.extend(generated.get(name, []))
        if rows or name in result or name in generated:
            result[name] = rows
    return result
