from collective.quota.catalog.blob_size_index import BlobSizeIndex
from collective.quota.catalog.blob_size_index import manage_addBlobSizeIndex
from plone import api
from plone.app.testing import SITE_OWNER_NAME
from plone.testing.zope import login

import Products


def test_class_registered_as_product_meta_type():
    names = [m["name"] for m in Products.meta_types]
    assert "BlobSizeIndex" in names


def test_manage_add_index(portal):
    catalog = api.portal.get_tool("portal_catalog")
    manage_addBlobSizeIndex(catalog, "blob_size_2")
    index = catalog._catalog.getIndex("blob_size_2")
    assert isinstance(index, BlobSizeIndex)
    assert index.meta_type == "BlobSizeIndex"


def test_listed_in_available_indexes(portal):
    catalog = api.portal.get_tool("portal_catalog")
    with api.env.adopt_roles(["Manager"]):
        assert "BlobSizeIndex" in [m["name"] for m in catalog.availableIndexes()]


def test_add_form_renders(app, portal):
    login(app.acl_users, SITE_OWNER_NAME)
    catalog = api.portal.get_tool("portal_catalog")
    dispatcher = catalog.Indexes.manage_addProduct["collective.quota"]
    html = dispatcher.manage_addBlobSizeIndexForm()
    assert 'action="manage_addBlobSizeIndex"' in html
