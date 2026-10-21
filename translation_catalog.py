"""Synchronize and validate Qt catalogs without requiring QGIS.

Run --update after editing plugin strings, review unfinished entries, then --check.
"""
import argparse
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
CONTEXT = 'WaterNetworkTools'


def sources():
    result = set()
    from wnt.utils.utils_epanet_options import OPTION_SPECS
    result.update(spec[1] for spec in OPTION_SPECS)
    result.update(choice for _, _, kind, _, choices, _, _ in OPTION_SPECS
                  if kind == 'enum' for choice in choices if not choice.isupper())
    for path in (ROOT / 'wnt').rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            name = getattr(node.func, 'attr', getattr(node.func, 'id', ''))
            value = node.args[0]
            if name == 'tr' and isinstance(value, ast.Constant) and isinstance(value.value, str):
                result.add(value.value)
    return result


def synchronize(path, current, update=False):
    tree = ET.parse(path)
    root = tree.getroot()
    context = next((c for c in root.findall('context') if c.findtext('name') == CONTEXT), None)
    if context is None:
        raise ValueError(f'{path}: missing {CONTEXT} context')
    entries = {}
    errors = []
    for message in context.findall('message'):
        source = message.findtext('source')
        if source in entries:
            errors.append(f'duplicate: {source!r}')
        entries[source] = message
    for source in sorted(current - entries.keys()):
        if update:
            message = ET.SubElement(context, 'message')
            ET.SubElement(message, 'source').text = source
            ET.SubElement(message, 'translation', type='unfinished')
        else:
            errors.append(f'missing: {source!r}')
    for source, message in entries.items():
        if source in current:
            translation = message.find('translation')
            if (translation is None or translation.get('type') in ('unfinished', 'vanished', 'obsolete')
                    or not ''.join(translation.itertext()).strip()):
                errors.append(f'untranslated: {source!r}')
    if update:
        ET.indent(tree, space='    ')
        tree.write(path, encoding='utf-8', xml_declaration=True)
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--update', action='store_true')
    mode.add_argument('--check', action='store_true')
    args = parser.parse_args()
    errors = []
    for path in sorted((ROOT / 'wnt/i18n').glob('wnt_*.ts')):
        errors.extend(f'{path.name}: {e}' for e in synchronize(path, sources(), args.update))
    print('\n'.join(errors) if errors else 'Translation catalogs synchronized.')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
