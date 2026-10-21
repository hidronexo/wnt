"""Shared QGIS 3 test application with deterministic lifetime."""

QGIS_APP = None


def get_qgis_app():
    """Initialize QGIS before constructing any Processing GUI controls."""
    from qgis.core import QgsApplication
    from processing.core.Processing import Processing

    global QGIS_APP
    if QGIS_APP is None:
        QGIS_APP = QgsApplication.instance()
        if QGIS_APP is None:
            QGIS_APP = QgsApplication([], True)
            QGIS_APP.initQgis()
        Processing.initialize()
    return QGIS_APP

