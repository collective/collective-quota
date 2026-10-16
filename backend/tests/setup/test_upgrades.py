from BTrees.Length import Length
from collective.quota import PACKAGE_NAME
from collective.quota.upgrades import utils
from collective.quota.usage import get_index
from collective.quota.usage import get_total_usage

import pytest


@pytest.fixture
def setup_tool(portal):
    return portal.portal_setup


class TestUpgrades:
    def test_no_pending_steps_on_fresh_install(self, setup_tool):
        assert setup_tool.listUpgrades(f"{PACKAGE_NAME}:default") == []

    def test_profile_version_matches_metadata(self, setup_tool):
        assert setup_tool.getLastVersionForProfile(f"{PACKAGE_NAME}:default") == (
            "1000",
        )


class TestUtils:
    @pytest.mark.parametrize(
        "profile", ["collective.quota:default", "profile-collective.quota:default"]
    )
    def test_run_import_step(self, portal, setup_tool, profile):
        portal.portal_actions.user.manage_delObjects(["disk-usage"])
        utils.run_import_step(setup_tool, "actions", profile=profile)
        assert "disk-usage" in portal.portal_actions.user.objectIds()

    def test_run_import_step_default_profile(self, portal, setup_tool):
        catalog = portal.portal_catalog
        catalog.delColumn("blob_size")
        utils.run_import_step(setup_tool, "catalog")
        assert "blob_size" in catalog.schema()

    def test_rebuild_usage(self, portal, setup_tool, make_file):
        make_file(portal, "a", 2048)
        get_total_usage(portal)
        get_index(portal)._total = Length(1)
        assert utils.rebuild_usage(setup_tool) >= 1
        assert get_total_usage(portal) == 2048
