"""Tests for code that ships with the cookieplone scaffold."""

from collective.quota.setuphandlers import HiddenProfiles
from plone.restapi.interfaces import IJSONSummarySerializerMetadata
from zope.component import getUtility


def test_summary_serializer_metadata(portal):
    utility = getUtility(
        IJSONSummarySerializerMetadata,
        name="collective.quota.summary_serializer_metadata",
    )
    assert utility.default_metadata_fields() == {
        "image_field",
        "image_scales",
        "effective",
        "Subject",
    }


def test_hidden_profiles():
    hidden = HiddenProfiles()
    assert hidden.getNonInstallableProfiles() == ["collective.quota:uninstall"]
    assert hidden.getNonInstallableProducts() == ["collective.quota.upgrades"]
