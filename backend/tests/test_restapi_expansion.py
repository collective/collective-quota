"""The ``quota`` expansion element."""

from collective.quota import PACKAGE_NAME
from plone import api
from plone.base.utils import get_installer

import pytest
import transaction


MB = 1024 * 1024


@pytest.fixture
def folder(functional_portal):
    with api.env.adopt_roles(["Manager"]):
        api.content.create(functional_portal, "Folder", id="folder", title="F")
        api.content.transition(obj=functional_portal["folder"], transition="publish")
    transaction.commit()
    return functional_portal["folder"]


def components(session, path, expand=False):
    response = session.get(path, params={"expand": "quota"} if expand else None)
    assert response.status_code == 200
    return response.json()["@components"]


class TestExpansion:
    def test_not_expanded(self, api_session, folder, functional_portal):
        quota = components(api_session("Editor"), "/folder")["quota"]
        assert quota == {"@id": f"{functional_portal.absolute_url()}/@quota-usage"}

    def test_expanded(self, api_session, folder, functional_portal, set_quota):
        set_quota(soft_mb=1, hard_mb=10)
        transaction.commit()
        quota = components(api_session("Editor"), "/folder", expand=True)["quota"]
        assert quota["@id"] == f"{functional_portal.absolute_url()}/@quota-usage"
        assert quota["level"] == "ok"
        assert quota["limits_configured"] is True
        assert quota["can_manage"] is False
        assert "items" not in quota
        assert "limit" not in quota

    def test_expanded_with_other_elements(self, api_session, folder):
        response = api_session("Editor").get(
            "/folder", params={"expand": "navroot,quota"}
        )
        result = response.json()["@components"]
        assert "level" in result["quota"]
        assert "navroot" in result["navroot"]

    def test_site_root(self, api_session, functional_portal):
        quota = components(api_session(), "", expand=True)["quota"]
        assert quota["can_manage"] is True
        assert "controlpanel" in quota

    @pytest.mark.parametrize("role", ["Anonymous", "Member"])
    @pytest.mark.parametrize("expand", [False, True])
    def test_no_key_without_permission(self, api_session, folder, role, expand):
        assert "quota" not in components(api_session(role), "/folder", expand)

    def test_no_key_after_uninstall(self, api_session, folder, functional_portal):
        get_installer(functional_portal).uninstall_product(PACKAGE_NAME)
        transaction.commit()
        result = components(api_session(), "/folder", expand=True)
        assert "quota" not in result
