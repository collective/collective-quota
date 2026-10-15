from BTrees.Length import Length
from collective.quota.interfaces import IBrowserLayer
from collective.quota.usage import get_index
from collective.quota.usage import get_total_usage
from pathlib import Path
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.protect.authenticator import createToken
from Products.Five.browser import BrowserView
from Products.statusmessages.interfaces import IStatusMessage
from zExceptions import Forbidden
from zExceptions import MethodNotAllowed
from zExceptions import Unauthorized
from zope.component import getSiteManager
from zope.interface import alsoProvides
from zope.interface import Interface
from zope.publisher.interfaces.browser import IBrowserRequest

import importlib.util
import pytest
import transaction


SCRIPT = Path(__file__).parent.parent / "scripts" / "rebuild_blob_size.py"


@pytest.fixture
def rebuild_view(portal, http_request):
    alsoProvides(http_request, IBrowserLayer)
    http_request.method = "POST"

    def func(token=True):
        if token:
            http_request.form["_authenticator"] = createToken()
        return portal.restrictedTraverse("@@quota-rebuild")

    return func


@pytest.fixture
def manager(portal):
    with api.env.adopt_roles(["Manager"]):
        yield


class TestRebuildView:
    def test_get_not_allowed(self, rebuild_view, http_request, manager):
        view = rebuild_view()
        http_request.method = "GET"
        with pytest.raises(MethodNotAllowed):
            view()

    def test_post_without_token_forbidden(self, rebuild_view, manager):
        with pytest.raises(Forbidden):
            rebuild_view(token=False)()

    def test_post_rebuilds_and_redirects_to_portal(
        self, portal, rebuild_view, http_request, make_file, manager
    ):
        make_file(portal, "a", 2048)
        get_total_usage(portal)
        get_index(portal)._total = Length(1)
        rebuild_view()()
        assert get_index(portal).total() == 2048
        assert http_request.response.getHeader("location") == portal.absolute_url()
        (message,) = IStatusMessage(http_request).show()
        assert (
            message.message == "Usage data rebuilt: 2 items, 2.0 KB in total."
        )  # site root + file

    def test_redirects_to_controlpanel_when_available(
        self, portal, rebuild_view, http_request, manager
    ):
        sm = getSiteManager()
        sm.registerAdapter(
            BrowserView, (Interface, IBrowserRequest), Interface, "quota-controlpanel"
        )
        try:
            rebuild_view()()
        finally:
            sm.unregisterAdapter(
                BrowserView,
                (Interface, IBrowserRequest),
                Interface,
                "quota-controlpanel",
            )
        location = http_request.response.getHeader("location")
        assert location == f"{portal.absolute_url()}/@@quota-controlpanel"


class TestRebuildPermission:
    @pytest.mark.parametrize("role", ["Editor", "Contributor", "Reviewer", "Member"])
    def test_requires_manage_settings(self, portal, http_request, role):
        alsoProvides(http_request, IBrowserLayer)
        setRoles(portal, TEST_USER_ID, [role])
        with pytest.raises(Unauthorized):
            portal.restrictedTraverse("@@quota-rebuild")

    @pytest.mark.parametrize("role", ["Manager", "Site Administrator"])
    def test_allowed_roles(self, portal, http_request, role):
        alsoProvides(http_request, IBrowserLayer)
        setRoles(portal, TEST_USER_ID, [role])
        assert portal.restrictedTraverse("@@quota-rebuild") is not None


class TestScript:
    @pytest.fixture
    def script(self):
        spec = importlib.util.spec_from_file_location("rebuild_blob_size", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_script_runs(self, script, functional_app, functional_portal, make_blob):
        with api.env.adopt_roles(["Manager"]):
            api.content.create(
                container=functional_portal, type="File", id="f", file=make_blob(500)
            )
        transaction.commit()
        get_index(functional_portal)._total = Length(0)
        assert script.main(functional_app, functional_portal.getId()) == 0
        assert get_index(functional_portal).total() == 500

    def test_script_site_not_found(self, script, functional_app, caplog):
        assert script.main(functional_app, "nope") == 1
        assert "Site 'nope' not found" in caplog.text
