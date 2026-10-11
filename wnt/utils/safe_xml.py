"""Safe XML parsing helpers with no mandatory QGIS runtime dependency."""

from pathlib import Path
import xml.etree.ElementTree as standard_et  # nosec B405


FORBIDDEN_DECLARATIONS = (b"<!DOCTYPE", b"<!ENTITY")


def _stdlib_parse(source):
    """Parse XML with the standard library after rejecting entity declarations."""
    if hasattr(source, "read"):
        data = source.read()
    else:
        data = Path(source).read_bytes()
    if isinstance(data, str):
        data = data.encode("utf-8")
    normalized_data = data.upper().replace(b"\x00", b"")
    if any(declaration in normalized_data for declaration in FORBIDDEN_DECLARATIONS):
        raise ValueError("DTD and entity declarations are not allowed in XML input")
    # DTD and entity declarations are rejected before this standard-library parse.
    return standard_et.ElementTree(standard_et.fromstring(data))  # nosec B314


def parse(source):
    """Parse untrusted XML safely, using defusedxml when it is available."""
    try:
        from defusedxml import ElementTree as safe_et
    except ImportError:
        return _stdlib_parse(source)
    return safe_et.parse(source)
