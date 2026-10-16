"""Let REST clients query ``blob_size`` (``@search?blob_size.query=1&...``).

plone.restapi parses query strings per index class; a ``FieldIndex`` subclass
would get the generic parser, which keeps the values as strings and makes the
comparison with the stored integers fail.
"""

from collective.quota.catalog.blob_size_index import BlobSizeIndex
from plone.restapi.interfaces import IIndexQueryParser
from plone.restapi.search.query import BaseIndexQueryParser
from typing import ClassVar
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface


@implementer(IIndexQueryParser)
@adapter(BlobSizeIndex, Interface, Interface)
class BlobSizeIndexQueryParser(BaseIndexQueryParser):
    query_value_type = int
    query_options: ClassVar[dict] = {"range": str}
