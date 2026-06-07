"""PGM map.xml parser and xml_data.json serialization.

Public API:
    parse(xml_path)      → MapXml          (map.xml → MapXml)
    to_xml(xml_data)     → str             (MapXml → map.xml string)
    from_dict(d)         → MapXml          (xml_data.json dict → MapXml)
    load(path)           → MapXml          (xml_data.json file → MapXml)
    MapXml               — parsed map data dataclass
"""

from .datatypes import MapXml
from .parser import parse
from .xml_writer import to_xml
from .deserializer import from_dict, load

__all__ = ['MapXml', 'parse', 'to_xml', 'from_dict', 'load']
