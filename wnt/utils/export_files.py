"""Validation and staged publication for solver project exports."""

import math
import os
from pathlib import Path
import tempfile

from .utils_epanet_model import read_sections, NODE_SECTIONS, LINK_SECTIONS
from .utils_parser import parse_tokens


class ModelReferences:
    """Validate solver project selections against the referenced INP categories."""

    def __init__(self, path):
        self.sections = read_sections(path)
        self.ids = {}
        for namespace in (NODE_SECTIONS, LINK_SECTIONS):
            seen = set()
            for category in namespace:
                identifiers = [parse_tokens(row)[0] for row in self.sections.get(category, []) if parse_tokens(row)]
                if len(identifiers) != len(set(identifiers)) or seen.intersection(identifiers):
                    raise ValueError('Duplicate INP identifiers: ' + category)
                seen.update(identifiers)
                self.ids[category] = set(identifiers)
        self.used = {}

    def require(self, category, identifier, unique=True):
        identifier = str(identifier)
        if identifier not in self.ids[category]:
            raise ValueError(f'{category}: ID not found in the selected INP: {identifier}')
        seen = self.used.setdefault(category, set())
        if unique and identifier in seen:
            raise ValueError(f'{category}: duplicate selection: {identifier}')
        seen.add(identifier)

    def extended_period(self):
        for row in self.sections.get('TIMES', []):
            tokens = parse_tokens(row)
            if tokens and tokens[0].upper() == 'DURATION':
                from .utils_epanet_options import time_hours
                return time_hours(tokens[1]) > 0
        return False


def pressure_value(value):
    """Accept zero constraints, but reject nonfinite or negative pressure."""
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError('Minimum pressure must be finite and nonnegative')
    return value


def catalog_groups(data, columns, encoding='utf-8-sig'):
    """Read a headerless catalog with an exact consumer-specific column count."""
    groups = {}
    for number, raw in enumerate(data.decode(encoding).splitlines(), 1):
        line = raw.partition(';')[0].strip()
        if not line:
            continue
        parts = line.split()
        if '#' in line or len(parts) != columns:
            raise ValueError(f'Catalog line {number}: expected {columns} columns and semicolon comments')
        values = [float(value) for value in parts[1:]]
        if any(not math.isfinite(value) or value <= 0 for value in values):
            raise ValueError(f'Catalog line {number}: values must be finite and positive')
        diameters = groups.setdefault(parts[0], set())
        if values[0] in diameters:
            raise ValueError(f'Catalog line {number}: duplicate diameter')
        diameters.add(values[0])
    if not groups:
        raise ValueError('Catalog is empty')
    return set(groups)


def publish_files(contents, inputs=()):
    """Stage all files and restore replaced destinations if publication fails."""
    paths = [Path(path).resolve() for path in contents]
    protected = [Path(path).resolve() for path in inputs]
    for index, path in enumerate(paths):
        for other in protected + paths[:index]:
            if path == other or path.exists() and other.exists() and path.samefile(other):
                raise ValueError('Input/output paths must be distinct: ' + str(path))
    staged = {}
    backups = {}
    published = []
    try:
        for path, data in zip(paths, contents.values()):
            backups[path] = path.read_bytes() if path.exists() else None
            descriptor, name = tempfile.mkstemp(prefix='.wnt-', dir=path.parent)
            staged[path] = Path(name)
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(data)
        for path, temporary in staged.items():
            os.replace(temporary, path)
            published.append(path)
    except Exception:
        for path in reversed(published):
            if backups[path] is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(backups[path])
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
