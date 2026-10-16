import pytest


class TestAction:
    def test_action_registered_with_permission(self, portal):
        action = portal.portal_actions.user["disk-usage"]
        assert action.title == "Disk usage"
        assert action.permissions == ("collective.quota: View Disk Usage",)
        assert action.url_expr == (
            'python:f"{plone_portal_state.portal_url()}/@@quota-usage"'
        )
        assert action.available_expr == "python:member is not None"
        assert action.icon_expr == "string:hdd"
        assert action.visible

    def test_after_preferences(self, portal):
        ids = list(portal.portal_actions.user.objectIds())
        assert ids.index("disk-usage") == ids.index("preferences") + 1


class TestUserMenu:
    @pytest.mark.parametrize(
        "role", ["Editor", "Contributor", "Reviewer", "Site Administrator", "Manager"]
    )
    def test_visible_in_user_menu(self, browser, functional_portal, role):
        test_browser = browser(role)
        test_browser.open(functional_portal.absolute_url())
        link = test_browser.getLink(url="/@@quota-usage")
        assert link.url == f"{functional_portal.absolute_url()}/@@quota-usage"
        assert link.text.strip() == "Disk usage"

    @pytest.mark.parametrize("role", ["Member", "Anonymous"])
    def test_hidden(self, browser, functional_portal, role):
        test_browser = browser(role)
        test_browser.open(functional_portal.absolute_url())
        assert "@@quota-usage" not in test_browser.contents
