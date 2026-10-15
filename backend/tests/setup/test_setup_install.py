from collective.quota import PACKAGE_NAME

import pytest


class TestSetupInstall:
    def test_addon_installed(self, installer):
        """Test if collective.quota is installed."""
        assert installer.is_product_installed(PACKAGE_NAME) is True

    @pytest.mark.parametrize("name", ["IBrowserLayer", "IQuotaRestapiLayer"])
    def test_browserlayer(self, browser_layers, name):
        """Test that both browser layers are registered."""
        from collective.quota import interfaces

        assert getattr(interfaces, name) in browser_layers

    def test_latest_version(self, profile_last_version):
        """Test latest version of default profile."""
        assert profile_last_version(f"{PACKAGE_NAME}:default") == "1000"

    def test_plone_volto_not_installed(self, installer):
        """The add-on must work on a plain Classic site."""
        assert installer.is_product_installed("plone.volto") is False

    def test_restapi_installed(self, installer):
        """plone.restapi:default is a dependency (REST layer, permissions)."""
        assert installer.is_product_installed("plone.restapi") is True

    def test_blob_size_index_and_column(self, portal):
        """The blob_size index is a BlobSizeIndex and has a metadata column."""
        from collective.quota.catalog.blob_size_index import BlobSizeIndex

        catalog = portal.portal_catalog
        assert isinstance(catalog._catalog.getIndex("blob_size"), BlobSizeIndex)
        assert "blob_size" in catalog.schema()

    def test_configlet(self, portal):
        ids = [a.getId() for a in portal.portal_controlpanel.listActions()]
        assert "collective-quota" in ids
