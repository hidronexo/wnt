"""Verify an extracted release ZIP using QGIS Python and an isolated profile."""

import argparse
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


def verify(archive):
    from qgis.core import QgsApplication, QgsProcessingParameterDefinition
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
            wrappers = dialog.mainWidget().wrappers
            for category in ('JUNCTIONS', 'RESERVOIRS', 'TANKS', 'PIPES', 'PUMPS', 'VALVES'):
                key = 'INPUT_' + category
                parameter = algorithm.parameterDefinition(key)
                if key not in wrappers or parameter.flags() & QgsProcessingParameterDefinition.FlagAdvanced:
                    raise RuntimeError('Missing main layer selector: ' + key)
            for key in ('ENERGY_PRICE', 'ENERGY_PATTERN', 'PUMP_EFFICIENCY', 'DEMAND_CHARGE', 'QUALITY_ANALYSIS',
                        'MASS_UNITS', 'TRACE_NODE', 'BULK_ORDER', 'WALL_ORDER', 'TANK_ORDER', 'GLOBAL_BULK',
                        'GLOBAL_WALL', 'LIMITING_CONCENTRATION', 'WALL_CORRELATION', 'DURATION', 'REPORT_STATUS'):
                if key not in wrappers or not algorithm.parameterDefinition(key).flags() & QgsProcessingParameterDefinition.FlagAdvanced:
                    raise RuntimeError('Missing advanced option: ' + key)
            wrappers['WORKFLOW'].setValue(1)
            app.processEvents()
            dialog.close()
            dialog.deleteLater()
            app.processEvents()
        print('ZIP CRC, layout, version 1.6.0, 24 algorithms, six selectors and English/Spanish forms: OK')
        provider.unload()
        app.exitQgis()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    verify(parser.parse_args().archive)
