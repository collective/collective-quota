"""Commit guard with real commits (functional layer: commits are isolated)."""

from collective.quota import PACKAGE_NAME
from collective.quota.guard import check_quota
from collective.quota.guard import get_ledger
from collective.quota.guard import guard_suspended
from collective.quota.guard import QuotaCommitAborted
from collective.quota.testing import IMultiBlobSchema
from collective.quota.testing import MULTI_BLOB_TYPE
from collective.quota.usage import get_total_usage
from collective.quota.usage import rebuild_usage
from plone import api
from Products.CMFCore.indexing import processQueue
from Products.CMFPlone.utils import get_installer

import json
import pytest
import re
import transaction


MB = 1024 * 1024
KB = 1024


@pytest.fixture
def site(functional_portal, make_file, set_quota):
    """site(hard_mb, policy, files={id: bytes}) -> portal with committed content."""

    def func(hard_mb=1, policy="block_files", files=None, folder=False):
        for name, size in (files or {}).items():
            make_file(functional_portal, name, size)
        if folder:
            with api.env.adopt_roles(["Manager"]), guard_suspended():
                api.content.create(functional_portal, "Folder", id="folder", title="F")
        set_quota(hard_mb=hard_mb, policy=policy)
        transaction.commit()
        return functional_portal

    return func


@pytest.fixture
def manager(functional_portal):
    with api.env.adopt_roles(["Manager"]):
        yield


def commit_aborted(reason):
    with pytest.raises(QuotaCommitAborted) as excinfo:
        transaction.commit()
    transaction.abort()
    assert excinfo.value.reason == reason


def hooks():
    return [hook for hook, _a, _k in transaction.get().getBeforeCommitHooks()]


class TestBypassPaths:
    def test_plone_api_create_over_limit_aborted_on_commit(
        self, site, make_blob, manager
    ):
        portal = site(hard_mb=1)
        api.content.create(portal, "File", id="big", file=make_blob(2 * MB))
        commit_aborted("unapproved_bytes")
        assert "big" not in portal.objectIds()
        assert get_total_usage(portal) == 0

    def test_direct_attribute_write_and_reindex_aborted(self, site, make_blob, manager):
        """The reindex is queued: the hook is registered while the queue flushes."""
        portal = site(hard_mb=1, files={"small": 100 * KB})
        portal["small"].file = make_blob(2 * MB)
        portal["small"].reindexObject()
        assert check_quota not in hooks()
        commit_aborted("unapproved_bytes")
        assert portal["small"].file.getSize() == 100 * KB
        assert get_total_usage(portal) == 100 * KB

    def test_copy_paste_over_limit_aborted(self, site, manager):
        portal = site(hard_mb=1, files={"a": 600 * KB})
        api.content.copy(source=portal["a"], target=portal, id="b")
        commit_aborted("unapproved_bytes")
        assert "b" not in portal.objectIds()

    def test_copy_under_limit_allowed(self, site, manager):
        portal = site(hard_mb=2, files={"a": 600 * KB})
        api.content.copy(source=portal["a"], target=portal, id="b")
        transaction.commit()
        assert get_total_usage(portal) == 1200 * KB

    def test_move_and_rename_over_limit_allowed(self, site, manager):
        portal = site(hard_mb=1, files={"a": 2 * MB}, folder=True)
        api.content.move(source=portal["a"], target=portal["folder"])
        transaction.commit()
        api.content.rename(obj=portal["folder"]["a"], new_id="renamed")
        transaction.commit()
        assert "renamed" in portal["folder"].objectIds()
        assert get_total_usage(portal) == 2 * MB

    def test_delete_always_allowed_over_limit(self, site, manager):
        portal = site(hard_mb=1, policy="block_all", files={"a": 2 * MB, "b": MB})
        api.content.delete(obj=portal["a"])
        transaction.commit()
        assert get_total_usage(portal) == MB

    def test_allow_policy_never_aborts(self, site, make_blob, manager):
        portal = site(hard_mb=1, policy="allow", files={"a": 2 * MB})
        api.content.create(portal, "File", id="big", file=make_blob(2 * MB))
        api.content.create(portal, "Document", id="doc")
        transaction.commit()
        assert get_total_usage(portal) == 4 * MB

    def test_env_locked_hard_limit_enforced_by_guard(
        self, site, make_blob, manager, quota_env
    ):
        portal = site(hard_mb=0)
        quota_env(hard=1, lock="1")
        api.content.create(portal, "File", id="big", file=make_blob(2 * MB))
        commit_aborted("unapproved_bytes")


class TestApprovedPaths:
    def test_validated_upload_commits(self, site, make_blob, manager):
        """limit_file_size over the limit: a validated small file goes in."""
        portal = site(hard_mb=1, policy="limit_file_size", files={"a": 2 * MB})
        blob = make_blob(100 * KB)
        file_field = portal.portal_types["File"].lookupSchema()["file"]
        file_field.bind(portal).validate(blob)  # hook A approves
        assert get_ledger().approved_bytes == 100 * KB
        api.content.create(portal, "File", id="small", file=blob)
        transaction.commit()
        assert get_total_usage(portal) == 2 * MB + 100 * KB

    def test_unvalidated_small_upload_aborted(self, site, make_blob, manager):
        """Bypass paths get no approval, even for files under the cap."""
        portal = site(hard_mb=1, policy="limit_file_size", files={"a": 2 * MB})
        api.content.create(portal, "File", id="small", file=make_blob(100 * KB))
        commit_aborted("unapproved_bytes")

    def test_multi_field_form_net_delta_within_approvals(
        self, site, make_blob, manager
    ):
        portal = site(hard_mb=1, policy="limit_file_size", files={"a": 2 * MB})
        obj = api.content.create(portal, MULTI_BLOB_TYPE, id="multi", title="m")
        values = {
            "attachment": make_blob(100 * KB),
            "picture": make_blob(200 * KB, filename="p.png", image=True),
            "second": make_blob(300 * KB),
        }
        for name, value in values.items():
            IMultiBlobSchema[name].bind(obj).validate(value)
            setattr(obj, name, value)
        obj.reindexObject()
        transaction.commit()
        assert get_total_usage(portal) == 2 * MB + 600 * KB

    def test_block_all_unapproved_document_create_aborted_block_files_allowed(
        self, site, manager, set_quota
    ):
        portal = site(hard_mb=1, policy="block_all", files={"a": 2 * MB})
        api.content.create(portal, "Document", id="doc")
        commit_aborted("unapproved_items")
        assert "doc" not in portal.objectIds()
        set_quota(hard_mb=1, policy="block_files")
        transaction.commit()
        api.content.create(portal, "Document", id="doc")
        transaction.commit()
        assert "doc" in portal.objectIds()


class TestRebuild:
    def test_rebuild_usage_on_over_limit_site_succeeds(self, site):
        portal = site(hard_mb=1, policy="block_all", files={"a": 2 * MB, "b": MB})
        portal.portal_catalog._catalog.getIndex("blob_size").clear()
        transaction.commit()
        assert rebuild_usage(portal) == 3  # site root + 2 files
        transaction.commit()
        assert get_total_usage(portal) == 3 * MB

    def test_fresh_install_on_over_limit_site(
        self, functional_portal, make_blob, quota_env
    ):
        """3 MB of content exists before install; the environment says 1 MB."""
        installer = get_installer(functional_portal)
        installer.uninstall_product(PACKAGE_NAME)
        transaction.commit()
        quota_env(hard=1, policy="block_all", lock="1")
        with api.env.adopt_roles(["Manager"]):
            for i in range(3):
                api.content.create(
                    functional_portal, "File", id=f"f{i}", file=make_blob(MB)
                )
            processQueue()
            transaction.commit()
            installer.install_product(PACKAGE_NAME)
            transaction.commit()
        assert get_total_usage(functional_portal) == 3 * MB


class TestOverhead:
    def test_no_hook_registered_for_unrelated_transactions(
        self, functional_portal, manager
    ):
        with guard_suspended():
            api.content.create(functional_portal, "Document", id="doc", title="A")
            transaction.commit()
        doc = functional_portal["doc"]
        doc.title = "B"
        doc.reindexObject()
        processQueue()
        assert check_quota not in hooks()
        transaction.commit()


class TestErrorSurfaces:
    MESSAGE = (
        "The change was cancelled: it would add 600.0 KB to the site and exceed "
        "the disk quota (1.2 MB of 1.0 MB)."
    )

    @pytest.fixture
    def copied(self, site, browser):
        """browser(role) that copied ``a`` and will paste it over the limit."""
        portal = site(hard_mb=1, files={"a": 600 * KB})

        def func(accept=None):
            test_browser = browser("Contributor")
            test_browser.handleErrors = True
            test_browser.raiseHttpErrors = False
            if accept:
                test_browser.addHeader("Accept", accept)
            test_browser.open(portal.absolute_url())
            token = re.search(r'data-token="([^"]+)"', test_browser.contents).group(1)
            test_browser.open(
                f"{portal.absolute_url()}/a/object_copy?_authenticator={token}"
            )
            test_browser.open(
                f"{portal.absolute_url()}/object_paste?_authenticator={token}"
            )
            return portal, test_browser

        return func

    def test_rest_copy_over_limit_400(self, site, api_session):
        portal = site(hard_mb=1, files={"a": 600 * KB})
        response = api_session("Manager").post(
            "/@copy", json={"source": portal["a"].absolute_url()}
        )
        assert response.status_code == 400
        body = response.json()
        assert body["type"] == "QuotaCommitAborted"
        assert body["message"] == self.MESSAGE

    def test_classic_paste_shows_message_to_editors(self, copied):
        portal, test_browser = copied(accept="text/html")
        assert test_browser.headers["status"] == "400 Bad Request"
        assert "Disk quota exceeded" in test_browser.contents
        assert self.MESSAGE in test_browser.contents
        transaction.begin()
        assert "copy_of_a" not in portal.objectIds()

    def test_classic_json_when_html_not_accepted(self, copied):
        _portal, test_browser = copied()
        assert test_browser.headers["status"] == "400 Bad Request"
        assert json.loads(test_browser.contents) == {
            "error_type": "QuotaCommitAborted",
            "message": self.MESSAGE,
        }
