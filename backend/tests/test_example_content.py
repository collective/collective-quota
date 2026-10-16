"""The ``initial`` profile imports a small Classic sample.

plone.exportimport commits while importing, so these tests use the functional
layer, whose storage is thrown away after each test.
"""

from collective.quota.usage import get_total_usage
from plone import api

import pytest
import transaction


KB = 1024


@pytest.fixture
def imported(functional_portal, set_quota):
    # Over the hard limit already: the import must still go in.
    set_quota(hard_mb=1, policy="block_all")
    setup_tool = functional_portal.portal_setup
    setup_tool.runAllImportStepsFromProfile("profile-collective.quota:initial")
    transaction.commit()
    return functional_portal


def test_content_created(imported):
    assert sorted(imported["media"].objectIds()) == [
        "annual-report",
        "banner",
        "dataset",
    ]
    assert imported["about-the-quota"].portal_type == "Document"


def test_files_indexed(imported):
    brains = imported.portal_catalog(
        blob_size={"query": 1, "range": "min"},
        sort_on="blob_size",
        sort_order="descending",
    )
    assert [b.getId for b in brains] == ["annual-report", "dataset", "banner"]
    assert brains[0].blob_size == 2048 * KB
    assert brains[1].blob_size == 500 * KB
    assert get_total_usage(imported) == sum(b.blob_size for b in brains)


def test_document_links_to_report(imported, browser):
    uid = imported["media"]["annual-report"].UID()
    test_browser = browser("Editor")
    test_browser.open(f"{imported.absolute_url()}/@@quota-delete?uids:list={uid}")
    assert 'id="quota-delete-breaches"' in test_browser.contents
    assert "About the quota" in test_browser.contents


def test_published(imported):
    for path in ("media", "media/annual-report", "about-the-quota"):
        obj = imported.unrestrictedTraverse(path)
        assert api.content.get_state(obj, default=None) in (None, "published")
