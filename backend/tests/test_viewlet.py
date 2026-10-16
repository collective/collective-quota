from Acquisition import aq_base
from collective.quota.browser.viewlets import QuotaWarningViewlet
from collective.quota.interfaces import IBrowserLayer
from plone.app.layout.viewlets.interfaces import IGlobalStatusMessage
from plone.app.testing import logout
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.viewletmanager.interfaces import IViewletSettingsStorage
from Products.Five import BrowserView
from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.interface import alsoProvides
from zope.viewlet.interfaces import IViewlet
from zope.viewlet.interfaces import IViewletManager

import pytest
import transaction


MB = 1024 * 1024
NAME = "collective.quota.warning"


@pytest.fixture
def render_manager(portal, http_request):
    """render_manager(role="Editor", view_name="view") -> rendered manager HTML"""
    alsoProvides(http_request, IBrowserLayer)

    def func(role="Editor", view_name="view"):
        if role == "Anonymous":
            logout()
        else:
            setRoles(portal, TEST_USER_ID, ["Member", role])
        view = BrowserView(portal, http_request)
        view.__name__ = view_name
        manager = getMultiAdapter(
            (portal, http_request, view), IViewletManager, "plone.globalstatusmessage"
        )
        manager.update()
        return manager.render()

    return func


@pytest.fixture
def viewlet(portal, http_request):
    """viewlet() -> updated QuotaWarningViewlet for the site root"""
    alsoProvides(http_request, IBrowserLayer)

    def func():
        view = BrowserView(portal, http_request)
        view.__name__ = "view"
        manager = getMultiAdapter(
            (portal, http_request, view), IViewletManager, "plone.globalstatusmessage"
        )
        instance = getMultiAdapter(
            (portal, http_request, view, manager), IViewlet, NAME
        )
        assert isinstance(instance, QuotaWarningViewlet)
        instance.update()
        return instance

    return func


@pytest.fixture
def usage(portal, make_file, set_quota):
    """usage(used_mb, soft_mb=0, hard_mb=0, policy="block_all", max_file_mb=10)"""

    def func(used_mb, soft_mb=0, hard_mb=0, policy="block_all", max_file_mb=10):
        make_file(portal, "big", int(used_mb * MB))
        set_quota(
            soft_mb=soft_mb, hard_mb=hard_mb, policy=policy, max_file_mb=max_file_mb
        )

    return func


class TestVisibility:
    def test_hidden_for_anonymous_even_over_limit(self, usage, render_manager):
        usage(3, hard_mb=2)
        assert 'id="collective-quota-warning"' not in render_manager("Anonymous")

    def test_hidden_for_anonymous_when_permission_mis_mapped(
        self, portal, usage, render_manager
    ):
        usage(3, hard_mb=2)
        portal.manage_permission(
            "collective.quota: View Disk Usage", ["Anonymous"], acquire=True
        )
        assert 'id="collective-quota-warning"' not in render_manager("Anonymous")

    def test_hidden_for_member_without_permission(self, usage, render_manager):
        usage(3, hard_mb=2)
        assert 'id="collective-quota-warning"' not in render_manager("Member")

    @pytest.mark.parametrize(
        "role", ["Editor", "Contributor", "Reviewer", "Site Administrator", "Manager"]
    )
    def test_shown_for_roles_with_permission(self, usage, render_manager, role):
        usage(3, hard_mb=2)
        assert 'id="collective-quota-warning"' in render_manager(role)

    def test_hidden_below_soft_limit(self, usage, render_manager):
        usage(1, soft_mb=2, hard_mb=4)
        assert 'id="collective-quota-warning"' not in render_manager()

    def test_hidden_when_limits_disabled(self, usage, render_manager):
        usage(3)
        assert 'id="collective-quota-warning"' not in render_manager()

    @pytest.mark.parametrize("view_name", ["quota-usage", "quota-controlpanel"])
    def test_hidden_on_usage_and_controlpanel_views(
        self, usage, render_manager, view_name
    ):
        usage(3, hard_mb=2)
        assert 'id="collective-quota-warning"' not in render_manager(
            view_name=view_name
        )


class TestContent:
    def test_warning_between_soft_and_hard(self, usage, viewlet):
        usage(1.5, soft_mb=1, hard_mb=2)
        instance = viewlet()
        assert instance.available
        assert instance.css_class == "alert-warning"
        html = instance.render()
        assert 'class="alert alert-warning d-flex' in html
        assert 'data-level="warning"' in html
        assert "this site uses 1.5 MB of 2.0 MB (75%)" in html

    @pytest.mark.parametrize(
        "policy,hint",
        [
            (
                "block_all",
                "New content and uploads are blocked until files are removed.",
            ),
            ("block_files", "Uploads are blocked until files are removed."),
            (
                "limit_file_size",
                "Only files up to 1.0 MB can be uploaded until files are removed.",
            ),
            ("allow", "Uploads are still allowed."),
        ],
    )
    def test_danger_at_hard_limit_with_policy_hint(self, usage, viewlet, policy, hint):
        usage(2, soft_mb=1, hard_mb=2, policy=policy, max_file_mb=1)
        instance = viewlet()
        assert instance.css_class == "alert-danger"
        html = instance.render()
        assert 'class="alert alert-danger d-flex' in html
        assert f"Disk quota exceeded: this site uses 2.0 MB of 2.0 MB. {hint}" in html

    def test_button_links_to_usage_view(self, portal, usage, viewlet):
        usage(3, hard_mb=2)
        html = viewlet().render()
        assert f'href="{portal.absolute_url()}/@@quota-usage"' in html
        assert "Review disk usage" in html

    def test_render_empty_when_unavailable(self, viewlet):
        assert viewlet().render() == ""

    def test_reads_only_the_running_total(self, portal, usage, viewlet, monkeypatch):
        """O(1): the viewlet never searches the catalog."""
        usage(3, hard_mb=2)
        catalog_class = type(aq_base(portal.portal_catalog))

        searches = []
        for name in ("searchResults", "unrestrictedSearchResults", "__call__"):
            monkeypatch.setattr(catalog_class, name, searches.append)
        assert viewlet().available
        assert searches == []


class TestRegistration:
    def test_order_after_status_messages(self, portal):
        storage = getUtility(IViewletSettingsStorage)
        skinname = portal.getCurrentSkinName()
        order = list(storage.getOrder("plone.globalstatusmessage", skinname))
        assert order[:2] == ["plone.globalstatusmessage", NAME]

    def test_registered_for_manager(self, portal, http_request):
        alsoProvides(http_request, IBrowserLayer)
        setRoles(portal, TEST_USER_ID, ["Editor"])
        view = BrowserView(portal, http_request)
        manager = getMultiAdapter(
            (portal, http_request, view), IViewletManager, "plone.globalstatusmessage"
        )
        assert IGlobalStatusMessage.providedBy(manager)
        manager.update()
        names = [v.__name__ for v in manager.viewlets]
        assert names.index("plone.globalstatusmessage") < names.index(NAME)


class TestPage:
    def test_rendered_in_page_for_editor(
        self, browser, functional_portal, make_file, set_quota
    ):
        make_file(functional_portal, "big", 3 * MB)
        set_quota(soft_mb=1, hard_mb=2)
        transaction.commit()
        url = functional_portal.absolute_url()

        editor = browser("Editor")
        editor.open(url)
        contents = editor.contents
        assert 'id="collective-quota-warning"' in contents
        # Below the status messages, above the content.
        assert contents.index('id="global_statusmessage"') < contents.index(
            'id="collective-quota-warning"'
        )
        editor.getLink("Review disk usage").click()
        assert editor.url == f"{url}/@@quota-usage"
        assert 'id="collective-quota-warning"' not in editor.contents

        anonymous = browser("Anonymous")
        anonymous.open(url)
        assert 'id="collective-quota-warning"' not in anonymous.contents

    def test_hidden_on_controlpanel_page(
        self, browser, functional_portal, make_file, set_quota
    ):
        make_file(functional_portal, "big", 3 * MB)
        set_quota(hard_mb=2)
        transaction.commit()
        manager = browser("Manager")
        manager.open(f"{functional_portal.absolute_url()}/@@quota-controlpanel")
        assert 'id="collective-quota-warning"' not in manager.contents
        manager.open(f"{functional_portal.absolute_url()}/folder_contents")
        assert 'id="collective-quota-warning"' in manager.contents
