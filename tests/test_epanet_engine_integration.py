"""Opt-in acceptance against an external EPANET library; never bundle it."""

import os
import pytest
from wnt.utils.utils_epanet_api import EpanetToolkit
from wnt.utils.utils_epanet_model import scratch_sections, write_sections
from wnt.utils.utils_epanet_options import analysis_sections
from wnt.utils.model_validation import validate_model


@pytest.mark.skipif(not os.environ.get('WNT_EPANET_LIBRARY'), reason='Set WNT_EPANET_LIBRARY for native engine acceptance')
@pytest.mark.parametrize('quality', [0, 1, 2, 3])
def test_analysis_families_are_accepted_by_epanet(tmp_path, quality):
    toolkit = EpanetToolkit.from_library_path(os.environ['WNT_EPANET_LIBRARY'])
    options = dict(version='2.2', flow_units='LPS', headloss='H-W', demand_model='DDA',
                   default_pattern='', demand_multiplier=1, emitter_exponent=0.5,
                   viscosity=1, diffusivity=1, specific_gravity=1, trials=40, accuracy=0.001,
                   unbalanced='STOP', minimum_pressure=0, required_pressure=15, pressure_exponent=0.5)
    sections = scratch_sections(options)
    sections['JUNCTIONS'] = ['J 0 1']
    sections['RESERVOIRS'] = ['R 30']
    sections['PIPES'] = ['P R J 1000 100 120 0 CV']
    sections['COORDINATES'] = ['R 0 0', 'J 1000 0']
    for name, rows in analysis_sections(dict(QUALITY_ANALYSIS=quality, TRACE_NODE='R',
                                            DURATION='1:00', ENERGY_PRICE=0.2,
                                            DEMAND_CHARGE=1, GLOBAL_BULK=-0.1), '2.2').items():
        sections.setdefault(name, []).extend(rows)
    validate_model(sections)
    path = tmp_path / 'model.inp'
    write_sections(path, sections)
    hydraulic = toolkit.read_hydraulic_results(path)
    assert hydraulic.node_count == 2
    assert hydraulic.link_count == 1
    if quality:
        result = toolkit.read_quality_results(path)
        assert result.node_rows
