from collective.quota.indexers.blob_size import get_blob_sizes
from collective.quota.indexers.blob_size import get_stored_value
from collective.quota.indexers.blob_size import has_blob_fields
from collective.quota.testing import MULTI_BLOB_TYPE
from collective.quota.usage import get_index
from plone import api
from ZODB.POSException import ConflictError
from zope.interface import Interface

import Missing
import pytest


def brain_for(obj):
    catalog = api.portal.get_tool("portal_catalog")
    (brain,) = catalog.unrestrictedSearchResults(UID=obj.UID())
    return brain


def indexed_value(portal, obj):
    return get_index(portal).getEntryForObject(brain_for(obj).getRID(), None)


def create(container, **kwargs):
    with api.env.adopt_roles(["Manager"]):
        return api.content.create(container=container, **kwargs)


class BrokenBlob:
    def __init__(self, exc):
        self.exc = exc

    def getSize(self):
        raise self.exc


class TestIndexer:
    def test_file_indexed(self, portal, make_file):
        obj = make_file(portal, "f1", 10240)
        assert brain_for(obj).blob_size == 10240
        assert indexed_value(portal, obj) == 10240

    def test_image_indexed(self, portal, make_image):
        obj = make_image(portal, "i1", 5000)
        assert brain_for(obj).blob_size == 5000
        assert indexed_value(portal, obj) == 5000

    def test_lead_image_behavior(self, portal, make_blob):
        doc = create(
            portal,
            type="Document",
            id="d1",
            title="d1",
            image=make_blob(3000, filename="lead.png", image=True),
        )
        assert indexed_value(portal, doc) == 3000

    def test_document_without_lead_image_indexes_zero(self, portal):
        doc = create(portal, type="Document", id="d2", title="d2")
        assert brain_for(doc).blob_size == 0

    @pytest.mark.parametrize("portal_type", ["Folder", "Link"])
    def test_items_without_blob_fields_not_indexed(self, portal, portal_type):
        obj = create(portal, type=portal_type, id="x", title="x")
        brain = brain_for(obj)
        assert brain.blob_size is Missing.Value
        assert indexed_value(portal, obj) is None
        catalog = api.portal.get_tool("portal_catalog")
        hits = catalog(blob_size={"query": 0, "range": "min"})
        assert obj.UID() not in [b.UID for b in hits]

    def test_multi_field_sum(self, portal, make_blob):
        obj = create(
            portal,
            type=MULTI_BLOB_TYPE,
            title="Multi",
            attachment=make_blob(1000),
            picture=make_blob(2000, filename="p.png", image=True),
            second=make_blob(3000),
        )
        assert get_blob_sizes(obj) == {
            "attachment": 1000,
            "picture": 2000,
            "second": 3000,
        }
        assert indexed_value(portal, obj) == 6000
        obj.second = None
        obj.reindexObject()
        assert indexed_value(portal, obj) == 3000

    def test_empty_blob_fields_index_zero(self, portal):
        obj = create(portal, type="File", id="empty", title="empty")
        assert brain_for(obj).blob_size == 0

    def test_corrupt_blob_counts_zero_and_logs(self, portal, make_file, caplog):
        obj = make_file(portal, "f1", 1000)
        obj.file = BrokenBlob(OSError("missing blob"))
        obj.reindexObject()
        assert indexed_value(portal, obj) == 0
        assert "Cannot read the size of field 'file'" in caplog.text

    def test_conflict_error_propagates(self, portal, make_file):
        obj = make_file(portal, "f1", 1000)
        obj.file = BrokenBlob(ConflictError())
        with pytest.raises(ConflictError):
            get_blob_sizes(obj)

    def test_has_blob_fields(self, portal, make_file):
        assert has_blob_fields(make_file(portal, "f1", 10)) is True
        assert (
            has_blob_fields(create(portal, type="Folder", id="fo", title="fo")) is False
        )

    def test_get_stored_value_without_adapter(self, portal, make_file):
        class IUnrelated(Interface):
            pass

        assert get_stored_value(make_file(portal, "f1", 10), IUnrelated, "x") is None
