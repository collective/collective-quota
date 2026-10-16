"""QuotaUploadValidator edge cases (hook A), called directly."""

from collective.quota.guard import get_ledger
from collective.quota.guard import guard_suspended
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
    def test_skipped_while_guard_suspended(self, over_limit, make_blob):
        field = file_field(over_limit)
        with guard_suspended():
            QuotaUploadValidator(field, make_blob(2 * MB))()
        with pytest.raises(QuotaExceeded):
            QuotaUploadValidator(field, make_blob(2 * MB))()

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


class TestRestDeserializerSuspended:
    """Hook C: plone.exportimport creates items through the REST deserializer."""

    @pytest.fixture
    def deserializer(self, portal, http_request, make_file, set_quota):
        from collective.quota.interfaces import IQuotaRestapiLayer
        from plone import api
        from plone.restapi.interfaces import IDeserializeFromJson
        from zope.component import getMultiAdapter
        from zope.interface import alsoProvides

        make_file(portal, "a", 2 * MB)
        set_quota(hard_mb=1, policy="block_all")
        alsoProvides(http_request, IQuotaRestapiLayer)
        with api.env.adopt_roles(["Manager"]):
            doc = api.content.create(portal, "Document", id="doc", title="Doc")
        return getMultiAdapter((doc, http_request), IDeserializeFromJson)

    def test_create_refused(self, deserializer):
        from zExceptions import BadRequest

        with pytest.raises(BadRequest):
            deserializer(data={"title": "New"}, create=True)

    def test_create_allowed_while_suspended(self, deserializer):
        with guard_suspended():
            deserializer(data={"title": "New"}, create=True)
        assert deserializer.context.title == "New"
