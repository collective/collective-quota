"""Sanity checks for the shared test fixtures in conftest.py."""

from collective.quota.testing import MULTI_BLOB_TYPE
from plone import api
from plone.app.testing import TEST_USER_ID

import os
import pytest


MB = 1024 * 1024


class TestContentFixtures:
    def test_multi_blob_type(self, portal, make_blob):
        with api.env.adopt_roles(["Manager"]):
            obj = api.content.create(
                container=portal,
                type=MULTI_BLOB_TYPE,
                title="Multi",
                attachment=make_blob(1000),
                picture=make_blob(2000, filename="p.png", image=True),
                second=make_blob(3000),
            )
        assert obj.portal_type == MULTI_BLOB_TYPE
        assert obj.attachment.getSize() == 1000
        assert obj.picture.getSize() == 2000
        assert obj.picture.getImageSize() == (1, 1)
        assert obj.second.getSize() == 3000

    def test_document_has_leadimage(self, portal):
        assert "plone.leadimage" in portal.portal_types["Document"].behaviors

    def test_make_file(self, portal, make_file):
        obj = make_file(portal, "f1", 2 * MB)
        assert obj.portal_type == "File"
        assert obj.file.getSize() == 2 * MB
        assert obj.file.filename == "f1.bin"

    def test_make_image(self, portal, make_image):
        obj = make_image(portal, "i1", 5000)
        assert obj.portal_type == "Image"
        assert obj.image.getSize() == 5000
        assert obj.image.getImageSize() == (1, 1)
        assert obj.image.filename == "i1.png"

    def test_make_blob_image_too_small(self, make_blob):
        with pytest.raises(ValueError, match="at least"):
            make_blob(10, image=True)


class TestQuotaEnv:
    NAMES = (
        "COLLECTIVE_QUOTA_SOFT_LIMIT_MB",
        "COLLECTIVE_QUOTA_HARD_LIMIT_MB",
        "COLLECTIVE_QUOTA_OVER_LIMIT_POLICY",
        "COLLECTIVE_QUOTA_MAX_FILE_SIZE_MB",
        "COLLECTIVE_QUOTA_LOCK_SETTINGS",
    )

    def test_autouse_clears(self):
        for name in self.NAMES:
            assert name not in os.environ

    def test_sets_all(self, quota_env):
        quota_env(soft=1, hard=2, policy="allow", max_file=3, lock="yes")
        assert [os.environ[n] for n in self.NAMES] == ["1", "2", "allow", "3", "yes"]

    def test_clears_previous(self, quota_env):
        quota_env(soft=1, hard=2)
        quota_env(hard=5)
        assert "COLLECTIVE_QUOTA_SOFT_LIMIT_MB" not in os.environ
        assert os.environ["COLLECTIVE_QUOTA_HARD_LIMIT_MB"] == "5"

    def test_unknown_argument(self, quota_env):
        with pytest.raises(TypeError, match="hardd"):
            quota_env(hardd=1)


class TestFunctionalFixtures:
    @pytest.mark.parametrize(
        "role,marker",
        [
            ("Manager", 'id="personaltools-logout"'),
            ("Editor", 'id="personaltools-logout"'),
            ("Anonymous", 'id="personaltools-login"'),
        ],
    )
    def test_browser(self, browser, functional_portal, role, marker):
        test_browser = browser(role)
        test_browser.open(functional_portal.absolute_url())
        assert marker in test_browser.contents

    def test_browser_role_granted(self, browser, functional_portal):
        browser("Editor")
        roles = api.user.get_roles(username=TEST_USER_ID, obj=functional_portal)
        assert "Editor" in roles

    @pytest.mark.parametrize(
        "role,status", [("Manager", 200), ("Editor", 200), ("Anonymous", 401)]
    )
    def test_api_session(self, api_session, role, status):
        response = api_session(role).get(f"/@users/{TEST_USER_ID}")
        assert response.status_code == status


class TestSetQuota:
    def test_set_quota_writes_all_records(self, portal, set_quota):
        set_quota(soft_mb=1, hard_mb=2, policy="allow", max_file_mb=3)
        values = {
            name: api.portal.get_registry_record(f"collective.quota.{name}")
            for name in (
                "soft_limit_mb",
                "hard_limit_mb",
                "over_limit_policy",
                "max_file_size_mb",
            )
        }
        assert values == {
            "soft_limit_mb": 1,
            "hard_limit_mb": 2,
            "over_limit_policy": "allow",
            "max_file_size_mb": 3,
        }

    def test_set_quota_defaults(self, portal, set_quota):
        set_quota()
        assert api.portal.get_registry_record("collective.quota.max_file_size_mb") == 10
        assert api.portal.get_registry_record("collective.quota.over_limit_policy") == (
            "block_all"
        )
