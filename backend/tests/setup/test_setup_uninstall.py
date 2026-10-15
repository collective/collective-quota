from collective.quota import PACKAGE_NAME

import pytest


class TestSetupUninstall:
    @pytest.fixture(autouse=True)
    def uninstalled(self, installer):
        installer.uninstall_product(PACKAGE_NAME)

    def test_addon_uninstalled(self, installer):
        """Test if collective.quota is uninstalled."""
        assert installer.is_product_installed(PACKAGE_NAME) is False

    @pytest.mark.parametrize("name", ["IBrowserLayer", "IQuotaRestapiLayer"])
    def test_browserlayer_not_registered(self, browser_layers, name):
        """Test that both browser layers are removed."""
        from collective.quota import interfaces

        assert getattr(interfaces, name) not in browser_layers
