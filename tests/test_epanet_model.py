"""Tests for QGIS-independent EPANET model helpers."""

from wnt.utils.utils_epanet_model import (
    LAYER_SCHEMAS,
    detect_epanet_version,
    option_lines,
    scratch_sections,
)


def options(version="2.2"):
    return {
        "version": version,
        "flow_units": "LPS",
        "headloss": "H-W",
        "demand_model": "PDA",
        "default_pattern": "1",
        "demand_multiplier": 1.0,
        "emitter_exponent": 0.5,
        "viscosity": 1.0,
        "diffusivity": 1.0,
        "specific_gravity": 1.0,
        "trials": 40,
        "accuracy": 0.001,
        "unbalanced": "STOP",
        "minimum_pressure": 0.0,
        "required_pressure": 15.0,
        "pressure_exponent": 0.5,
    }


def test_six_schemas_have_provenance_and_no_generic_epanet_field():
    assert tuple(LAYER_SCHEMAS) == (
        "JUNCTIONS", "RESERVOIRS", "TANKS", "PIPES", "PUMPS", "VALVES"
    )
    for schema in LAYER_SCHEMAS.values():
        names = [name for name, _kind in schema]
        assert names[-2:] == ["inp_source", "epanet_version"]
        assert "epanet" not in names


def test_version_detection_uses_unambiguous_epanet_22_options():
    assert detect_epanet_version({"OPTIONS": ["UNITS LPS", "HEADLOSS H-W"]}) == "2.0"
    assert detect_epanet_version({"OPTIONS": ["DEMAND MODEL PDA"]}) == "2.2"
    assert detect_epanet_version({"OPTIONS": ["REQUIRED PRESSURE 15"]}) == "2.2"


def test_epanet_20_omits_pressure_driven_options():
    lines = option_lines(options("2.0"))
    assert not any(line.startswith("DEMAND MODEL") for line in lines)
    assert not any(line.startswith("REQUIRED PRESSURE") for line in lines)


def test_epanet_22_writes_editable_scratch_options_and_six_sections():
    sections = scratch_sections(options())
    assert all(name in sections for name in LAYER_SCHEMAS)
    assert "HEADLOSS    H-W" in sections["OPTIONS"]
    assert "DEMAND MODEL    PDA" in sections["OPTIONS"]
    assert "REQUIRED PRESSURE    15.0" in sections["OPTIONS"]
