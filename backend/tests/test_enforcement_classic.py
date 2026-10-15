"""Hooks A and B through Classic add/edit forms."""

from collective.quota.interfaces import IBrowserLayer
from collective.quota.usage import get_total_usage
from collective.quota.validators import _in_add_form
from z3c.form.interfaces import IAddForm
from zope.interface import alsoProvides
from zope.interface import implementer

import pytest
import transaction


MB = 1024 * 1024
KB = 1024
UPLOAD_BLOCKED = "This file cannot be saved: the site has reached its disk quota"
FILE_TOO_LARGE = "only files up to 10.0 MB can be added now. This file is 15.0 MB."
ADD_BLOCKED = "New content cannot be added: the site has reached its disk quota"


@pytest.fixture
def site(functional_portal, make_file, set_quota):
    def func(hard_mb=1, policy="block_files", max_file_mb=10, files=None):
        for name, size in (files or {}).items():
            make_file(functional_portal, name, size)
        set_quota(hard_mb=hard_mb, policy=policy, max_file_mb=max_file_mb)
        transaction.commit()
        return functional_portal

    return func


def total(portal):
    transaction.begin()
    return get_total_usage(portal)


def add_file(test_browser, portal, size, name="upload", field="form.widgets.file"):
    test_browser.open(f"{portal.absolute_url()}/++add++File")
    test_browser.getControl(name="form.widgets.title").value = name
    test_browser.getControl(name=field).add_file(
        b"\0" * size, "application/octet-stream", f"{name}.bin"
    )
    test_browser.getControl(name="form.buttons.save").click()


class TestUploads:
    def test_upload_over_limit_blocked_on_add_form(self, site, browser):
        portal = site(hard_mb=1)
        test_browser = browser("Contributor")
        add_file(test_browser, portal, 2 * MB)
        assert UPLOAD_BLOCKED in test_browser.contents
        assert "(0 KB of 1.0 MB)" in test_browser.contents
        transaction.begin()
        assert "upload.bin" not in portal.objectIds()
        assert total(portal) == 0

    def test_upload_within_limit_saved(self, site, browser):
        portal = site(hard_mb=1)
        test_browser = browser("Contributor")
        add_file(test_browser, portal, 500 * KB)
        assert UPLOAD_BLOCKED not in test_browser.contents
        transaction.begin()
        assert "upload.bin" in portal.objectIds()
        assert total(portal) == 500 * KB

    def test_edit_replace_with_smaller_allowed_when_over_limit(self, site, browser):
        portal = site(hard_mb=1, policy="block_all", files={"a": 2 * MB})
        test_browser = browser("Editor")
        test_browser.open(f"{portal.absolute_url()}/a/@@edit")
        test_browser.getControl(name="form.widgets.file.action").value = ["replace"]
        test_browser.getControl(name="form.widgets.file").add_file(
            b"\0" * (500 * KB), "application/octet-stream", "small.bin"
        )
        test_browser.getControl(name="form.buttons.save").click()
        assert "Changes saved" in test_browser.contents
        assert total(portal) == 500 * KB

    def test_edit_replace_with_bigger_blocked_when_over_limit(self, site, browser):
        portal = site(hard_mb=1, files={"a": 2 * MB})
        test_browser = browser("Editor")
        test_browser.open(f"{portal.absolute_url()}/a/@@edit")
        test_browser.getControl(name="form.widgets.file.action").value = ["replace"]
        test_browser.getControl(name="form.widgets.file").add_file(
            b"\0" * (3 * MB), "application/octet-stream", "big.bin"
        )
        test_browser.getControl(name="form.buttons.save").click()
        assert UPLOAD_BLOCKED in test_browser.contents
        assert total(portal) == 2 * MB

    def test_edit_keep_existing_file_allowed(self, site, browser):
        portal = site(hard_mb=1, policy="block_all", files={"a": 2 * MB})
        test_browser = browser("Editor")
        test_browser.open(f"{portal.absolute_url()}/a/@@edit")
        test_browser.getControl(name="form.widgets.title").value = "Renamed"
        assert test_browser.getControl(name="form.widgets.file.action").value == [
            "nochange"
        ]
        test_browser.getControl(name="form.buttons.save").click()
        assert "Changes saved" in test_browser.contents
        transaction.begin()
        assert portal["a"].title == "Renamed"

    @pytest.mark.parametrize("size,allowed", [(5 * MB, True), (15 * MB, False)])
    def test_limit_file_size_policy(self, site, browser, size, allowed):
        portal = site(hard_mb=1, policy="limit_file_size", files={"a": 2 * MB})
        test_browser = browser("Contributor")
        add_file(test_browser, portal, size)
        transaction.begin()
        assert ("upload.bin" in portal.objectIds()) is allowed
        assert (FILE_TOO_LARGE in test_browser.contents) is not allowed

    def test_lead_image_behavior_validated(self, site, browser, make_blob):
        portal = site(hard_mb=1, files={"a": 2 * MB})
        test_browser = browser("Contributor")
        test_browser.open(f"{portal.absolute_url()}/++add++Document")
        test_browser.getControl(name="form.widgets.IDublinCore.title").value = "Doc"
        image = make_blob(2 * MB, image=True)
        test_browser.getControl(name="form.widgets.ILeadImageBehavior.image").add_file(
            image.data, "image/png", "lead.png"
        )
        test_browser.getControl(name="form.buttons.save").click()
        assert UPLOAD_BLOCKED in test_browser.contents
        transaction.begin()
        assert "doc" not in portal.objectIds()

    def test_multi_field_type_each_field_validated(self, site, browser):
        portal = site(hard_mb=1)
        test_browser = browser("Contributor")
        test_browser.open(f"{portal.absolute_url()}/++add++quota_multi")
        test_browser.getControl(name="form.widgets.IBasic.title").value = "Multi"
        test_browser.getControl(name="form.widgets.title").value = "Multi"
        for name, size in (("attachment", 600 * KB), ("second", 600 * KB)):
            test_browser.getControl(name=f"form.widgets.{name}").add_file(
                b"\0" * size, "application/octet-stream", f"{name}.bin"
            )
        test_browser.getControl(name="form.buttons.save").click()
        # Each field alone fits under the limit, so both are approved: one save
        # may overshoot (documented limitation), the next one is blocked.
        transaction.begin()
        assert "multi" in portal.objectIds()
        assert total(portal) == 1200 * KB
        add_file(test_browser, portal, 1 * KB)
        assert UPLOAD_BLOCKED in test_browser.contents


class TestAddForm:
    @pytest.mark.parametrize(
        "policy,created", [("block_all", False), ("block_files", True)]
    )
    def test_block_all_blocks_document_add(self, site, browser, policy, created):
        portal = site(hard_mb=1, policy=policy, files={"a": 2 * MB})
        test_browser = browser("Contributor")
        test_browser.open(f"{portal.absolute_url()}/++add++Document")
        test_browser.getControl(name="form.widgets.IDublinCore.title").value = "Doc"
        test_browser.getControl(name="form.buttons.save").click()
        assert (ADD_BLOCKED in test_browser.contents) is not created
        assert test_browser.contents.count(ADD_BLOCKED) == (0 if created else 1)
        transaction.begin()
        assert ("doc" in portal.objectIds()) is created

    def test_add_allowed_under_the_limit(self, site, browser):
        portal = site(hard_mb=10, policy="block_all", files={"a": 2 * MB})
        test_browser = browser("Contributor")
        add_file(test_browser, portal, 100 * KB)
        transaction.begin()
        assert "upload.bin" in portal.objectIds()


class TestAddFormDetection:
    def test_in_add_form(self, http_request, monkeypatch):
        @implementer(IAddForm)
        class Form:
            pass

        class Wrapper:
            form_instance = Form()

        monkeypatch.setattr(
            "collective.quota.validators.getRequest", lambda: http_request
        )
        alsoProvides(http_request, IBrowserLayer)
        http_request["PUBLISHED"] = Wrapper()
        assert _in_add_form()
        http_request["PUBLISHED"] = Form()
        assert _in_add_form()
        http_request["PUBLISHED"] = object()
        assert not _in_add_form()

    def test_no_request(self, monkeypatch):
        monkeypatch.setattr("collective.quota.validators.getRequest", lambda: None)
        assert not _in_add_form()
