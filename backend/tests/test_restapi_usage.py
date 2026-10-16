"""GET @quota-usage."""

from plone import api

import pytest
import transaction


MB = 1024 * 1024
URL = "/@quota-usage"

SUMMARY_KEYS = {
    "@id",
    "total",
    "total_human",
    "soft",
    "soft_human",
    "hard",
    "hard_human",
    "percent",
    "level",
    "limits_configured",
    "message",
    "policy",
    "policy_title",
    "policy_hint",
    "can_manage",
}


@pytest.fixture
def site(functional_portal, make_file, set_quota):
    def func(files=None, **quota):
        for name, size in (files or {}).items():
            make_file(functional_portal, name, size)
        set_quota(**quota)
        transaction.commit()
        return functional_portal

    return func


class TestPermissions:
    def test_anonymous_401(self, api_session):
        assert api_session("Anonymous").get(URL).status_code == 401

    def test_member_401(self, api_session):
        # plone.restapi answers 401 for an authenticated user lacking the
        # service permission, as for every other service.
        assert api_session("Member").get(URL).status_code == 401

    @pytest.mark.parametrize("role", ["Editor", "Contributor", "Reviewer"])
    def test_allowed(self, api_session, role):
        assert api_session(role).get(URL).status_code == 200

    def test_not_on_content(self, api_session, functional_portal):
        with api.env.adopt_roles(["Manager"]):
            api.content.create(functional_portal, "Folder", id="folder")
        transaction.commit()
        assert api_session().get(f"/folder{URL}").status_code == 404


class TestShape:
    def test_editor(self, api_session, site):
        portal = site(files={"a": 2 * MB}, soft_mb=4096, hard_mb=5120)
        body = api_session("Editor").get(URL).json()
        portal_url = portal.absolute_url()
        assert set(body) == SUMMARY_KEYS | {"limit", "limits", "items"}
        assert body["@id"] == f"{portal_url}/@quota-usage"
        assert body["total"] == 2 * MB
        assert body["total_human"] == "2.0 MB"
        assert body["soft"] == 4096 * MB
        assert body["soft_human"] == "4.0 GB"
        assert body["hard"] == 5120 * MB
        assert body["hard_human"] == "5.0 GB"
        assert body["percent"] == 0
        assert body["level"] == "ok"
        assert body["limits_configured"] is True
        assert body["message"] is None
        assert body["policy"] == "block_all"
        assert body["policy_title"] == "Block new items and any upload that adds bytes"
        assert body["policy_hint"] == (
            "New content and uploads are blocked until files are removed."
        )
        assert body["can_manage"] is False
        assert body["limit"] == 25
        assert body["limits"] == [10, 25, 50, 100]

    def test_admin_can_manage(self, api_session, site):
        portal = site()
        body = api_session().get(URL).json()
        assert body["can_manage"] is True
        assert body["controlpanel"] == (
            f"{portal.absolute_url()}/@controlpanels/collective-quota"
        )

    def test_item(self, api_session, site):
        portal = site(files={"a": 2 * MB})
        transaction.begin()
        obj = portal["a"]
        [item] = api_session("Editor").get(URL).json()["items"]
        modified = item.pop("modified")
        assert modified.startswith(obj.modified().asdatetime().strftime("%Y-%m-%dT"))
        assert "+00:00" in modified or modified.endswith("Z")
        assert item == {
            "@id": obj.absolute_url(),
            "UID": obj.UID(),
            "title": "a",
            "@type": "File",
            "type_title": "File",
            "parent": {"@id": portal.absolute_url(), "title": "Plone site"},
            "blob_size": 2 * MB,
            "blob_size_human": "2.0 MB",
            "can_delete": True,
        }

    @pytest.mark.parametrize(
        "query,limit,count", [("", 25, 30), ("?limit=10", 10, 10), ("?limit=7", 25, 30)]
    )
    def test_limit(self, api_session, site, query, limit, count):
        site(files={f"f{i:02}": 1000 + i for i in range(30)})
        body = api_session("Editor").get(f"{URL}{query}").json()
        assert body["limit"] == limit
        assert len(body["items"]) == min(count, limit)
        sizes = [item["blob_size"] for item in body["items"]]
        assert sizes == sorted(sizes, reverse=True)


class TestLevels:
    def test_no_limits(self, api_session, site):
        site(files={"a": 1000})
        body = api_session("Editor").get(URL).json()
        assert body["limits_configured"] is False
        assert body["level"] == "ok"
        assert body["soft"] == body["hard"] == 0
        for key in ("message", "percent", "policy_hint", "soft_human", "hard_human"):
            assert body[key] is None
        assert body["policy"] == "block_all"
        assert [item["@id"].rsplit("/", 1)[-1] for item in body["items"]] == ["a"]

    def test_soft_only(self, api_session, site):
        site(files={"a": 3 * MB}, soft_mb=2)
        body = api_session("Editor").get(URL).json()
        assert body["limits_configured"] is True
        assert body["level"] == "warning"
        assert body["percent"] is None
        assert body["policy_hint"] is None
        assert body["message"].startswith(
            "Disk usage warning: this site uses 3.0 MB of 2.0 MB (150%)."
        )

    def test_warning(self, api_session, site):
        site(files={"a": 3 * MB}, soft_mb=2, hard_mb=10, policy="block_files")
        body = api_session("Editor").get(URL).json()
        assert body["level"] == "warning"
        assert body["percent"] == 30
        assert body["message"].startswith(
            "Disk usage warning: this site uses 3.0 MB of 10.0 MB (30%)."
        )
        assert body["policy_hint"] == "Uploads are blocked until files are removed."

    def test_exceeded(self, api_session, site):
        site(files={"a": 3 * MB}, hard_mb=2, policy="limit_file_size", max_file_mb=1)
        body = api_session("Editor").get(URL).json()
        assert body["level"] == "exceeded"
        assert body["percent"] == 150
        assert body["message"] == (
            "Disk quota exceeded: this site uses 3.0 MB of 2.0 MB. Only files up "
            "to 1.0 MB can be uploaded until files are removed."
        )
