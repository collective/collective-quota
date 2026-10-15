from Acquisition import aq_base
from collective.quota import usage
from collective.quota.guard import guard_suspended
from collective.quota.guard import note_index_change
from collective.quota.settings import QuotaSettings
from collective.quota.usage import get_index
from collective.quota.usage import get_total_usage
from collective.quota.usage import get_usage_info
from collective.quota.usage import rebuild_usage
from plone import api
from ZODB.POSException import ConflictError

import pytest


MB = 1024 * 1024


def settings(soft=0, hard=0):
    return QuotaSettings(
        soft_bytes=soft, hard_bytes=hard, policy="block_all", max_file_bytes=10 * MB
    )


class FakeBrain:
    def __init__(self, exc):
        self.exc = exc

    def getPath(self):
        return "/plone/broken"

    def _unrestrictedGetObject(self):
        raise self.exc


class TestIndexLookup:
    def test_get_index_default_portal(self, portal):
        assert get_index() is not None

    def test_missing_index(self, portal):
        api.portal.get_tool("portal_catalog").delIndex("blob_size")
        assert get_index(portal) is None
        assert get_total_usage(portal) == 0
        assert rebuild_usage(portal) == 0

    def test_wrong_index_type(self, portal):
        catalog = api.portal.get_tool("portal_catalog")
        catalog.delIndex("blob_size")
        catalog.addIndex("blob_size", "FieldIndex")
        assert get_index(portal) is None


class TestUsageInfo:
    @pytest.mark.parametrize(
        "soft,hard,total,level,percent",
        [
            (0, 0, 5 * MB, "ok", None),
            (10 * MB, 0, 5 * MB, "ok", None),
            (4 * MB, 0, 5 * MB, "warning", None),
            (4 * MB, 10 * MB, 5 * MB, "warning", 50),
            (0, 10 * MB, 5 * MB, "ok", 50),
            (4 * MB, 5 * MB, 5 * MB, "exceeded", 100),
            (0, 4 * MB, 5 * MB, "exceeded", 125),
        ],
    )
    def test_levels(
        self, portal, make_file, monkeypatch, soft, hard, total, level, percent
    ):
        make_file(portal, "f", total)
        monkeypatch.setattr(usage, "get_settings", lambda: settings(soft, hard))
        info = get_usage_info(portal)
        assert (info.total, info.soft, info.hard) == (total, soft, hard)
        assert info.level == level
        assert info.percent == percent


class TestRebuildUsage:
    def test_counts_and_logs(self, portal, make_file, caplog):
        make_file(portal, "a", 10)
        make_file(portal, "b", 20)
        caplog.set_level("INFO", logger="collective.quota")
        count = rebuild_usage(portal, log_every=1)
        catalog = api.portal.get_tool("portal_catalog")
        assert count == len(catalog.unrestrictedSearchResults(path="/plone"))
        assert "rebuild_usage: 1 items processed" in caplog.text
        assert "total 30 bytes" in caplog.text

    def test_without_metadata_update(self, portal, make_file):
        make_file(portal, "a", 10)
        get_index(portal).clear()
        rebuild_usage(portal, update_metadata=False)
        assert get_total_usage(portal) == 10

    def test_skips_objects_that_fail_to_load(self, portal, monkeypatch, caplog):
        catalog = api.portal.get_tool("portal_catalog")
        monkeypatch.setattr(
            type(aq_base(catalog)),
            "unrestrictedSearchResults",
            lambda self, *a, **kw: [FakeBrain(KeyError("gone"))],
        )
        assert rebuild_usage(portal) == 0
        assert "Cannot load /plone/broken; skipped" in caplog.text

    def test_conflict_error_propagates(self, portal, monkeypatch):
        catalog = api.portal.get_tool("portal_catalog")
        monkeypatch.setattr(
            type(aq_base(catalog)),
            "unrestrictedSearchResults",
            lambda self, *a, **kw: [FakeBrain(ConflictError())],
        )
        with pytest.raises(ConflictError):
            rebuild_usage(portal)

    def test_commit_every(self, functional_portal, make_blob):
        # Functional layer: commits are isolated per test.
        with api.env.adopt_roles(["Manager"]):
            for i in range(3):
                api.content.create(
                    container=functional_portal,
                    type="File",
                    id=f"f{i}",
                    file=make_blob(100),
                )
        get_index(functional_portal).clear()
        count = rebuild_usage(functional_portal, commit_every=2)
        assert count == 4  # site root + 3 files
        assert get_total_usage(functional_portal) == 300


class TestStubs:
    def test_guard_stubs(self):
        assert note_index_change(None, 5) is None
        with guard_suspended():
            pass
