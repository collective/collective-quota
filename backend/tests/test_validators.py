"""QuotaUploadValidator edge cases (hook A), called directly."""

from collective.quota.guard import get_ledger
from collective.quota.policy import QuotaExceeded
from collective.quota.validators import QuotaUploadValidator
from plone.namedfile.field import NamedBlobFile

import pytest


MB = 1024 * 1024


@pytest.fixture
def over_limit(portal, make_file, set_quota):
    make_file(portal, "a", 2 * MB)
    set_quota(hard_mb=1, policy="block_files")
    return portal


def file_field(portal):
    return portal.portal_types["File"].lookupSchema()["file"]


class TestValidator:
    def test_none_and_non_file_values_skipped(self, over_limit):
        field = file_field(over_limit)
        assert QuotaUploadValidator(field, None)() is None
        assert QuotaUploadValidator(field, "not a file")() is None

    def test_unchanged_value_skipped(self, over_limit):
        obj = over_limit["a"]
        field = file_field(over_limit).bind(obj)
        QuotaUploadValidator(field, obj.file)()  # same object: no check

    def test_replace_on_bound_field_uses_old_size(self, over_limit, make_blob):
        obj = over_limit["a"]
        field = file_field(over_limit).bind(obj)
        QuotaUploadValidator(field, make_blob(MB))()  # smaller: allowed
        with pytest.raises(QuotaExceeded):
            QuotaUploadValidator(field, make_blob(3 * MB))()

    def test_field_without_interface_reads_attribute(self, over_limit, make_blob):
        obj = over_limit["a"]
        field = NamedBlobFile(__name__="file").bind(obj)
        assert field.interface is None
        QuotaUploadValidator(field, make_blob(MB))()  # old 2 MB from the attribute
        assert get_ledger().approved_bytes == 0

    def test_hard_limit_disabled(self, over_limit, set_quota, make_blob):
        set_quota(hard_mb=0)
        QuotaUploadValidator(file_field(over_limit), make_blob(5 * MB))()
        assert get_ledger().approved_bytes == 0

    def test_without_index(self, over_limit, make_blob):
        over_limit.portal_catalog.delIndex("blob_size")
        QuotaUploadValidator(file_field(over_limit), make_blob(5 * MB))()

    def test_without_site(self, over_limit, make_blob, monkeypatch):
        monkeypatch.setattr("collective.quota.validators.getSite", lambda: None)
        QuotaUploadValidator(file_field(over_limit), make_blob(5 * MB))()

    def test_allowed_upload_recorded(self, over_limit, set_quota, make_blob):
        set_quota(hard_mb=10)
        QuotaUploadValidator(file_field(over_limit), make_blob(MB))()
        assert get_ledger().approved_bytes == MB
