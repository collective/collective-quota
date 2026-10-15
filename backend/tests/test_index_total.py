from BTrees.Length import Length
from collective.quota.catalog.blob_size_index import BlobSizeIndex
from collective.quota.usage import get_index
from collective.quota.usage import get_total_usage
from plone import api
from types import SimpleNamespace

import pytest


KB = 1024


def recomputed(index):
    return sum(v for v in index._unindex.values() if isinstance(v, int))


@pytest.fixture
def manager():
    with api.env.adopt_roles(["Manager"]):
        yield


class TestTotalInPortal:
    def test_total_follows_add_edit_delete(self, portal, make_file, make_blob, manager):
        a = make_file(portal, "a", 10 * KB)
        make_file(portal, "b", 20 * KB)
        make_file(portal, "c", 30 * KB)
        assert get_total_usage(portal) == 60 * KB
        a.file = make_blob(5 * KB)
        a.reindexObject()
        assert get_total_usage(portal) == 55 * KB
        api.content.delete(obj=portal["b"])
        assert get_total_usage(portal) == 35 * KB

    def test_total_follows_move_copy_rename(self, portal, make_file, manager):
        folder = api.content.create(container=portal, type="Folder", id="folder")
        obj = make_file(portal, "a", 10 * KB)
        assert get_total_usage(portal) == 10 * KB
        obj = api.content.move(source=obj, target=folder)
        assert get_total_usage(portal) == 10 * KB
        obj = api.content.rename(obj=obj, new_id="renamed")
        assert get_total_usage(portal) == 10 * KB
        api.content.copy(source=obj, target=portal)
        assert get_total_usage(portal) == 20 * KB

    def test_total_follows_folder_delete(self, portal, make_file, manager):
        folder = api.content.create(container=portal, type="Folder", id="folder")
        make_file(folder, "a", 10 * KB)
        make_file(folder, "b", 20 * KB)
        make_file(portal, "c", 5 * KB)
        api.content.delete(obj=folder)
        assert get_total_usage(portal) == 5 * KB

    def test_clear_and_rebuild_restores_total(self, portal, make_file):
        make_file(portal, "a", 10 * KB)
        make_file(portal, "b", 20 * KB)
        get_total_usage(portal)  # flush the indexing queue
        get_index(portal)._total = Length(12345)
        api.portal.get_tool("portal_catalog").clearFindAndRebuild()
        # clearFindAndRebuild goes through the indexing queue too.
        assert get_total_usage(portal) == 30 * KB
        assert recomputed(get_index(portal)) == 30 * KB

    def test_reindex_index_populates_empty_index(self, portal, make_file):
        make_file(portal, "a", 10 * KB)
        make_file(portal, "b", 20 * KB)
        get_total_usage(portal)  # flush the indexing queue
        catalog = api.portal.get_tool("portal_catalog")
        catalog.manage_clearIndex(["blob_size"])
        assert get_index(portal).total() == 0
        catalog.reindexIndex("blob_size", portal.REQUEST)
        assert get_index(portal).total() == 30 * KB

    def test_reindex_index_keeps_correct_total(self, portal, make_file):
        make_file(portal, "a", 10 * KB)
        get_total_usage(portal)  # flush the indexing queue
        api.portal.get_tool("portal_catalog").reindexIndex("blob_size", portal.REQUEST)
        assert get_index(portal).total() == 10 * KB

    def test_total_lazy_rebuild_when_attribute_missing(self, portal, make_file):
        make_file(portal, "a", 10 * KB)
        get_total_usage(portal)  # flush the indexing queue
        index = get_index(portal)
        del index._total  # instance created before the attribute existed
        assert index.total() == 10 * KB


class TestIndexUnit:
    """BlobSizeIndex on its own, without a catalog."""

    @pytest.fixture
    def index(self):
        return BlobSizeIndex("blob_size")

    def test_new_index_total_zero(self, index):
        assert index.total() == 0

    def test_index_reindex_unindex(self, index):
        index.index_object(1, SimpleNamespace(blob_size=5))
        index.index_object(2, SimpleNamespace(blob_size=7))
        assert index.total() == 12
        index.index_object(1, SimpleNamespace(blob_size=10))
        assert index.total() == 17
        index.unindex_object(2)
        assert index.total() == 10
        index.unindex_object(2)  # not indexed: no change
        assert index.total() == 10

    def test_datum_none_removes_and_subtracts(self, index):
        # The base class returns 0 here although it removed the entry.
        index.index_object(1, SimpleNamespace(blob_size=5))
        index.index_object(1, SimpleNamespace(blob_size=None))
        assert index.getEntryForObject(1, None) is None
        assert index.total() == 0

    def test_missing_attribute_keeps_out(self, index):
        index.index_object(1, SimpleNamespace())
        assert index.numObjects() == 0
        assert index.total() == 0

    @pytest.mark.parametrize("value", [True, 1.5])
    def test_non_int_values_ignored(self, index, value):
        index.index_object(1, SimpleNamespace(blob_size=value))
        index.index_object(2, SimpleNamespace(blob_size=3))
        assert index.total() == 3
        assert index.rebuild_total() == 3
        index.unindex_object(1)
        assert index.total() == 3

    def test_clear_resets_total(self, index):
        index.index_object(1, SimpleNamespace(blob_size=5))
        index.clear()
        assert index.total() == 0

    def test_note_index_change_called(self, index, monkeypatch):
        from collective.quota import guard

        calls = []
        monkeypatch.setattr(guard, "note_index_change", lambda i, d: calls.append(d))
        index.index_object(1, SimpleNamespace(blob_size=5))
        index.index_object(1, SimpleNamespace(blob_size=5))  # unchanged: no call
        index.unindex_object(1)
        assert calls == [5, -5]
