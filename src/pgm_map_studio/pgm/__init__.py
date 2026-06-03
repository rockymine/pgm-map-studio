"""PGM map.xml parser.

Public API:
    parse(xml_path)  → MapXml
    MapXml           — parsed map data dataclass
"""

from .datatypes import MapXml
from .parser import parse
from .xml_writer import to_xml

__all__ = ['MapXml', 'parse', 'to_xml']
