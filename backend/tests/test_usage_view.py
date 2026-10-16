from collective.quota.browser.usage import DEFAULT_LIMIT
from collective.quota.interfaces import IBrowserLayer
from plone import api
from plone.app.testing import logout
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from zExceptions import Unauthorized
from zope.interface import alsoProvides

import pytest
import re
import transaction


MB = 1024 * 1024


def render(view):
    """Rendered page with the space before ``>`` removed."""
    return re.sub(r"\s+>", ">", view())


@pytest.fixture
def usage_view(portal, http_request):
    """usage_view(role="Editor", **form) -> DiskUsageView as the test user"""
    alsoProvides(http_request, IBrowserLayer)

    def func(role="Editor", **form):
        setRoles(portal, TEST_USER_ID, ["Member", role])
        http_request.form.update(form)
        return portal.restrictedTraverse("@@quota-usage")

    return func


class TestPermission:
    def test_member_denied(self, usage_view):
        with pytest.raises(Unauthorized):
            usage_view("Member")

    def test_anonymous_denied(self, portal, http_request):
        alsoProvides(http_request, IBrowserLayer)
        logout()
        with pytest.raises(Unauthorized):
            portal.restrictedTraverse("@@quota-usage")

    @pytest.mark.parametrize(
        "role", ["Editor", "Contributor", "Reviewer", "Site Administrator", "Manager"]
    )
    def test_allowed(self, browser, functional_portal, role):
        test_browser = browser(role)
        test_browser.open(f"{functional_portal.absolute_url()}/@@quota-usage")
        assert test_browser.headers["status"] == "200 OK"
        assert "Disk usage" in test_browser.contents

    def test_anonymous_redirected_to_login(self, browser, functional_portal):
        test_browser = browser("Anonymous")
        test_browser.handleErrors = True
        test_browser.open(f"{functional_portal.absolute_url()}/@@quota-usage")
        assert "/login?came_from=" in test_browser.url


class TestLimit:
    @pytest.mark.parametrize(
        "value,expected",
        [(None, DEFAULT_LIMIT), ("10", 10), ("100", 100), ("999", 25), ("x", 25)],
    )
    def test_limit(self, usage_view, value, expected):
        form = {} if value is None else {"limit": value}
        assert usage_view(**form).limit() == expected


class TestItems:
    def test_items_sorted_desc_and_limited(self, portal, usage_view, make_file):
        for i in range(30):
            make_file(portal, f"f{i:02}", 1000 + i)
        items = usage_view().items()
        assert [item["size"] for item in items] == [1029 - i for i in range(25)]
        assert len(usage_view(limit="10").items()) == 10
        assert len(usage_view(limit="999").items()) == 25

    def test_item_fields(self, portal, usage_view, make_file):
        with api.env.adopt_roles(["Manager"]):
            folder = api.content.create(portal, "Folder", id="docs", title="Docs")
        make_file(folder, "report", 2 * MB)
        [item] = usage_view().items()
        url = f"{portal.absolute_url()}/docs/report"
        modified = item.pop("modified")
        assert modified
        assert item == {
            "uid": api.content.get(path="/docs/report").UID(),
            "title": "report",
            "url": url,
            "edit_url": f"{url}/edit",
            "portal_type": "File",
            "type_title": "File",
            "parent_url": f"{portal.absolute_url()}/docs",
            "parent_title": "Docs",
            "size": 2 * MB,
            "size_human": "2.0 MB",
            "can_delete": True,
        }

    def test_items_respect_view_permission(self, portal, usage_view, make_file):
        make_file(portal, "public", 1000)
        hidden = make_file(portal, "hidden", 2000)
        hidden.manage_permission("Access contents information", ["Manager"], 0)
        hidden.manage_permission("View", ["Manager"], acquire=False)
        hidden.reindexObjectSecurity()
        assert [item["title"] for item in usage_view("Contributor").items()] == [
            "public"
        ]

    def test_listed_item_without_view_permission(self, portal, usage_view, make_file):
        """Catalog visibility follows "Access contents information"."""
        obj = make_file(portal, "noview", 2000)
        obj.manage_permission("View", ["Manager"], acquire=False)
        [item] = usage_view("Contributor").items()
        assert item["title"] == "noview"

    def test_items_without_blobs_not_listed(self, portal, usage_view):
        with api.env.adopt_roles(["Manager"]):
            api.content.create(portal, "Document", id="doc", title="Doc")
        assert usage_view().items() == []

    def test_metadata_fallback(self, portal, usage_view, make_file):
        catalog = portal.portal_catalog
        catalog.delColumn("blob_size")
        make_file(portal, "a", 3000)
        catalog.addColumn("blob_size")  # existing records get Missing.Value
        [brain] = catalog(portal_type="File")
        assert not isinstance(brain.blob_size, int)
        [item] = usage_view().items()
        assert item["size"] == 3000

    def test_no_index(self, portal, usage_view, make_file):
        make_file(portal, "a", 3000)
        portal.portal_catalog.delIndex("blob_size")
        assert usage_view().items() == []

    def test_can_delete_flag(self, portal, usage_view, make_file):
        obj = make_file(portal, "keep", 1000)
        obj.manage_permission("Delete objects", ["Manager"], acquire=False)
        view = usage_view()
        [item] = view.items()
        assert item["can_delete"] is False
        html = view()
        assert 'title="You cannot delete this item"' in html
        assert 'name="uids:list"' not in html
        assert 'class="quota-delete"' not in html

    def test_unknown_type_title(self, portal, usage_view, make_file):
        make_file(portal, "a", 1000)
        portal.portal_types.manage_delObjects(["File"])
        [item] = usage_view().items()
        assert item["type_title"] == "File"


class TestSummary:
    def test_summary_shows_limits_policy_and_level(
        self, portal, usage_view, make_file, set_quota
    ):
        make_file(portal, "a", 3 * MB)
        set_quota(soft_mb=2, hard_mb=10, policy="block_files")
        html = render(usage_view())
        assert '<strong id="quota-usage-total">3.0 MB</strong>' in html
        assert '<strong id="quota-usage-hard">10.0 MB</strong>' in html
        assert "(30%)" in html
        assert 'data-level="warning"' in html
        assert "Allow new items, block uploads that add bytes" in html
        assert "<span>2.0 MB</span>" in html
        assert 'class="alert alert-warning" id="quota-usage-alert"' in html
        assert "Disk usage warning: this site uses 3.0 MB of 10.0 MB (30%)." in html

    def test_alert_danger_when_exceeded(self, portal, usage_view, make_file, set_quota):
        make_file(portal, "a", 3 * MB)
        set_quota(hard_mb=2, policy="block_all")
        html = usage_view()()
        assert 'class="alert alert-danger" id="quota-usage-alert"' in html
        assert "Disk quota exceeded: this site uses 3.0 MB of 2.0 MB." in html

    def test_no_alert_and_no_bar_when_limits_disabled(self, usage_view):
        html = usage_view()()
        assert 'id="quota-usage-alert"' not in html
        assert 'id="quota-usage-bar"' not in html
        assert "No uploaded files or images found." in html
        assert 'id="quota-delete-selected"' not in html

    def test_manage_links_only_for_managers(self, usage_view):
        assert 'id="quota-usage-manage"' not in usage_view("Editor")()
        html = usage_view("Site Administrator")()
        assert 'id="quota-usage-manage"' in html
        assert "/@@quota-controlpanel" in html
        assert "/@@quota-rebuild" in html

    def test_footer_mentions_limit(self, usage_view):
        html = " ".join(usage_view(limit="10")().split())
        assert "Showing the 10 largest items you can see." in html


class TestPage:
    def test_listing_and_limit_selector(self, browser, functional_portal, make_file):
        for i in range(12):
            make_file(functional_portal, f"f{i:02}", 1000 + i)
        transaction.commit()
        test_browser = browser("Editor")
        test_browser.open(f"{functional_portal.absolute_url()}/@@quota-usage")
        assert test_browser.contents.count('name="uids:list"') == 12
        test_browser.getControl(name="limit").value = ["10"]
        test_browser.getForm(id="quota-limit-form").submit()
        assert "limit=10" in test_browser.url
        assert test_browser.contents.count('name="uids:list"') == 10
        assert 'id="collective-quota-warning"' not in test_browser.contents
