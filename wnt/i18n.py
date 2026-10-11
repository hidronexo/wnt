"""Translation helpers for Water Network Tools."""

from pathlib import Path
import os
from qgis.PyQt.QtCore import QCoreApplication, QLocale, QSettings

from .utils import safe_xml

TR_CONTEXT = 'WaterNetworkTools'
_TS_CACHE: dict = {}


def _locale_prefix():
    """Return the active two-letter QGIS locale prefix."""
    locale = os.environ.get('WNT_LOCALE')
    if not locale:
        locale = QSettings().value('locale/userLocale', '') or QLocale.system().name()
    return str(locale)[:2].lower()


def _ts_translations(locale):
    """Return translations from the source catalog as a fallback for missing .qm entries."""
    if locale in _TS_CACHE:
        return _TS_CACHE[locale]

    translations = {}
    ts_path = Path(__file__).resolve().parent / 'i18n' / f'wnt_{locale}.ts'
    if ts_path.is_file():
        try:
            root = safe_xml.parse(ts_path).getroot()
            for message in root.findall('.//message'):
                source = message.findtext('source')
                translation = message.find('translation')
                if source and translation is not None and translation.attrib.get('type') != 'unfinished':
                    text = ''.join(translation.itertext()).strip()
                    if text:
                        translations[source] = text
        except (RuntimeError, SyntaxError, ValueError):
            translations = {}

    _TS_CACHE[locale] = translations
    return translations


def tr(message):
    """Translate plugin text using the shared Water Network Tools context."""
    locale = _locale_prefix()
    if locale in ('', 'en'):
        return message

    translated = QCoreApplication.translate(TR_CONTEXT, message)
    if translated and translated != message:
        return translated
    return _ts_translations(locale).get(message, translated or message)
