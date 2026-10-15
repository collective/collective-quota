from zope.component import queryUtility
from zope.security.interfaces import IPermission

import pytest


MANAGE = "collective.quota: Manage Quota Settings"
VIEW = "collective.quota: View Disk Usage"

EXPECTED_ROLES = {
    MANAGE: {"Manager", "Site Administrator"},
    VIEW: {"Manager", "Site Administrator", "Editor", "Contributor", "Reviewer"},
}


def selected_roles(portal, permission):
    return {r["name"] for r in portal.rolesOfPermission(permission) if r["selected"]}


@pytest.mark.parametrize(
    "permission_id,title",
    [
        ("collective.quota.ManageSettings", MANAGE),
        ("collective.quota.ViewDiskUsage", VIEW),
    ],
)
def test_permission_registered(permission_id, title):
    permission = queryUtility(IPermission, name=permission_id)
    assert permission is not None
    assert permission.title == title


@pytest.mark.parametrize("permission", [MANAGE, VIEW])
def test_default_roles(portal, permission):
    """Only the documented roles get the permission; Member/Anonymous do not."""
    assert selected_roles(portal, permission) == EXPECTED_ROLES[permission]


@pytest.mark.parametrize("permission", [MANAGE, VIEW])
def test_permission_acquired(portal, permission):
    assert portal.acquiredRolesAreUsedBy(permission) == "CHECKED"


@pytest.mark.parametrize(
    "role,can_manage,can_view",
    [
        ("Manager", True, True),
        ("Site Administrator", True, True),
        ("Editor", False, True),
        ("Contributor", False, True),
        ("Reviewer", False, True),
        ("Member", False, False),
        ("Anonymous", False, False),
    ],
)
def test_role_matrix(portal, role, can_manage, can_view):
    assert (role in selected_roles(portal, MANAGE)) is can_manage
    assert (role in selected_roles(portal, VIEW)) is can_view
