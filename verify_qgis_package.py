"""Verify an extracted release ZIP using QGIS Python and an isolated profile."""

import argparse
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


def verify(archive):
    from qgis.core import QgsApplication, QgsProcessingParameterDefinition
    from qgis.PyQt.QtWidgets import QToolButton
    from qgis.PyQt.QtCore import QTranslator
    from processing.core.Processing import Processing
    from processing.gui.AlgorithmDialog import AlgorithmDialog
    with TemporaryDirectory(prefix='wnt-package-check-') as folder:
        root = Path(folder)
        with ZipFile(archive) as zipped:
            if zipped.testzip():
                raise RuntimeError('ZIP CRC check failed')
            for name in zipped.namelist():
                if not (root / name).resolve().is_relative_to(root.resolve()) or not name.startswith('wnt/'):
                    raise RuntimeError('Invalid ZIP member: ' + name)
                if '__pycache__' in name or name.endswith('.pyc'):
                    raise RuntimeError('Generated cache in ZIP: ' + name)
            zipped.extractall(root)
        sys.path.insert(0, str(root))
        app = QgsApplication([], True, str(root / 'profile'))
        app.initQgis()
        Processing.initialize()
        from wnt.wnt_provider import WaterNetworkToolsProvider
        import wnt
        if not Path(wnt.__file__).is_relative_to(root):
            raise RuntimeError('Loaded the checkout instead of the ZIP')
        if 'version=1.6.0' not in (root / 'wnt/metadata.txt').read_text(encoding='utf-8'):
            raise RuntimeError('Incorrect release version')
        provider = WaterNetworkToolsProvider()
        provider.loadAlgorithms()
        if len(provider.algorithms()) != 24:
            raise RuntimeError('Missing Processing algorithms')
        translator = QTranslator()
        if not translator.load(str(root / 'wnt/i18n/wnt_es.qm')):
            raise RuntimeError('Cannot load Spanish translations')
        for spanish in (False, True):
            os.environ['WNT_LOCALE'] = 'es' if spanish else 'en'
            if spanish:
                app.installTranslator(translator)
            algorithm = next(item for item in provider.algorithms() if item.name() == 'network_to_epanet').createInstance()
            algorithm.initAlgorithm()
            expected = 'Exportar modelo EPANET a archivo INP' if spanish else 'Export EPANET model to INP file'
            if algorithm.displayName() != expected:
                raise RuntimeError('Incorrect UI translation: ' + algorithm.displayName())
            dialog = AlgorithmDialog(algorithm)
            dialog.show()
            app.processEvents()
            wrappers = dialog.mainWidget().wrappers
            for category in ('JUNCTIONS', 'RESERVOIRS', 'TANKS', 'PIPES', 'PUMPS', 'VALVES'):
                key = 'INPUT_' + category
                parameter = algorithm.parameterDefinition(key)
                if key not in wrappers or parameter.flags() & QgsProcessingParameterDefinition.FlagAdvanced:
                    raise RuntimeError('Missing main layer selector: ' + key)
                wrapper = wrappers[key]
                widget = getattr(wrapper, 'widget', None) or wrapper.wrappedWidget()
                if not widget.isVisible():
                    raise RuntimeError('Hidden main layer selector: ' + key)
            main = [p.name() for p in algorithm.parameterDefinitions()
                    if not p.flags() & QgsProcessingParameterDefinition.FlagAdvanced]
            if main != list(algorithm.INPUTS.values()) + ['WORKFLOW', 'INPUT_EPANET', 'OUTPUT']:
                raise RuntimeError('Incorrect main parameter order')
            advanced = [p.name() for p in algorithm.parameterDefinitions()
                        if p.flags() & QgsProcessingParameterDefinition.FlagAdvanced]
            if advanced != [name for _, names in algorithm.OPTION_GROUPS for name in names]:
                raise RuntimeError('Incorrect advanced parameter order')
            families = [p.description().split(' — ')[0] for p in algorithm.parameterDefinitions() if ' — ' in p.description()]
            families = [value for index, value in enumerate(families) if index == 0 or value != families[index - 1]]
            expected_families = (['Hidráulica', 'Emisores', 'Energía', 'Calidad', 'Reacciones',
                                  'Estabilidad del cálculo', 'EPANET 2.2', 'Tiempos', 'Informe']
                                 if spanish else ['Hydraulics', 'Emitters', 'Energy', 'Quality', 'Reactions',
                                                  'Calculation stability', 'EPANET 2.2', 'Times', 'Report'])
            if families != expected_families:
                raise RuntimeError('Incorrect translated option families: ' + str(families))
            for key in ('ENERGY_PRICE', 'ENERGY_PATTERN', 'PUMP_EFFICIENCY', 'DEMAND_CHARGE', 'QUALITY_ANALYSIS',
                        'MASS_UNITS', 'TRACE_NODE', 'BULK_ORDER', 'WALL_ORDER', 'TANK_ORDER', 'GLOBAL_BULK',
                        'GLOBAL_WALL', 'LIMITING_CONCENTRATION', 'WALL_CORRELATION', 'DURATION', 'REPORT_STATUS',
                        'HYDRAULICS_MODE', 'HYDRAULICS_FILE', 'UNBALANCED_TRIALS', 'REPORT_NODE_IDS', 'REPORT_FIELDS'):
                if key not in wrappers or not algorithm.parameterDefinition(key).flags() & QgsProcessingParameterDefinition.FlagAdvanced:
                    raise RuntimeError('Missing advanced option: ' + key)
            wrappers['WORKFLOW'].setValue(1)
            first_wrapper = wrappers[advanced[0]]
            first_widget = getattr(first_wrapper, 'widget', None) or first_wrapper.wrappedWidget()
            if not first_widget.isVisible():
                toggle = dialog.findChild(QToolButton, 'collapseButton')
                if toggle is None:
                    raise RuntimeError('Missing advanced-parameter toggle')
                toggle.click()
            app.processEvents()
            for key in advanced:
                wrapper = wrappers[key]
                widget = getattr(wrapper, 'widget', None) or wrapper.wrappedWidget()
                if widget is None or not widget.isVisible():
                    raise RuntimeError('Advanced parameter not visible after expanding: ' + key)
            version22 = ['DEMAND_MODEL', 'MINIMUM_PRESSURE', 'REQUIRED_PRESSURE',
                         'PRESSURE_EXPONENT', 'MAXIMUM_HEAD_ERROR', 'MAXIMUM_FLOW_CHANGE']
            positions = [advanced.index(key) for key in version22]
            if positions != list(range(positions[0], positions[0] + len(version22))):
                raise RuntimeError('EPANET 2.2 parameters are not consecutive')
            dialog.close()
            dialog.deleteLater()
            app.processEvents()
            importer = next(item for item in provider.algorithms() if item.name() == 'network_from_epanet').createInstance()
            importer.initAlgorithm()
            dialog = AlgorithmDialog(importer)
            dialog.show()
            app.processEvents()
            for category in algorithm.INPUTS:
                if 'OUTPUT_' + category not in dialog.mainWidget().wrappers:
                    raise RuntimeError('Missing typed import output: ' + category)
                wrapper = dialog.mainWidget().wrappers['OUTPUT_' + category]
                widget = getattr(wrapper, 'widget', None) or wrapper.wrappedWidget()
                if not widget.isVisible():
                    raise RuntimeError('Hidden typed import output: ' + category)
            dialog.close()
            dialog.deleteLater()
            app.processEvents()
        # Exercise the packaged algorithms, not modules from the checkout.
        from qgis.core import QgsProcessingContext, QgsProcessingFeedback
        from wnt.utils.utils_epanet_model import read_sections
        # Dialogs own their algorithm instances and delete them on close.
        importer = next(item for item in provider.algorithms() if item.name() == 'network_from_epanet').createInstance()
        importer.initAlgorithm()
        algorithm = next(item for item in provider.algorithms() if item.name() == 'network_to_epanet').createInstance()
        algorithm.initAlgorithm()
        source = root / 'six.inp'
        source.write_text(
            '[JUNCTIONS]\nJ 0 1\nK 0\n[RESERVOIRS]\nR 30\n'
            '[TANKS]\nT 0 1 0 5 10\n[PIPES]\nP R J 100 150 120 0 CV\n'
            '[PUMPS]\nU J T POWER 1\n[VALVES]\nV T K 100 TCV 1\n'
            '[COORDINATES]\nR 0 0\nJ 100 0\nT 200 0\nK 300 0\n', encoding='latin-1')
        context = QgsProcessingContext()
        feedback = QgsProcessingFeedback()
        destinations = {'OUTPUT_' + category: 'TEMPORARY_OUTPUT' for category in algorithm.INPUTS}
        imported = importer.processAlgorithm({'INPUT': str(source), 'CRS': 'EPSG:25830', **destinations}, context, feedback)
        sources = {}
        for category in algorithm.INPUTS:
            layer = context.getMapLayer(imported['OUTPUT_' + category])
            if layer.featureCount() != (2 if category == 'JUNCTIONS' else 1):
                raise RuntimeError('Incorrect imported category: ' + category)
            sources['INPUT_' + category] = layer
        output = root / 'six-export.inp'
        algorithm.processAlgorithm({**sources, 'WORKFLOW': 1, 'OUTPUT': str(output)}, context, feedback)
        sections = read_sections(output)
        for category in algorithm.INPUTS:
            if len(sections[category]) != (2 if category == 'JUNCTIONS' else 1):
                raise RuntimeError('Incorrect exported category: ' + category)
        if sections['PIPES'][0].split()[-1] != 'CV':
            raise RuntimeError('Check-valve pipe status lost')
        print('ZIP CRC, version 1.6.0, 24 algorithms, ordered EN/ES dialogs and six-category INP roundtrip with CV: OK')
        provider.unload()
        app.exitQgis()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    verify(parser.parse_args().archive)
