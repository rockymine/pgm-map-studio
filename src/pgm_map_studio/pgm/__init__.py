"""PGM map.xml parser.

Public API:
    parse(xml_path)  → MapXml
    MapXml           — parsed map data dataclass
"""

from .datatypes import MapXml
from .parser import parse

__all__ = ['MapXml', 'parse']
