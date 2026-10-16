"""POST @quota-rebuild."""

from BTrees.Length import Length
from collective.quota.usage import get_index
from collective.quota.usage import get_total_usage

import pytest
import transaction


URL = "/@quota-rebuild"


class TestRebuild:
    def test_admin(self, api_session, functional_portal, make_file):
        make_file(functional_portal, "a", 2048)
        make_file(functional_portal, "b", 1024)
        get_total_usage(functional_portal)
        get_index(functional_portal)._total = Length(1)  # out of sync
        transaction.commit()
        response = api_session().post(URL)
        assert response.status_code == 200
        body = response.json()
        transaction.begin()
        assert body["total"] == get_total_usage(functional_portal) == 3072
        assert body["total_human"] == "3.0 KB"
        assert body["items"] >= 2

    @pytest.mark.parametrize("role", ["Editor", "Anonymous"])
    def test_requires_permission(self, api_session, role):
        assert api_session(role).post(URL).status_code == 401

    def test_get_not_allowed(self, api_session):
        assert api_session().get(URL).status_code != 200
