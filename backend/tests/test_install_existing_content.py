from collective.quota import PACKAGE_NAME
from collective.quota.usage import get_index
from collective.quota.usage import get_total_usage
from plone import api


def test_reinstall_populates_index_metadata_and_total(portal, installer, make_file):
    installer.uninstall_product(PACKAGE_NAME)
    catalog = api.portal.get_tool("portal_catalog")
    assert "blob_size" not in catalog.indexes()
    assert "blob_size" not in catalog.schema()

    make_file(portal, "a", 1000)
    make_file(portal, "b", 3000)
    assert get_total_usage(portal) == 0  # index missing

    installer.install_product(PACKAGE_NAME)
    assert get_index(portal) is not None
    assert get_total_usage(portal) == 4000
    brains = catalog(sort_on="blob_size", sort_order="descending", portal_type="File")
    assert [(b.getId, b.blob_size) for b in brains] == [("b", 3000), ("a", 1000)]
