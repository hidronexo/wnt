"""Validate serialized physical properties and model references before publishing."""

import math
from .utils_epanet_model import NODE_SECTIONS, LINK_SECTIONS
from .utils_parser import parse_tokens


def validate_model(sections):
    rows = {name: [parse_tokens(line) for line in lines if parse_tokens(line)]
            for name, lines in sections.items()}
    ids = {name: {row[0] for row in rows.get(name, [])}
           for name in NODE_SECTIONS + LINK_SECTIONS + ('PATTERNS', 'CURVES')}
    nodes = set().union(*(ids[name] for name in NODE_SECTIONS))

    def number(value, minimum=None, positive=False):
        result = float(value)
        if not math.isfinite(result) or (minimum is not None and result < minimum) or (positive and result <= 0):
            raise ValueError('Invalid model number: ' + str(value))
        return result

    def reference(value, category):
        if value and value != '*' and value not in ids[category]:
            raise ValueError(f'Undefined {category} reference: {value}')

    for category in NODE_SECTIONS + LINK_SECTIONS:
        for row in rows.get(category, []):
            if not row[0] or len(row[0]) > 31:
                raise ValueError('Invalid EPANET identifier: ' + row[0])
            if category == 'JUNCTIONS':
                number(row[1])
                if len(row) > 2:
                    number(row[2])
                if len(row) > 3:
                    reference(row[3], 'PATTERNS')
            elif category == 'RESERVOIRS':
                number(row[1])
                if len(row) > 2:
                    reference(row[2], 'PATTERNS')
            elif category == 'TANKS':
                number(row[1])
                initial, low, high = (number(value, 0) for value in row[2:5])
                if not low <= initial <= high or high <= low:
                    raise ValueError('Invalid tank levels: ' + row[0])
                number(row[5], positive=True)
                if len(row) > 6:
                    number(row[6], 0)
                if len(row) > 7:
                    reference(row[7], 'CURVES')
            elif category == 'PIPES':
                for value in row[3:6]:
                    number(value, positive=True)
                if len(row) > 6:
                    number(row[6], 0)
            elif category == 'PUMPS':
                for key, value in zip(row[3::2], row[4::2]):
                    if key.upper() == 'HEAD':
                        reference(value, 'CURVES')
                    elif key.upper() == 'PATTERN':
                        reference(value, 'PATTERNS')
                    elif key.upper() in ('POWER', 'SPEED'):
                        number(value, 0, positive=key.upper() == 'POWER')
            elif category == 'VALVES':
                number(row[3], positive=True)
                subtype = row[4].upper()
                if subtype not in ('PRV', 'PSV', 'PBV', 'FCV', 'TCV', 'GPV'):
                    raise ValueError('Invalid valve subtype: ' + subtype)
                if subtype == 'GPV':
                    reference(row[5], 'CURVES')
                else:
                    number(row[5], 0)
                if len(row) > 6:
                    number(row[6], 0)
    for row in rows.get('OPTIONS', []):
        if row[0].upper() == 'PATTERN' and len(row) > 1:
            reference(row[1], 'PATTERNS')
        if len(row) > 2 and row[0].upper() == 'QUALITY' and row[1].upper() == 'TRACE' and row[2] not in nodes:
            raise ValueError('Undefined trace node: ' + row[2])
    for row in rows.get('DEMANDS', []):
        if row[0] not in ids['JUNCTIONS']:
            raise ValueError('Undefined demand junction: ' + row[0])
        number(row[1])
        if len(row) > 2:
            reference(row[2], 'PATTERNS')
    for row in rows.get('ENERGY', []):
        offset = 2 if row[0].upper() == 'PUMP' else 1
        if row[0].upper() == 'PUMP' and row[1] not in ids['PUMPS']:
            raise ValueError('Undefined energy pump: ' + row[1])
        if row[offset].upper() == 'PATTERN':
            reference(row[offset + 1], 'PATTERNS')
        if row[0].upper() == 'PUMP' and row[offset].upper() == 'EFFIC':
            reference(row[offset + 1], 'CURVES')
