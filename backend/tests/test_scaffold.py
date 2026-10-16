"""Tests for code that ships with the cookieplone scaffold."""

from collective.quota.setuphandlers import HiddenProfiles
from pathlib import Path
from plone.restapi.interfaces import IJSONSummarySerializerMetadata
from zope.component import getUtility

import tomllib


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


def test_plone_volto_only_an_acceptance_extra():
    """The backend stands alone: plone.volto is never a runtime dependency."""
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    project = tomllib.loads(pyproject.read_text())["project"]
    assert not [d for d in project["dependencies"] if d.startswith("plone.volto")]
    assert project["optional-dependencies"]["acceptance"] == ["plone.volto"]
