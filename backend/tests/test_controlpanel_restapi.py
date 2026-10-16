"""REST control panel: @controlpanels/collective-quota."""

from collective.quota.settings import FIELDS

import pytest
import transaction


URL = "/@controlpanels/collective-quota"
SOFT_ABOVE_HARD = "The soft limit cannot be higher than the hard limit."


class TestGet:
    def test_get(self, api_session):
        response = api_session().get(URL)
        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "Quota"
        assert body["group"] == "Add-on Configuration"
        assert set(body["schema"]["properties"]) == set(FIELDS)
        assert body["data"] == dict.fromkeys(FIELDS)

    def test_listed(self, api_session):
        response = api_session().get("/@controlpanels")
        assert response.status_code == 200
        panels = {panel["@id"].rsplit("/", 1)[-1]: panel for panel in response.json()}
        assert panels["collective-quota"]["group"] == "Add-on Configuration"

    def test_get_without_configlet(self, api_session, functional_portal):
        """A site whose configlet is missing still serves the panel."""
        functional_portal.portal_controlpanel.unregisterConfiglet("collective-quota")
        transaction.commit()
        response = api_session().get(URL)
        assert response.status_code == 200
        assert response.json()["group"] == "Products"

    def test_get_exposes_effective_values_sources_and_locked(
        self, api_session, functional_portal, quota_env, set_quota
    ):
        quota_env(hard=100, soft=5, policy="block_files", lock="1")
        set_quota(soft_mb=None, hard_mb=20, policy=None, max_file_mb=3)
        transaction.commit()
        body = api_session().get(URL).json()
        # Locked fields show the environment value, the others what is stored.
        assert body["data"] == {
            "soft_limit_mb": 5,
            "hard_limit_mb": 100,
            "over_limit_policy": {
                "token": "block_files",
                "title": "Allow new items, block uploads that add bytes",
            },
            "max_file_size_mb": 3,
        }
        assert body["effective"] == {
            "soft_limit_mb": 5,
            "hard_limit_mb": 100,
            "over_limit_policy": "block_files",
            "max_file_size_mb": 3,
        }
        assert body["sources"] == {
            "soft_limit_mb": "env-locked",
            "hard_limit_mb": "env-locked",
            "over_limit_policy": "env-locked",
            "max_file_size_mb": "registry",
        }
        assert body["locked"] == [
            "hard_limit_mb",
            "over_limit_policy",
            "soft_limit_mb",
        ]
        properties = body["schema"]["properties"]
        assert properties["hard_limit_mb"]["readonly"] is True
        assert properties["over_limit_policy"]["readonly"] is True
        assert "readonly" not in properties["max_file_size_mb"]

    def test_get_unset_values_are_null(self, api_session, quota_env):
        quota_env(hard=100)  # not locked: data keeps what is stored
        body = api_session().get(URL).json()
        assert body["data"]["hard_limit_mb"] is None
        assert body["effective"]["hard_limit_mb"] == 100
        assert body["sources"]["hard_limit_mb"] == "env"
        assert body["locked"] == []

    @pytest.mark.parametrize("role,status", [("Editor", 401), ("Anonymous", 401)])
    def test_get_requires_permission(self, api_session, role, status):
        assert api_session(role).get(URL).status_code == status


class TestPatch:
    def test_patch(self, stored_settings, api_session):
        response = api_session().patch(URL, json={"hard_limit_mb": 200})
        assert response.status_code == 204
        assert stored_settings()["hard_limit_mb"] == 200

    def test_patch_site_administrator(self, stored_settings, api_session):
        response = api_session("Site Administrator").patch(
            URL, json={"over_limit_policy": "block_files"}
        )
        assert response.status_code == 204
        assert stored_settings()["over_limit_policy"] == "block_files"

    @pytest.mark.parametrize("role", ["Editor", "Anonymous"])
    def test_patch_requires_permission(self, stored_settings, api_session, role):
        response = api_session(role).patch(URL, json={"hard_limit_mb": 200})
        assert response.status_code == 401
        assert stored_settings()["hard_limit_mb"] is None

    def test_patch_null_clears_value(self, stored_settings, api_session, set_quota):
        set_quota(hard_mb=50)
        transaction.commit()
        response = api_session().patch(URL, json={"hard_limit_mb": None})
        assert response.status_code == 204
        assert stored_settings()["hard_limit_mb"] is None

    def test_patch_locked_field_rejected_400_nothing_written(
        self, stored_settings, api_session, quota_env
    ):
        quota_env(hard=100, lock="1")
        response = api_session().patch(
            URL, json={"hard_limit_mb": 500, "soft_limit_mb": 10}
        )
        assert response.status_code == 400
        assert (
            "Setting hard_limit_mb is locked by environment variable "
            "COLLECTIVE_QUOTA_HARD_LIMIT_MB" in response.text
        )
        assert stored_settings() == dict.fromkeys(FIELDS)

    def test_patch_locked_field_with_locked_value_ignored(
        self, stored_settings, api_session, quota_env
    ):
        """Clients that send the whole form back are not refused."""
        quota_env(hard=100, lock="1")
        response = api_session().patch(
            URL, json={"hard_limit_mb": 100, "soft_limit_mb": 10}
        )
        assert response.status_code == 204
        values = stored_settings()
        assert values["hard_limit_mb"] is None  # never written
        assert values["soft_limit_mb"] == 10

    def test_patch_invariants_on_effective_values(
        self, stored_settings, api_session, quota_env
    ):
        quota_env(hard=100, lock="1")
        response = api_session().patch(URL, json={"soft_limit_mb": 200})
        assert response.status_code == 400
        assert SOFT_ABOVE_HARD in response.text
        assert stored_settings() == dict.fromkeys(FIELDS)

    def test_patch_invariants_against_stored_values(
        self, stored_settings, api_session, set_quota
    ):
        set_quota(
            soft_mb=None, hard_mb=None, policy="limit_file_size", max_file_mb=None
        )
        transaction.commit()
        response = api_session().patch(URL, json={"max_file_size_mb": 0})
        assert response.status_code == 400
        assert "Set a maximum file size greater than 0 for this policy." in (
            response.text
        )
        assert stored_settings()["max_file_size_mb"] is None

    @pytest.mark.parametrize(
        "payload",
        [
            {"hard_limit_mb": -5},
            {"hard_limit_mb": "lots"},
            {"over_limit_policy": "nope"},
        ],
    )
    def test_patch_invalid_field_value(self, stored_settings, api_session, payload):
        response = api_session().patch(URL, json={**payload, "soft_limit_mb": 1})
        assert response.status_code == 400
        assert stored_settings() == dict.fromkeys(FIELDS)


class TestDeserializerUnit:
    def test_unmasked_errors_keep_exception(self, portal, http_request, quota_env):
        from collective.quota.controlpanels.restapi import QuotaConfigletPanel
        from collective.quota.controlpanels.restapi import (
            QuotaControlpanelDeserializeFromJson,
        )
        from zExceptions import BadRequest
        from zope.schema.interfaces import ValidationError

        import json

        http_request["BODY"] = json.dumps({"hard_limit_mb": -1}).encode()
        panel = QuotaConfigletPanel(portal, http_request)
        deserializer = QuotaControlpanelDeserializeFromJson(panel)
        with pytest.raises(BadRequest) as excinfo:
            deserializer(mask_validation_errors=False)
        (error,) = excinfo.value.args[0]
        assert isinstance(error["error"], ValidationError)
        assert error["field"] == "hard_limit_mb"
