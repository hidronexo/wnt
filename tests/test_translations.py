"""Tests for compiled Qt translations."""

import ast
from pathlib import Path
import xml.etree.ElementTree as ET
import pytest

pytest.importorskip("qgis")

from .utilities import get_qgis_app

from qgis.PyQt.QtCore import QSettings, QTranslator

QGIS_APP = get_qgis_app()


pytestmark = pytest.mark.qgis


def test_qgis_translations(monkeypatch):
    """Water Network Tools translations load from the compiled plugin catalog."""
    monkeypatch.delenv('LANG', raising=False)

    plugin_dir = Path(__file__).resolve().parents[1] / 'wnt'
    file_path = plugin_dir / 'i18n' / 'wnt_es.qm'

    if not file_path.is_file():
        pytest.skip(f'Compiled translation file not found: {file_path}')

    translator = QTranslator()

    assert translator.load(str(file_path))

    source_file = plugin_dir / 'processes' / 'wnt_validate.py'
    tree = ast.parse(source_file.read_text(encoding='utf-8-sig'))
    help_source = next(
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'tr'
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and 'Analyses the network graph' in node.args[0].value
    )

    translated_help = translator.translate('WaterNetworkTools', help_source)

    assert translated_help.startswith('<p>Analiza el grafo de la red')
    assert '<code>problems</code>' in translated_help


def test_translation_catalog_matches_translatable_sources():
    """Every current tr() string is present in the Spanish catalog."""
    plugin_dir = Path(__file__).resolve().parents[1] / 'wnt'
    catalog = ET.parse(plugin_dir / 'i18n' / 'wnt_es.ts')
    catalog_sources = {
        source.text.replace('\r\n', '\n').replace('\r', '\n')
        for source in catalog.findall('.//source')
        if source.text
    }
    code_sources = set()

    for source_file in plugin_dir.rglob('*.py'):
        tree = ast.parse(source_file.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue

            function = node.func
            is_translation_call = (
                isinstance(function, ast.Attribute) and function.attr == 'tr'
            ) or (
                isinstance(function, ast.Name) and function.id == 'tr'
            )
            if not is_translation_call:
                continue

            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                code_sources.add(
                    argument.value.replace('\r\n', '\n').replace('\r', '\n')
                )

    assert code_sources <= catalog_sources


def test_spanish_translation_catalog_has_no_unfinished_entries():
    """Spanish catalog entries must be usable by QGIS, not left unfinished."""
    plugin_dir = Path(__file__).resolve().parents[1] / 'wnt'
    catalog = ET.parse(plugin_dir / 'i18n' / 'wnt_es.ts')
    unfinished = catalog.findall('.//translation[@type="unfinished"]')
    empty = [
        translation for translation in catalog.findall('.//translation')
        if not ''.join(translation.itertext()).strip()
    ]

    assert unfinished == []
    assert empty == []



def test_spanish_catalog_has_no_mojibake_markers():
    """Spanish translations should keep UTF-8 accents readable."""
    plugin_dir = Path(__file__).resolve().parents[1] / 'wnt'
    text = (plugin_dir / 'i18n' / 'wnt_es.ts').read_text(encoding='utf-8')

    for marker in ('\u00c3', '\u00c2', '\ufffd', '\u00e2', '\u00c6', '\u0192', '\u2122'):
        assert marker not in text


def _assert_display_name_uses_tr(plugin_dir, source_path, source):
    tree = ast.parse((plugin_dir / source_path).read_text(encoding='utf-8-sig'))
    display_name_functions = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == 'displayName'
    ]
    returns = [
        return_node.value
        for function in display_name_functions
        for return_node in ast.walk(function)
        if isinstance(return_node, ast.Return)
    ]

    assert any(
        isinstance(return_value, ast.Call)
        and isinstance(return_value.func, ast.Attribute)
        and return_value.func.attr == 'tr'
        and return_value.args
        and isinstance(return_value.args[0], ast.Constant)
        and return_value.args[0].value == source
        for return_value in returns
    )


def test_processing_toolbox_entries_use_spanish_catalog():
    """Processing toolbox entries with compiled translations stay valid."""
    plugin_dir = Path(__file__).resolve().parents[1] / 'wnt'
    file_path = plugin_dir / 'i18n' / 'wnt_es.qm'
    translator = QTranslator()

    if not file_path.is_file():
        pytest.skip(f'Compiled translation file not found: {file_path}')

    assert translator.load(str(file_path))
    expected_names = {
        'processes/wnt_assign_demand.py': ('Assign demand', 'Asignar demanda'),
        'processes/wnt_config_toolkit.py': (
            'Configure EPANET lib',
            'Configurar biblioteca EPANET',
        ),
        'processes/wnt_connect_by_distance.py': (
            'Connect by distance',
            'Conectar por distancia',
        ),
        'processes/wnt_demand_to_epanet_scenario.py': (
            'Demand to epanet scenario file (.scn)',
            'Exportar demandas a escenario de EPANET (.scn)',
        ),
        'processes/wnt_network_from_epanet.py': (
            'Network from EPANET file',
            'Importar red desde EPANET',
        ),
        'processes/wnt_network_from_landxml.py': (
            'Network from LandXML file',
            'Importar red desde LandXML',
        ),
        'processes/wnt_network_from_lines.py': (
            'Network from lines',
            'Crear red a partir de líneas',
        ),
        'processes/wnt_network_to_graph.py': (
            'Network to graph file',
            'Exportar red a grafo',
        ),
        'processes/wnt_network_to_ppno.py': (
            'Network to pressure pipe optimization data file (.ext)',
            'Exportar red a PPNO (.ext)',
        ),
        'processes/wnt_pipe_properties_to_epanet_scenario.py': (
            'Pipe properties to EPANET scenario file (.scn)',
            'Exportar propiedades de tuberías a escenario de EPANET (.scn)',
        ),
        'processes/wnt_update_assignment.py': (
            'Update assignment',
            'Actualizar asignaci\u00f3n',
        ),
        'processes/wnt_validate.py': ('Validate', 'Validar'),
        'processes/wnt_network_to_epanet.py': (
            'Network to epanet file (.inp)',
            'Exportar red a EPANET (.inp)',
        ),
        'processes/wnt_network_to_pipesizing.py': (
            'Network to pipesizing data file (.pro)',
            'Exportar red a PipeSizing (.pro)',
        ),
        'processes/wnt_network_to_xml.py': ('Network to XML', 'Exportar red a XML'),
        'processes/wnt_hydrant_pairs.py': ('Hydrant pairs', 'Pares de hidrantes'),
        'processes/wnt_classify.py': ('Classify', 'Clasificar'),
        'processes/wnt_node_degrees.py': ('Node degrees', 'Calcular grados de los nodos'),
        'processes/wnt_network_from_xml.py': ('Network from XML', 'Importar red desde XML'),
        'processes/wnt_results_from_epanet.py': (
            'Results from EPANET',
            'Importar resultados de EPANET',
        ),
        'processes/wnt_merge_networks.py': ('Merge networks', 'Fusionar redes'),
        'processes/wnt_elevation_from_tin.py': (
            'Node elevation from TIN (LandXML)',
            'Asignar cotas a nodos desde TIN (LandXML)',
        ),
        'processes/wnt_elevation_from_raster.py': (
            'Node elevation from DEM',
            'Asignar cotas a nodos desde MDE',
        ),
        'processes/wnt_split_lines_at_points.py': (
            'Split lines at points',
            'Dividir líneas en puntos',
        ),
    }
    expected_toolbox_text = {
        'Build': 'Construir',
        'Demand': 'Demanda',
        'Export': 'Exportar',
        'Fire': 'Incendio',
        'Graph': 'Grafo',
        'Import': 'Importar',
        'Modify': 'Modificar',
        'Network names': 'Nombres de red',
        'Links': 'Links de salida',
        'Create new output layer': 'Crear capa de salida nueva',
        'Update input layer': 'Actualizar capa de entrada',
    }

    for source, translation in expected_toolbox_text.items():
        assert translator.translate('WaterNetworkTools', source) == translation

    for source_path, (source, translation) in expected_names.items():
        assert translator.translate('WaterNetworkTools', source) == translation
        _assert_display_name_uses_tr(plugin_dir, source_path, source)

    network_from_xml = ast.parse(
        (plugin_dir / 'processes' / 'wnt_network_from_xml.py').read_text(
            encoding='utf-8-sig'
        )
    )
    help_source = next(
        node.args[0].value
        for node in ast.walk(network_from_xml)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'tr'
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and 'Imports network node and link layers from XML' in node.args[0].value
    )
    translated_help = translator.translate('WaterNetworkTools', help_source)

    assert translated_help.startswith('<p>Importa capas de nodos y links')
    assert 'Imports network node and link layers from XML' not in translated_help


def test_processing_toolbox_entries_use_spanish_ts_fallback(monkeypatch):
    """All current toolbox process names are translated in Spanish at runtime."""
    plugin_dir = Path(__file__).resolve().parents[1] / 'wnt'
    expected_names = {
        'processes/wnt_assign_demand.py': ('Assign demand', 'Asignar demanda'),
        'processes/wnt_config_toolkit.py': (
            'Configure EPANET lib',
            'Configurar biblioteca EPANET',
        ),
        'processes/wnt_connect_by_distance.py': (
            'Connect by distance',
            'Conectar por distancia',
        ),
        'processes/wnt_demand_to_epanet_scenario.py': (
            'Demand to epanet scenario file (.scn)',
            'Exportar demandas a escenario de EPANET (.scn)',
        ),
        'processes/wnt_network_from_epanet.py': (
            'Network from EPANET file',
            'Importar red desde EPANET',
        ),
        'processes/wnt_network_from_landxml.py': (
            'Network from LandXML file',
            'Importar red desde LandXML',
        ),
        'processes/wnt_network_from_lines.py': (
            'Network from lines',
            'Crear red a partir de líneas',
        ),
        'processes/wnt_network_to_graph.py': (
            'Network to graph file',
            'Exportar red a grafo',
        ),
        'processes/wnt_network_to_ppno.py': (
            'Network to pressure pipe optimization data file (.ext)',
            'Exportar red a PPNO (.ext)',
        ),
        'processes/wnt_pipe_properties_to_epanet_scenario.py': (
            'Pipe properties to EPANET scenario file (.scn)',
            'Exportar propiedades de tuberías a escenario de EPANET (.scn)',
        ),
        'processes/wnt_update_assignment.py': (
            'Update assignment',
            'Actualizar asignación',
        ),
        'processes/wnt_validate.py': ('Validate', 'Validar'),
        'processes/wnt_network_to_epanet.py': (
            'Network to epanet file (.inp)',
            'Exportar red a EPANET (.inp)',
        ),
        'processes/wnt_network_to_pipesizing.py': (
            'Network to pipesizing data file (.pro)',
            'Exportar red a PipeSizing (.pro)',
        ),
        'processes/wnt_network_to_xml.py': ('Network to XML', 'Exportar red a XML'),
        'processes/wnt_hydrant_pairs.py': ('Hydrant pairs', 'Pares de hidrantes'),
        'processes/wnt_classify.py': ('Classify', 'Clasificar'),
        'processes/wnt_node_degrees.py': ('Node degrees', 'Calcular grados de los nodos'),
        'processes/wnt_network_from_xml.py': ('Network from XML', 'Importar red desde XML'),
        'processes/wnt_results_from_epanet.py': (
            'Results from EPANET',
            'Importar resultados de EPANET',
        ),
        'processes/wnt_merge_networks.py': ('Merge networks', 'Fusionar redes'),
        'processes/wnt_elevation_from_tin.py': (
            'Node elevation from TIN (LandXML)',
            'Asignar cotas a nodos desde TIN (LandXML)',
        ),
        'processes/wnt_elevation_from_raster.py': (
            'Node elevation from DEM',
            'Asignar cotas a nodos desde MDE',
        ),
        'processes/wnt_split_lines_at_points.py': (
            'Split lines at points',
            'Dividir líneas en puntos',
        ),
    }

    monkeypatch.setenv('WNT_LOCALE', 'es')
    settings = QSettings()
    previous_locale = settings.value('locale/userLocale', '')
    settings.setValue('locale/userLocale', 'es')
    from wnt.i18n import _TS_CACHE, tr

    _TS_CACHE.clear()

    try:
        for source_path, (source, translation) in expected_names.items():
            assert tr(source) == translation
            _assert_display_name_uses_tr(plugin_dir, source_path, source)
    finally:
        settings.setValue('locale/userLocale', previous_locale)
        _TS_CACHE.clear()
