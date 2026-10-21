"""Run the six-category adapters with real QGIS memory layers and sinks."""

import pytest

pytest.importorskip('qgis')
from qgis.core import QgsFeature, QgsGeometry, QgsProcessingContext, QgsProcessingFeedback, QgsVectorLayer
from .utilities import get_qgis_app
from wnt.processes.wnt_node_degrees import NodeDegreesAlgorithm
from wnt.processes.wnt_classify import ClassifyAlgorithm
from wnt.processes.wnt_network_from_lines import NetworkFromLinesAlgorithm
from wnt.processes.wnt_merge_networks import MergeNetworksAlgorithm
from wnt.processes.wnt_network_to_xml import NetworkToXmlAlgorithm
from wnt.processes.wnt_network_from_xml import NetworkFromXmlAlgorithm

QGIS_APP = get_qgis_app()
pytestmark = pytest.mark.qgis


def layer(point, records):
    uri = ('Point' if point else 'LineString') + '?crs=EPSG:25830&field=id:string'
    if not point:
        uri += '&field=start:string&field=end:string&field=type:string'
    result = QgsVectorLayer(uri, 'model', 'memory')
    for index, values in enumerate(records):
        feature = QgsFeature(result.fields())
        feature.setAttributes(values)
        feature.setGeometry(QgsGeometry.fromWkt(
            f'POINT ({index} 0)' if point else f'LINESTRING ({index} 0, {index + 1} 0)'))
        assert result.dataProvider().addFeatures([feature])[0]
    return result


def test_degrees_include_pumps_valves_reservoirs_and_tanks():
    algorithm = NodeDegreesAlgorithm()
    algorithm.initAlgorithm()
    context = QgsProcessingContext()
    inputs = {
        'INPUT_JUNCTIONS': layer(True, [['J']]),
        'INPUT_RESERVOIRS': layer(True, [['R']]),
        'INPUT_TANKS': layer(True, [['T']]),
        'INPUT_PIPES': layer(False, [['P', 'R', 'J', 'PIPE']]),
        'INPUT_PUMPS': layer(False, [['U', 'J', 'T', 'PUMP']]),
        'INPUT_VALVES': layer(False, [['V', 'T', 'J', 'PRV']]),
        'OUTPUT_MODE': 0,
    }
    result = algorithm.processAlgorithm(inputs, context, QgsProcessingFeedback())
    assert set(result) == {'OUTPUT_JUNCTIONS', 'OUTPUT_RESERVOIRS', 'OUTPUT_TANKS'}
    for category, expected in [('JUNCTIONS', 3), ('RESERVOIRS', 1), ('TANKS', 2)]:
        output = context.getMapLayer(result['OUTPUT_' + category])
        assert next(output.getFeatures())['degree'] == expected


def test_classification_preserves_all_link_categories():
    algorithm = ClassifyAlgorithm()
    algorithm.initAlgorithm()
    context = QgsProcessingContext()
    inputs = {'INPUT_' + category: layer(False, [[identifier, start, end, kind]])
              for category, identifier, start, end, kind in [
                  ('PIPES', 'P', 'R', 'J', 'PIPE'), ('PUMPS', 'U', 'J', 'T', 'PUMP'),
                  ('VALVES', 'V', 'T', 'R', 'PRV')]}
    result = algorithm.processAlgorithm(inputs, context, QgsProcessingFeedback())
    assert len(result) == 3
    for category in ('PIPES', 'PUMPS', 'VALVES'):
        output = context.getMapLayer(result['OUTPUT_' + category])
        assert output.featureCount() == 1
        assert next(output.getFeatures())['topology'] == 'mesh'


def test_builder_categorizes_cv_pump_and_valve_without_generic_outputs():
    algorithm = NetworkFromLinesAlgorithm()
    algorithm.initAlgorithm()
    context = QgsProcessingContext()
    source = layer(False, [['P', 'A', 'B', 'CVPIPE'], ['U', 'B', 'C', 'PUMP'], ['V', 'C', 'D', 'PRV']])
    parameters = {algorithm.INPUT: source, algorithm.CRS: 'EPSG:25830',
                  algorithm.LINK_TYPE_FIELD: 'type'}
    result = algorithm.processAlgorithm(parameters, context, QgsProcessingFeedback())
    assert set(result) == {'OUTPUT_JUNCTIONS', 'OUTPUT_PIPES', 'OUTPUT_PUMPS', 'OUTPUT_VALVES'}
    pipe = next(context.getMapLayer(result['OUTPUT_PIPES']).getFeatures())
    assert pipe['type'] == 'PIPE'
    assert pipe['status'] == 'CV'
    assert context.getMapLayer(result['OUTPUT_PUMPS']).featureCount() == 1
    assert context.getMapLayer(result['OUTPUT_VALVES']).featureCount() == 1


def test_merge_keeps_reservoir_and_junction_at_same_position_and_remaps_ids():
    algorithm = MergeNetworksAlgorithm()
    algorithm.initAlgorithm()
    context = QgsProcessingContext()
    parameters = {'CRS': 'EPSG:25830', 'TOLERANCE': 0.01,
                  'INPUT_JUNCTIONS_1': layer(True, [['A'], ['B']]),
                  'INPUT_PIPES_1': layer(False, [['P', 'A', 'B', 'PIPE']]),
                  'INPUT_RESERVOIRS_2': layer(True, [['A']]),
                  'INPUT_TANKS_2': layer(True, [['T']]),
                  'INPUT_PUMPS_2': layer(False, [['P', 'A', 'T', 'PUMP']])}
    result = algorithm.processAlgorithm(parameters, context, QgsProcessingFeedback())
    reservoir = next(context.getMapLayer(result['OUTPUT_RESERVOIRS']).getFeatures())
    pump = next(context.getMapLayer(result['OUTPUT_PUMPS']).getFeatures())
    assert reservoir['id'] != 'A'
    assert pump['id'] != 'P'
    assert pump['start'] == reservoir['id']
    assert pump['end'] == 'T'
    assert context.getMapLayer(result['OUTPUT_JUNCTIONS']).featureCount() == 2


def test_typed_xml_preserves_cv_direction_and_categories(tmp_path):
    from qgis.core import QgsField
    from qgis.PyQt.QtCore import QMetaType
    source = layer(False, [['P', 'R', 'J', 'PIPE']])
    source.dataProvider().addAttributes([QgsField('status', QMetaType.QString), QgsField('diameter', QMetaType.Double)])
    source.updateFields()
    feature = next(source.getFeatures())
    source.dataProvider().changeAttributeValues({feature.id(): {4: 'CV', 5: 150}})
    exporter = NetworkToXmlAlgorithm()
    exporter.initAlgorithm()
    context = QgsProcessingContext()
    output = str(tmp_path / 'network.xml')
    exporter.processAlgorithm({'INPUT_JUNCTIONS': layer(True, [['J']]),
                               'INPUT_RESERVOIRS': layer(True, [['R']]),
                               'INPUT_PIPES': source, 'OUTPUT': output}, context, QgsProcessingFeedback())
    importer = NetworkFromXmlAlgorithm()
    importer.initAlgorithm()
    result = importer.processAlgorithm({'INPUT': output}, context, QgsProcessingFeedback())
    assert len(result) == 6
    pipe = next(context.getMapLayer(result['OUTPUT_PIPES']).getFeatures())
    assert (pipe['start'], pipe['end'], pipe['status'], pipe['diameter']) == ('R', 'J', 'CV', 150)
    assert context.getMapLayer(result['OUTPUT_RESERVOIRS']).featureCount() == 1


def test_results_keep_category_and_time_even_when_node_and_link_ids_match(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from wnt.processes.wnt_results_from_epanet import ResultsFromEpanetAlgorithm
    path = tmp_path / 'model.inp'
    path.write_text('[JUNCTIONS]\nX 0\n[RESERVOIRS]\nR 10\n[TANKS]\nT 0 1 0 2 1\n[PIPES]\nX R X 10 100 120\n[PUMPS]\nU X T POWER 1\n[VALVES]\nV T X 100 TCV 0\n', encoding='latin-1')
    rows = SimpleNamespace(node_rows=[['0:00', key, 1, 2, 3] for key in ('X', 'R', 'T')],
                           link_rows=[['0:00', key, 1, 2, 3, 'OPEN', 1, 0] for key in ('X', 'U', 'V')])
    toolkit = SimpleNamespace(constants=SimpleNamespace(max_label_len=31), read_hydraulic_results=lambda _path: rows)
    monkeypatch.setattr('wnt.processes.wnt_results_from_epanet.EpanetToolkit.from_config', lambda: toolkit)
    algorithm = ResultsFromEpanetAlgorithm()
    algorithm.initAlgorithm()
    context = QgsProcessingContext()
    result = algorithm.processAlgorithm({'INPUT': str(path), 'RESULT_TYPE': 0}, context, QgsProcessingFeedback())
    assert len(result) == 6
    for category, identifier in [('JUNCTIONS', 'X'), ('RESERVOIRS', 'R'), ('TANKS', 'T'), ('PIPES', 'X'), ('PUMPS', 'U'), ('VALVES', 'V')]:
        feature = next(context.getMapLayer(result['OUTPUT_' + category]).getFeatures())
        assert (feature['id'], feature['time']) == (identifier, '0:00')


def test_inp_roundtrip_preserves_multiple_demands_and_cv(tmp_path):
    from wnt.processes.wnt_network_from_epanet import NetworkFromEpanetAlgorithm
    from wnt.processes.wnt_network_to_epanet import NetworkToEpanetAlgorithm
    from wnt.utils.utils_epanet_model import read_sections, PHYSICAL_SECTIONS
    source = tmp_path / 'source.inp'
    source.write_text('[JUNCTIONS]\nJ 10 1 DAILY\n[RESERVOIRS]\nR 30\n[PIPES]\nP R J 100 150 120 0 CV\n[DEMANDS]\nJ 1 DAILY ; Domestic\nJ 2 DAILY ; Industry\n[PATTERNS]\nDAILY 1 2\n[COORDINATES]\nJ 100 0\nR 0 0\n', encoding='latin-1')
    importer = NetworkFromEpanetAlgorithm()
    importer.initAlgorithm()
    context = QgsProcessingContext()
    destinations = {'OUTPUT_' + category: 'TEMPORARY_OUTPUT' for category in PHYSICAL_SECTIONS}
    imported = importer.processAlgorithm({'INPUT': str(source), 'CRS': 'EPSG:25830', **destinations}, context, QgsProcessingFeedback())
    sources = {'INPUT_' + category: context.getMapLayer(imported['OUTPUT_' + category]) for category in PHYSICAL_SECTIONS}
    exporter = NetworkToEpanetAlgorithm()
    exporter.initAlgorithm()
    output = tmp_path / 'roundtrip.inp'
    exporter.processAlgorithm({**sources, 'WORKFLOW': 1, 'INPUT_DEFINITIONS': str(source), 'OUTPUT': str(output)}, context, QgsProcessingFeedback())
    sections = read_sections(output)
    assert sections['DEMANDS'] == ['J 1 DAILY ; Domestic', 'J 2 DAILY ; Industry']
    assert sections['PIPES'][0].split()[:3] == ['P', 'R', 'J']
    assert sections['PIPES'][0].split()[-1] == 'CV'
    # A sparse edit must not reset omitted hydraulic properties to defaults.
    from qgis.core import QgsField
    from qgis.PyQt.QtCore import QMetaType
    junctions = layer(True, [['J']])
    junctions.dataProvider().addAttributes([QgsField('elevation', QMetaType.Double)])
    junctions.updateFields()
    junctions.dataProvider().changeAttributeValues({next(junctions.getFeatures()).id(): {1: 12}})
    edited = tmp_path / 'edited.inp'
    exporter.processAlgorithm({'INPUT_JUNCTIONS': junctions, 'WORKFLOW': 0,
                               'INPUT_EPANET': str(source), 'OUTPUT': str(edited)}, context, QgsProcessingFeedback())
    updated = read_sections(edited)
    assert updated['DEMANDS'] == sections['DEMANDS']
    assert updated['JUNCTIONS'][0].split()[1:] == ['12.0', '1', 'DAILY']
    assert updated['PIPES'][0].split()[-1] == 'CV'


def test_legacy_two_layer_adapter_preserves_categories_and_cv(tmp_path):
    import json
    from wnt.processes.wnt_network_to_epanet import NetworkToEpanetAlgorithm
    from wnt.utils.utils_epanet_model import read_sections
    nodes = QgsVectorLayer('Point?crs=EPSG:25830&field=id:string&field=type:string&field=elevation:double&field=epanet:string', 'legacy', 'memory')
    for identifier, kind, elevation, x in [('J', 'JUNCTION', 0, 100), ('R', 'RESERVOIR', 30, 0)]:
        feature = QgsFeature(nodes.fields())
        feature.setAttributes([identifier, kind, elevation, '{}'])
        feature.setGeometry(QgsGeometry.fromWkt(f'POINT ({x} 0)'))
        nodes.dataProvider().addFeatures([feature])
    pipes = QgsVectorLayer('LineString?crs=EPSG:25830&field=id:string&field=start:string&field=end:string&field=type:string&field=epanet:string', 'legacy', 'memory')
    feature = QgsFeature(pipes.fields())
    feature.setAttributes(['P', 'R', 'J', 'CVPIPE', json.dumps(dict(length=100, diameter=100, roughness=120))])
    feature.setGeometry(QgsGeometry.fromWkt('LINESTRING (0 0, 100 0)'))
    pipes.dataProvider().addFeatures([feature])
    algorithm = NetworkToEpanetAlgorithm()
    algorithm.initAlgorithm()
    context = QgsProcessingContext()
    output = tmp_path / 'legacy.inp'
    algorithm.processAlgorithm({'INPUT_NODES': nodes, 'INPUT_LINES': pipes, 'WORKFLOW': 1,
                                'OUTPUT': str(output)}, context, QgsProcessingFeedback())
    sections = read_sections(output)
    assert len(sections['RESERVOIRS']) == len(sections['JUNCTIONS']) == 1
    assert sections['PIPES'][0].split()[-1] == 'CV'


def test_inp_import_without_coordinates_keeps_typed_objects(tmp_path):
    from wnt.processes.wnt_network_from_epanet import NetworkFromEpanetAlgorithm
    from wnt.utils.utils_epanet_model import PHYSICAL_SECTIONS
    source = tmp_path / 'no_coords.inp'
    source.write_text('[JUNCTIONS]\nJ 0\n[RESERVOIRS]\nR 30\n[PIPES]\nP R J 100 100 120\n', encoding='latin-1')
    algorithm = NetworkFromEpanetAlgorithm()
    algorithm.initAlgorithm()
    context = QgsProcessingContext()
    destinations = {'OUTPUT_' + category: 'TEMPORARY_OUTPUT' for category in PHYSICAL_SECTIONS}
    result = algorithm.processAlgorithm({'INPUT': str(source), 'CRS': 'EPSG:25830', **destinations}, context, QgsProcessingFeedback())
    assert context.getMapLayer(result['OUTPUT_JUNCTIONS']).featureCount() == 1
    assert context.getMapLayer(result['OUTPUT_PIPES']).featureCount() == 1
