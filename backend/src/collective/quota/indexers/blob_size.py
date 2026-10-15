"""``blob_size`` indexer: sum of the bytes stored in an item's blob fields."""

from collective.quota import logger
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.utils import iterSchemata
from plone.indexer import indexer
from plone.namedfile.interfaces import INamedField
from ZODB.POSException import ConflictError
from zope.schema import getFieldsInOrder


def iter_blob_fields(obj):
    """Yield (schema, name, field) for every INamedField on obj.

    Covers the type schema and all behavior schemas.
    """
    for schema in iterSchemata(obj):
        for name, field in getFieldsInOrder(schema):
            if INamedField.providedBy(field):
                yield schema, name, field


def get_stored_value(obj, schema, name):
    """Read a field value through the schema adapter (obj itself for the main
    schema, the behavior adapter otherwise)."""
    adapter = schema(obj, None)
    if adapter is None:
        return None
    return getattr(adapter, name, None)


def get_blob_sizes(obj) -> dict[str, int]:
    """Map each blob field name to the bytes it stores (0 when empty)."""
    sizes = {}
    for schema, name, _field in iter_blob_fields(obj):
        value = get_stored_value(obj, schema, name)
        size = 0
        if value is not None:
            try:
                # Reads the stored _size; the blob file is not opened.
                size = int(value.getSize() or 0)
            except ConflictError:
                raise
            except Exception:
                logger.warning(
                    "Cannot read the size of field %r on %s; counting 0",
                    name,
                    "/".join(obj.getPhysicalPath()),
                    exc_info=True,
                )
        sizes[name] = size
    return sizes


def has_blob_fields(obj) -> bool:
    return any(True for _ in iter_blob_fields(obj))


@indexer(IDexterityContent)
def blob_size(obj):
    sizes = get_blob_sizes(obj)
    if not sizes:
        # Keeps items without blob fields out of the index.
        raise AttributeError("blob_size")
    return sum(sizes.values())
