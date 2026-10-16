"""collective.quota.listing: the biggest items shared by both UIs."""

from collective.quota.listing import biggest_items
from collective.quota.listing import DEFAULT_LIMIT
from collective.quota.listing import Item
from collective.quota.listing import LIMITS
from collective.quota.listing import parse_limit
from DateTime import DateTime
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

import pytest


MB = 1024 * 1024


@pytest.fixture
def items(portal, http_request):
    """items(role="Editor", limit=25) -> biggest_items as the test user"""

    def func(role="Editor", limit=DEFAULT_LIMIT):
        setRoles(portal, TEST_USER_ID, ["Member", role])
        return biggest_items(portal, http_request, limit)

    return func


class TestParseLimit:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, DEFAULT_LIMIT),
            ("", DEFAULT_LIMIT),
            ("x", DEFAULT_LIMIT),
            ("999", DEFAULT_LIMIT),
            ("10", 10),
            (50, 50),
            ("100", 100),
        ],
    )
    def test_parse_limit(self, value, expected):
        assert parse_limit(value) == expected

    def test_limits(self):
        assert LIMITS == (10, 25, 50, 100)
        assert DEFAULT_LIMIT in LIMITS


class TestBiggestItems:
    def test_ordering_and_limit(self, portal, items, make_file):
        for i in range(12):
            make_file(portal, f"f{i:02}", 1000 + i)
        assert [item.size for item in items(limit=10)] == [1011 - i for i in range(10)]
        assert len(items()) == 12

    def test_item(self, portal, items, make_file):
        with api.env.adopt_roles(["Manager"]):
            folder = api.content.create(portal, "Folder", id="docs", title="Docs")
        obj = make_file(folder, "report", 2 * MB)
        [item] = items()
        assert isinstance(item, Item)
        assert isinstance(item.modified, DateTime)
        assert item == Item(
            uid=obj.UID(),
            title="report",
            url=obj.absolute_url(),
            portal_type="File",
            type_title="File",
            parent_url=folder.absolute_url(),
            parent_title="Docs",
            size=2 * MB,
            modified=item.modified,
            can_delete=True,
        )

    def test_restricted_search_hides_items(self, portal, items, make_file):
        make_file(portal, "public", 1000)
        hidden = make_file(portal, "hidden", 2000)
        hidden.manage_permission("Access contents information", ["Manager"], 0)
        hidden.manage_permission("View", ["Manager"], acquire=False)
        hidden.reindexObjectSecurity()
        assert [item.title for item in items()] == ["public"]

    def test_can_delete_false(self, portal, items, make_file):
        obj = make_file(portal, "keep", 1000)
        obj.manage_permission("Delete objects", ["Manager"], acquire=False)
        [item] = items()
        assert item.can_delete is False

    def test_metadata_fallback(self, portal, items, make_file):
        catalog = portal.portal_catalog
        catalog.delColumn("blob_size")
        make_file(portal, "a", 3000)
        catalog.addColumn("blob_size")  # existing records get Missing.Value
        [item] = items()
        assert item.size == 3000

    def test_no_index(self, portal, items, make_file):
        make_file(portal, "a", 3000)
        portal.portal_catalog.delIndex("blob_size")
        assert items() == []
