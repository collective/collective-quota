from collective.quota.interfaces import IBrowserLayer
from collective.quota.usage import get_total_usage
from plone import api
from plone.app.linkintegrity.tests.utils import set_text
from plone.app.testing import login
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.locking.interfaces import ILockable
from plone.protect.authenticator import createToken
from Products.statusmessages.interfaces import IStatusMessage
from zExceptions import Forbidden
from zope.interface import alsoProvides

import pytest
import re
import transaction


MB = 1024 * 1024


@pytest.fixture
def delete_view(portal, http_request):
    """delete_view(*uids, role="Editor", confirm=False, token=True, **form)"""
    alsoProvides(http_request, IBrowserLayer)

    def func(*uids, role="Editor", confirm=False, token=True, **form):
        setRoles(portal, TEST_USER_ID, ["Member", role])
        if uids:
            form["uids"] = list(uids)
        if confirm:
            form["form.button.confirm"] = "Delete"
            http_request.method = "POST"
            if token:
                form["_authenticator"] = createToken()
        http_request.form.update(form)
        return portal.restrictedTraverse("@@quota-delete")

    return func


@pytest.fixture
def messages(http_request):
    def func():
        return [(m.message, m.type) for m in IStatusMessage(http_request).show()]

    return func


@pytest.fixture
def files(portal, make_file):
    """Two files: a (1 MB) and b (2 MB)."""
    return make_file(portal, "a", MB), make_file(portal, "b", 2 * MB)


def redirected_to_usage(portal, http_request):
    return http_request.response.getHeader("Location") == (
        f"{portal.absolute_url()}/@@quota-usage"
    )


class TestStepOne:
    def test_no_selection_redirects_with_message(
        self, portal, http_request, delete_view, messages
    ):
        delete_view()()
        assert redirected_to_usage(portal, http_request)
        assert messages() == [("No items selected.", "warning")]

    def test_single_uid_string(self, delete_view, files):
        view = delete_view(uids=files[0].UID())
        view()
        assert [item["uid"] for item in view.items] == [files[0].UID()]

    def test_confirmation_page_lists_items_and_total(self, delete_view, files):
        view = delete_view(*(obj.UID() for obj in files))
        html = " ".join(view().split())
        assert (
            "Do you really want to delete the following 2 items (3.0 MB in total)?"
            in html
        )
        for obj in files:
            assert f'value="{obj.UID()}"' in html
        assert 'name="form.button.confirm"' in html
        assert 'id="quota-delete-breaches"' not in html
        assert 'id="quota-delete-skipped"' not in html
        # Nothing was deleted yet.
        assert get_total_usage() == 3 * MB

    def test_unknown_uids(self, delete_view):
        html = delete_view("missing")()
        assert "None of the selected items exist any more." in html
        assert 'name="form.button.confirm"' not in html

    def test_cancel_redirects(self, portal, http_request, delete_view, files):
        delete_view(files[0].UID(), **{"form.button.cancel": "Cancel"})()
        assert redirected_to_usage(portal, http_request)
        assert "a" in portal


class TestLinkIntegrity:
    @pytest.fixture
    def linked(self, portal, files):
        with api.env.adopt_roles(["Manager"]):
            doc = api.content.create(portal, "Document", id="doc", title="Linking doc")
            set_text(doc, f'<a href="resolveuid/{files[0].UID()}">a</a>')
        return doc

    def test_linkintegrity_breach_warning_rendered(self, delete_view, files, linked):
        html = re.sub(r"\s+>", ">", delete_view(files[0].UID())())
        assert 'class="alert alert-warning" id="quota-delete-breaches"' in html
        assert "Potential link breakage" in html
        assert "Linking doc" in html

    def test_no_warning_when_source_deleted_too(self, delete_view, files, linked):
        html = delete_view(files[0].UID(), linked.UID())()
        assert 'id="quota-delete-breaches"' not in html

    def test_no_warning_when_linkintegrity_disabled(self, delete_view, files, linked):
        api.portal.set_registry_record("plone.enable_link_integrity_checks", False)
        html = delete_view(files[0].UID())()
        assert 'id="quota-delete-breaches"' not in html

    def test_folder_contents_overview(self, portal, delete_view, make_file):
        with api.env.adopt_roles(["Manager"]):
            folder = api.content.create(portal, "Folder", id="folder", title="F")
        make_file(folder, "inside", MB)
        html = delete_view(folder.UID())()
        assert "Deleting overview" in html

    def test_confirm_with_breach_deletes(self, portal, delete_view, files, linked):
        delete_view(files[0].UID(), confirm=True)()
        assert "a" not in portal


class TestConfirm:
    def test_confirm_deletes_and_updates_total(
        self, portal, http_request, delete_view, files, messages
    ):
        delete_view(*(obj.UID() for obj in files), confirm=True)()
        assert "a" not in portal
        assert "b" not in portal
        assert get_total_usage() == 0
        assert redirected_to_usage(portal, http_request)
        assert messages() == [("Deleted 2 items, freeing 3.0 MB.", "info")]

    @pytest.mark.parametrize("token", [False, "invalid"])
    def test_confirm_requires_authenticator(self, portal, delete_view, files, token):
        form = {} if token is False else {"_authenticator": token}
        view = delete_view(files[0].UID(), confirm=True, token=False, **form)
        with pytest.raises(Forbidden):
            view()
        assert "a" in portal

    def test_items_without_delete_permission_skipped_with_message(
        self, portal, delete_view, files, messages
    ):
        files[0].manage_permission("Delete objects", ["Manager"], acquire=False)
        view = delete_view(*(obj.UID() for obj in files))
        html = view()
        assert 'id="quota-delete-skipped"' in html
        assert "you are not allowed to delete it" in html
        assert [item["uid"] for item in view.items] == [files[1].UID()]

        delete_view(confirm=True)()
        assert "a" in portal
        assert "b" not in portal
        assert messages() == [
            ("Deleted 1 items, freeing 2.0 MB.", "info"),
            ("Skipped a: you are not allowed to delete it.", "warning"),
        ]

    def test_only_skipped_items(self, portal, delete_view, files, messages):
        files[0].manage_permission("Delete objects", ["Manager"], acquire=False)
        html = delete_view(files[0].UID())()
        assert 'name="form.button.confirm"' not in html
        assert 'id="quota-delete-skipped"' in html
        delete_view(confirm=True)()
        assert "a" in portal
        assert messages() == [
            ("Skipped a: you are not allowed to delete it.", "warning")
        ]

    @pytest.fixture
    def page(self, portal):
        """A lockable item (File has no locking behavior)."""
        with api.env.adopt_roles(["Manager"]):
            return api.content.create(portal, "Document", id="page", title="Page")

    def test_locked_by_other_user_skipped(self, portal, delete_view, page, messages):
        portal.acl_users.userFolderAddUser("other", "secret", ["Editor"], [])
        login(portal, "other")
        ILockable(page).lock()
        login(portal, TEST_USER_NAME)
        delete_view(page.UID(), confirm=True)()
        assert "page" in portal
        assert messages() == [
            ("Skipped Page: it is locked by another user.", "warning")
        ]

    def test_locked_by_current_user_unlocked_and_deleted(
        self, portal, delete_view, page
    ):
        ILockable(page).lock()
        delete_view(page.UID(), confirm=True)()
        assert "page" not in portal

    def test_unlocked_lockable_deleted(self, portal, delete_view, page):
        delete_view(page.UID(), confirm=True)()
        assert "page" not in portal

    def test_without_index_sizes_are_zero(self, portal, delete_view, files, messages):
        portal.portal_catalog.delIndex("blob_size")
        view = delete_view(files[0].UID())
        view()
        assert view.items[0]["size"] == 0
        delete_view(confirm=True)()
        assert "a" not in portal
        assert messages() == [("Deleted 1 items, freeing 0 KB.", "info")]


class TestBrowserFlow:
    def test_delete_from_listing_over_limit_commits(
        self, browser, functional_portal, make_file, set_quota
    ):
        """Deleting never adds bytes: the commit guard lets it through even
        while the site is over its hard limit."""
        make_file(functional_portal, "a", 2 * MB)
        make_file(functional_portal, "b", MB)
        make_file(functional_portal, "c", 512)
        set_quota(hard_mb=1, policy="block_all")
        transaction.commit()
        uids = {o: functional_portal[o].UID() for o in "abc"}

        test_browser = browser("Editor")
        test_browser.open(f"{functional_portal.absolute_url()}/@@quota-usage")
        form = test_browser.getForm(id="quota-usage-form")
        form.getControl(name="uids:list").value = [uids["a"], uids["b"]]
        form.submit()
        assert "@@quota-delete" in test_browser.url
        assert "following 2 items (3.0 MB in total)" in " ".join(
            test_browser.contents.split()
        )
        test_browser.getControl(name="form.button.confirm").click()
        assert test_browser.url.endswith("/@@quota-usage")
        assert "Deleted 2 items, freeing 3.0 MB." in test_browser.contents

        transaction.begin()  # see the server's commit
        assert sorted(o for o in "abc" if o in functional_portal.objectIds()) == ["c"]

    def test_single_delete_link(self, browser, functional_portal, make_file):
        make_file(functional_portal, "a", MB)
        transaction.commit()
        test_browser = browser("Editor")
        test_browser.open(f"{functional_portal.absolute_url()}/@@quota-usage")
        link = test_browser.getLink(url="@@quota-delete?uids:list=")
        link.click()
        assert re.search(r"following\s+1\s+items", test_browser.contents)
        test_browser.getControl(name="form.button.cancel").click()
        assert test_browser.url.endswith("/@@quota-usage")
