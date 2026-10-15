"""Classic control panel: @@quota-controlpanel."""

from collective.quota.controlpanels.quota import QuotaControlPanelForm
from collective.quota.interfaces import IBrowserLayer
from collective.quota.settings import FIELDS
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from urllib.parse import urlencode
from zExceptions import Unauthorized
from zope.interface import alsoProvides

import pytest
import re
import transaction


MB = 1024 * 1024
SOFT_ABOVE_HARD = "The soft limit cannot be higher than the hard limit."
MAX_FILE_REQUIRED = "Set a maximum file size greater than 0 for this policy."


@pytest.fixture
def panel(browser, functional_portal):
    """panel(role="Manager") -> browser showing the control panel."""

    def func(role="Manager"):
        test_browser = browser(role)
        test_browser.open(f"{functional_portal.absolute_url()}/@@quota-controlpanel")
        return test_browser

    return func


def fill(test_browser, soft="", hard="", policy=None, max_file=""):
    test_browser.getControl(name="form.widgets.soft_limit_mb").value = str(soft)
    test_browser.getControl(name="form.widgets.hard_limit_mb").value = str(hard)
    test_browser.getControl(name="form.widgets.max_file_size_mb").value = str(max_file)
    if policy is not None:
        test_browser.getControl(name="form.widgets.over_limit_policy:list").value = [
            policy
        ]


def save(test_browser):
    test_browser.getControl(name="form.buttons.save").click()


class TestPermission:
    @pytest.mark.parametrize("role", ["Editor", "Contributor", "Reviewer", "Member"])
    def test_requires_manage_permission(self, portal, http_request, role):
        alsoProvides(http_request, IBrowserLayer)
        setRoles(portal, TEST_USER_ID, [role])
        with pytest.raises(Unauthorized):
            portal.restrictedTraverse("@@quota-controlpanel")

    @pytest.mark.parametrize("role", ["Manager", "Site Administrator"])
    def test_allowed_roles(self, portal, http_request, role):
        alsoProvides(http_request, IBrowserLayer)
        setRoles(portal, TEST_USER_ID, [role])
        assert portal.restrictedTraverse("@@quota-controlpanel") is not None

    def test_site_administrator_renders(self, panel):
        assert "Quota settings" in panel("Site Administrator").contents


class TestSave:
    def test_save_values(self, stored_settings, panel):
        test_browser = panel()
        fill(test_browser, soft=100, hard=200, policy="block_files")
        save(test_browser)
        assert "Changes saved." in test_browser.contents
        assert stored_settings() == {
            "soft_limit_mb": 100,
            "hard_limit_mb": 200,
            "over_limit_policy": "block_files",
            "max_file_size_mb": None,
        }

    def test_invariant_soft_above_hard(self, stored_settings, panel):
        test_browser = panel()
        fill(test_browser, soft=300, hard=200)
        save(test_browser)
        assert SOFT_ABOVE_HARD in test_browser.contents
        assert stored_settings() == dict.fromkeys(FIELDS)

    def test_invariant_max_file_required(self, stored_settings, panel):
        test_browser = panel()
        fill(test_browser, policy="limit_file_size", max_file=0)
        save(test_browser)
        assert MAX_FILE_REQUIRED in test_browser.contents
        assert stored_settings() == dict.fromkeys(FIELDS)

    def test_invariants_use_effective_values(self, stored_settings, panel, quota_env):
        quota_env(hard=100, lock="1")
        test_browser = panel()
        test_browser.getControl(name="form.widgets.soft_limit_mb").value = "200"
        save(test_browser)
        assert SOFT_ABOVE_HARD in test_browser.contents
        assert stored_settings() == dict.fromkeys(FIELDS)

    def test_field_errors_still_reported(self, stored_settings, panel):
        test_browser = panel()
        fill(test_browser, hard="lots")
        save(test_browser)
        assert "The entered value is not a valid integer literal." in (
            test_browser.contents
        )
        assert stored_settings() == dict.fromkeys(FIELDS)

    def test_environment_conflict_does_not_block_saving(
        self, stored_settings, panel, quota_env
    ):
        """Conflicts that come only from the environment belong to the operator."""
        quota_env(soft=200, hard=100)
        test_browser = panel()
        fill(test_browser, policy="allow")
        save(test_browser)
        assert "Changes saved." in test_browser.contents
        assert stored_settings()["over_limit_policy"] == "allow"


class TestLock:
    def test_locked_field_rendered_display_mode_with_source_note(
        self, panel, quota_env
    ):
        quota_env(hard=100, lock="1")
        test_browser = panel()
        contents = test_browser.contents
        assert "widget-mode-display" in contents
        assert re.search(r'id="form-widgets-hard_limit_mb"[^>]*>100<', contents)
        with pytest.raises(LookupError):
            test_browser.getControl(name="form.widgets.hard_limit_mb")
        row = re.search(
            r'<tr id="quota-source-hard_limit_mb" data-source="env-locked">(.*?)</tr>',
            contents,
            re.S,
        ).group(1)
        assert "100 MB" in row
        assert "Environment (locked)" in row
        assert "COLLECTIVE_QUOTA_HARD_LIMIT_MB" in row

    def test_source_notes_on_editable_fields(self, panel, quota_env, set_quota):
        quota_env(soft=5)
        set_quota(soft_mb=None, hard_mb=50, policy=None, max_file_mb=None)
        transaction.commit()
        contents = panel().contents
        assert (
            "Currently: 5 MB (from environment variable COLLECTIVE_QUOTA_SOFT_LIMIT_MB;"
            " a value saved here takes precedence)." in contents
        )
        assert "Currently: 50 MB (set in this control panel)." in contents
        assert "Currently: 10 MB (built-in default)." in contents

    def test_locked_field_not_written_even_if_posted(
        self, stored_settings, panel, functional_portal, quota_env
    ):
        quota_env(hard=100, lock="1")
        test_browser = panel()
        token = test_browser.getForm(id="form").getControl(name="_authenticator").value
        test_browser.open(
            f"{functional_portal.absolute_url()}/@@quota-controlpanel",
            data=urlencode({
                "form.widgets.hard_limit_mb": "999",
                "form.widgets.soft_limit_mb": "7",
                "form.widgets.over_limit_policy:list": "allow",
                "form.widgets.over_limit_policy-empty-marker": "1",
                "form.widgets.max_file_size_mb": "",
                "form.buttons.save": "Save",
                "_authenticator": token,
            }),
        )
        assert "Changes saved." in test_browser.contents
        values = stored_settings()
        assert values["hard_limit_mb"] is None
        assert values["soft_limit_mb"] == 7

    def test_apply_changes_drops_locked_fields(self, portal, http_request, quota_env):
        """Guard against a widget forced into input mode."""
        quota_env(hard=100, lock="1")
        alsoProvides(http_request, IBrowserLayer)
        form = QuotaControlPanelForm(portal, http_request)
        form.update()
        with api.env.adopt_roles(["Manager"]):
            form.applyChanges({"hard_limit_mb": 999, "soft_limit_mb": 7})
        assert api.portal.get_registry_record("collective.quota.hard_limit_mb") is None
        assert api.portal.get_registry_record("collective.quota.soft_limit_mb") == 7

    def test_unlocked_fields_still_saved_when_lock_flag_on(
        self, stored_settings, panel, quota_env
    ):
        quota_env(hard=100, lock="1")
        test_browser = panel()
        fill_values = {"soft_limit_mb": "50", "max_file_size_mb": "4"}
        for name, value in fill_values.items():
            test_browser.getControl(name=f"form.widgets.{name}").value = value
        test_browser.getControl(name="form.widgets.over_limit_policy:list").value = [
            "limit_file_size"
        ]
        save(test_browser)
        assert "Changes saved." in test_browser.contents
        assert stored_settings() == {
            "soft_limit_mb": 50,
            "hard_limit_mb": None,
            "over_limit_policy": "limit_file_size",
            "max_file_size_mb": 4,
        }

    def test_sources_table_and_lock_alert(self, panel, quota_env, set_quota):
        quota_env(hard=100, policy="allow", lock="on")
        set_quota(soft_mb=10, hard_mb=None, policy=None, max_file_mb=None)
        transaction.commit()
        contents = panel().contents
        assert 'id="quota-lock-alert"' in contents
        sources = dict(
            re.findall(r'<tr id="quota-source-(\w+)" data-source="([\w-]+)">', contents)
        )
        assert sources == {
            "soft_limit_mb": "registry",
            "hard_limit_mb": "env-locked",
            "over_limit_policy": "env-locked",
            "max_file_size_mb": "default",
        }
        for label in ("Control panel", "Environment (locked)", "Default"):
            assert label in contents

    def test_no_lock_alert_without_flag(self, panel, quota_env):
        quota_env(hard=100)
        contents = panel().contents
        assert 'id="quota-lock-alert"' not in contents
        assert 'data-source="env"' in contents
        assert ">Environment<" in contents


class TestReset:
    def test_reset_to_defaults_clears_non_locked_records(
        self, stored_settings, panel, quota_env, set_quota
    ):
        quota_env(hard=100, lock="1")
        set_quota(soft_mb=10, hard_mb=20, policy="allow", max_file_mb=3)
        transaction.commit()
        test_browser = panel()
        test_browser.getControl(name="form.buttons.reset").click()
        assert "Settings reset." in test_browser.contents
        # The locked record is left alone: it is not the control panel's to clear.
        assert stored_settings() == {
            "soft_limit_mb": None,
            "hard_limit_mb": 20,
            "over_limit_policy": None,
            "max_file_size_mb": None,
        }


class TestUsageCard:
    def test_usage_card_shows_total_and_level(
        self, panel, functional_portal, make_file, set_quota
    ):
        make_file(functional_portal, "a", 2 * MB)
        make_file(functional_portal, "b", 1 * MB)
        set_quota(soft_mb=2, hard_mb=10)
        transaction.commit()
        contents = panel().contents
        assert '<strong id="quota-usage-total">3.0 MB</strong>' in contents
        assert '<strong id="quota-usage-hard">10.0 MB</strong>' in contents
        assert "(30%)" in contents
        assert (
            'class="progress-bar bg-warning" id="quota-usage-bar" style="width: 30%"'
            ' data-level="warning"' in contents
        )

    @pytest.mark.parametrize(
        "soft,hard,css",
        [(0, 1, "bg-danger"), (0, 100, "bg-success")],
    )
    def test_bar_levels(
        self, panel, functional_portal, make_file, set_quota, soft, hard, css
    ):
        make_file(functional_portal, "a", 2 * MB)
        set_quota(soft_mb=soft, hard_mb=hard)
        transaction.commit()
        contents = panel().contents
        assert f'class="progress-bar {css}"' in contents
        if hard == 1:
            assert 'style="width: 100%"' in contents  # capped at 100 %

    def test_no_bar_without_hard_limit(self, panel):
        contents = panel().contents
        assert 'id="quota-usage-bar"' not in contents
        assert 'id="quota-usage-total">0 KB<' in contents
        assert "disabled" in contents

    def test_usage_card_without_index(self, panel, functional_portal):
        functional_portal.portal_catalog.delIndex("blob_size")
        transaction.commit()
        assert 'id="quota-usage-total">0 KB<' in panel().contents

    def test_usage_link_only_when_view_exists(self, panel):
        assert 'id="quota-usage-link"' not in panel().contents


class TestRebuildButton:
    def test_rebuild_button_posts_to_rebuild_view(self, panel, functional_portal):
        test_browser = panel()
        assert re.search(
            r'<form method="post"\s+action="[^"]*/@@quota-rebuild"',
            test_browser.contents,
        )
        test_browser.getControl("Rebuild usage data").click()
        assert test_browser.url.endswith("/@@quota-controlpanel")
        assert "Usage data rebuilt:" in test_browser.contents


class TestConfiglet:
    def test_configlet_listed_in_site_setup(self, browser, functional_portal):
        test_browser = browser("Site Administrator")
        test_browser.open(f"{functional_portal.absolute_url()}/@@overview-controlpanel")
        assert f"{functional_portal.absolute_url()}/@@quota-controlpanel" in (
            test_browser.contents
        )

    def test_configlet_hidden_from_editors(self, portal):
        setRoles(portal, TEST_USER_ID, ["Editor"])
        ids = [
            c["id"] for c in portal.portal_controlpanel.enumConfiglets(group="Products")
        ]
        assert "collective-quota" not in ids


class TestFormUnit:
    def test_extract_without_setting_errors(self, portal, http_request):
        """Inline validation calls extractData(setErrors=False)."""
        alsoProvides(http_request, IBrowserLayer)
        http_request.form.update({
            "form.widgets.soft_limit_mb": "300",
            "form.widgets.hard_limit_mb": "200",
        })
        form = QuotaControlPanelForm(portal, http_request)
        form.update()
        _data, errors = form.extractData(setErrors=False)
        assert [error.message for error in errors] == [SOFT_ABOVE_HARD]
        assert form.widgets.errors == ()

    def test_usage_link_when_view_exists(self, portal, http_request):
        from collective.quota.controlpanels.quota import QuotaControlPanel
        from Products.Five.browser import BrowserView
        from zope.component import getSiteManager
        from zope.interface import Interface
        from zope.publisher.interfaces.browser import IBrowserRequest

        sm = getSiteManager()
        args = (BrowserView, (Interface, IBrowserRequest), Interface, "quota-usage")
        sm.registerAdapter(*args)
        try:
            url = QuotaControlPanel(portal, http_request).usage_view_url()
        finally:
            sm.unregisterAdapter(*args)
        assert url == f"{portal.absolute_url()}/@@quota-usage"
