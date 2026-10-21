"""Regression tests for data preservation and solver export contracts."""

import pytest

from wnt.utils.export_files import catalog_groups, publish_files
from wnt.utils.parameter_rules import enabled, parameter_rules
from wnt.utils.utils_epanet_model import merge_model_sections
from wnt.utils.utils_epanet_options import analysis_sections, time_hours


def test_optional_hydraulics_and_report_selection():
    result = analysis_sections({'HYDRAULICS_MODE': 1, 'HYDRAULICS_FILE': 'model results.hyd',
                                'REPORT_NODES': 2, 'REPORT_NODE_IDS': 'J1 R1 T1',
                                'REPORT_LINKS': 2, 'REPORT_LINK_IDS': 'P1 U1 V1'}, '2.2')
    assert 'HYDRAULICS SAVE "model results.hyd"' in result['OPTIONS']
    assert [line for line in result['REPORT'] if line.startswith('NODES')] == ['NODES J1', 'NODES R1', 'NODES T1']
    assert [line for line in result['REPORT'] if line.startswith('LINKS')] == ['LINKS P1', 'LINKS U1', 'LINKS V1']
    with pytest.raises(ValueError, match='file reference'):
        analysis_sections({'HYDRAULICS_MODE': 2}, '2.2')
    with pytest.raises(ValueError, match='selected report IDs'):
        analysis_sections({'REPORT_NODES': 2}, '2.2')


def test_report_table_validation():
    from wnt.utils.utils_epanet_options import report_field_lines
    assert report_field_lines([['PRESSURE', 'YES', '3', '50', '10']]) == [
        'PRESSURE YES', 'PRESSURE PRECISION 3', 'PRESSURE BELOW 50', 'PRESSURE ABOVE 10']
    assert report_field_lines(['FLOW', '', '', '', '']) == []
    for cells in (['NO_FIELD', '', '', '', ''], ['FLOW', 'MAYBE', '', '', ''],
                  ['FLOW', '', '-1', '', ''], ['FLOW', '', '', 'nan', ''],
                  ['FLOW', '', '', '1', '2'], ['FLOW']):
        with pytest.raises(ValueError):
            report_field_lines(cells)


def test_additional_option_widget_dependencies():
    for name, controller, active, inactive in (
            ('HYDRAULICS_FILE', 'HYDRAULICS_MODE', 1, 0),
            ('UNBALANCED_TRIALS', 'UNBALANCED', 1, 0),
            ('REPORT_NODE_IDS', 'REPORT_NODES', 2, 1),
            ('REPORT_LINK_IDS', 'REPORT_LINKS', 2, 0)):
        rules = parameter_rules('network_to_epanet', name, {'epanet_scratch_only': True})
        assert enabled(rules, {'WORKFLOW': 1, controller: active})
        assert not enabled(rules, {'WORKFLOW': 1, controller: inactive})
        assert not enabled(rules, {'WORKFLOW': 0, controller: active})


def test_partial_model_update_preserves_other_objects_and_global_settings():
    existing = {
        'JUNCTIONS': ['J1 10 1', 'J2 20 2'], 'RESERVOIRS': ['R1 100'],
        'PIPES': ['P1 R1 J1 50 100 120', 'P2 J1 J2 25 100 120'],
        'ENERGY': ['GLOBAL PRICE 0.25', 'PUMP PU1 EFFIC E1'],
        'REACTIONS': ['ORDER BULK 1', 'GLOBAL BULK -0.2', 'BULK P1 -0.3'],
        'PATTERNS': ['D1 1 2 3'], 'RULES': ['RULE R1', 'IF NODE J1 PRESSURE BELOW 10'],
    }
    merged = merge_model_sections(existing, {'PIPES': ['P1 R1 J1 50 150 120 0 CV']})
    assert merged['JUNCTIONS'] == existing['JUNCTIONS']
    assert merged['RESERVOIRS'] == existing['RESERVOIRS']
    assert merged['PIPES'] == ['P2 J1 J2 25 100 120', 'P1 R1 J1 50 150 120 0 CV']
    assert merged['REACTIONS'] == ['ORDER BULK 1', 'GLOBAL BULK -0.2']
    assert merged['ENERGY'] == existing['ENERGY']
    assert merged['PATTERNS'] == existing['PATTERNS']
    assert merged['RULES'] == existing['RULES']


def test_options_keep_legacy_status_checks_but_gate_22_convergence():
    old = analysis_sections({}, '2.0')['OPTIONS']
    new = analysis_sections({}, '2.2')['OPTIONS']
    assert 'CHECKFREQ 2' in old
    assert 'DAMPLIMIT 0' in old
    assert not any(line.startswith('HEADERROR') for line in old)
    assert 'HEADERROR 0' in new
    assert 'FLOWCHANGE 0' in new


def test_quality_trace_is_required_and_reactions_only_apply_to_chemical():
    with pytest.raises(ValueError, match='trace node'):
        analysis_sections({'QUALITY_ANALYSIS': 3}, '2.2')
    trace = analysis_sections({'QUALITY_ANALYSIS': 3, 'TRACE_NODE': 'R1'}, '2.2')
    assert 'QUALITY TRACE R1' in trace['OPTIONS']
    assert 'REACTIONS' not in trace
    chemical = analysis_sections({'QUALITY_ANALYSIS': 1}, '2.2')
    assert 'QUALITY CHEMICAL mg/L' in chemical['OPTIONS']
    assert 'ORDER TANK 1' in chemical['REACTIONS']


@pytest.mark.parametrize('value', ['-1', '1:60', 'nan', '1\n[OPTIONS]'])
def test_invalid_times_are_rejected(value):
    with pytest.raises(ValueError):
        time_hours(value)


def test_catalog_contracts_are_distinct_and_reject_nonfinite_numbers():
    assert catalog_groups(b'S1 100 120\n', 3) == {'S1'}
    assert catalog_groups(b'S1 100 120 50\n', 4) == {'S1'}
    for data in (b'S1 100 120 50', b'S1 nan 120', b'S1 100 120 # comment'):
        with pytest.raises(ValueError):
            catalog_groups(data, 3)


def test_publication_rejects_source_collision_without_changing_files(tmp_path):
    source = tmp_path / 'model.inp'
    source.write_bytes(b'original')
    catalog = tmp_path / 'model.psr'
    with pytest.raises(ValueError, match='distinct'):
        publish_files({source: b'new', catalog: b'catalog'}, inputs=(source,))
    assert source.read_bytes() == b'original'
    assert not catalog.exists()


def test_publication_restores_both_destinations_after_second_replace_fails(tmp_path, monkeypatch):
    import wnt.utils.export_files as export_files
    first, second = tmp_path / 'first.pro', tmp_path / 'second.psr'
    first.write_bytes(b'old project')
    second.write_bytes(b'old catalog')
    replace = export_files.os.replace

    def fail_second(source, destination):
        if destination == second:
            raise OSError('simulated failure')
        replace(source, destination)

    monkeypatch.setattr(export_files.os, 'replace', fail_second)
    with pytest.raises(OSError, match='simulated'):
        publish_files({first: b'new project', second: b'new catalog'})
    assert first.read_bytes() == b'old project'
    assert second.read_bytes() == b'old catalog'
    assert sorted(path.name for path in tmp_path.iterdir()) == ['first.pro', 'second.psr']


def test_pda_and_quality_controls_combine_with_workflow():
    rules = parameter_rules('network_to_epanet', 'MINIMUM_PRESSURE', {'epanet_scratch_only': True})
    assert enabled(rules, {'WORKFLOW': 1, 'EPANET_VERSION': 1, 'DEMAND_MODEL': 1})
    for values in ({'WORKFLOW': 0, 'EPANET_VERSION': 1, 'DEMAND_MODEL': 1},
                   {'WORKFLOW': 1, 'EPANET_VERSION': 0, 'DEMAND_MODEL': 1},
                   {'WORKFLOW': 1, 'EPANET_VERSION': 1, 'DEMAND_MODEL': 0}):
        assert not enabled(rules, values)
def test_solver_references_distinguish_pipe_from_pump_and_zero_pressure(tmp_path):
    from wnt.utils.export_files import ModelReferences, pressure_value
    model = tmp_path / 'model with spaces.inp'
    model.write_text('[JUNCTIONS]\nJ 0\n[RESERVOIRS]\nR 10\n[PIPES]\nP R J 10 100 120 0 CV\n[PUMPS]\nU R J POWER 1\n[TIMES]\nDURATION 24:00\n', encoding='latin-1')
    refs = ModelReferences(model)
    refs.require('PIPES', 'P')
    refs.require('JUNCTIONS', 'J')
    assert refs.extended_period()
    assert pressure_value(0) == 0
    with pytest.raises(ValueError, match='not found'):
        refs.require('PIPES', 'U')
    with pytest.raises(ValueError, match='duplicate'):
        refs.require('JUNCTIONS', 'J')
    with pytest.raises(ValueError):
        pressure_value(float('nan'))


def test_scratch_reference_validation_rejects_undefined_patterns():
    from wnt.utils.model_validation import validate_model
    sections = {'JUNCTIONS': ['J 0 1 DAILY'], 'RESERVOIRS': ['R 30'],
                'PIPES': ['P R J 10 100 120 0 CV']}
    with pytest.raises(ValueError, match='Undefined PATTERNS'):
        validate_model(sections)
    sections['PATTERNS'] = ['DAILY 1 2 1']
    validate_model(sections)
    sections['OPTIONS'] = ['QUALITY TRACE MISSING']
    with pytest.raises(ValueError, match='trace node'):
        validate_model(sections)
