from collective.quota.testing import ACCEPTANCE_TESTING
from collective.quota.testing import FUNCTIONAL_TESTING
from collective.quota.testing import INTEGRATION_TESTING
from plone import api
from plone.app.testing import setRoles
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import TEST_USER_PASSWORD
from plone.namedfile.file import NamedBlobFile
from plone.namedfile.file import NamedBlobImage
from plone.testing.zope import Browser
from pytest_plone import fixtures_factory

import base64
import pytest
import transaction


pytest_plugins = ["pytest_plone"]


globals().update(
    fixtures_factory((
        (ACCEPTANCE_TESTING, "acceptance"),
        (FUNCTIONAL_TESTING, "functional"),
        (INTEGRATION_TESTING, "integration"),
    ))
)


MB = 1024 * 1024

# Smallest valid PNG (1x1 transparent pixel), padded to reach a requested size.
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA"
    "60e6kgAAAABJRU5ErkJggg=="
)

# Environment variables read by collective.quota.settings (see specs, §2).
QUOTA_ENV_VARS = {
    "soft": "COLLECTIVE_QUOTA_SOFT_LIMIT_MB",
    "hard": "COLLECTIVE_QUOTA_HARD_LIMIT_MB",
    "policy": "COLLECTIVE_QUOTA_OVER_LIMIT_POLICY",
    "max_file": "COLLECTIVE_QUOTA_MAX_FILE_SIZE_MB",
    "lock": "COLLECTIVE_QUOTA_LOCK_SETTINGS",
}

# Blob field used by make_file for each content type.
BLOB_FIELDS = {
    "File": ("file", False),
    "Image": ("image", True),
}


@pytest.fixture(autouse=True)
def _clear_quota_env(monkeypatch):
    """Never let host COLLECTIVE_QUOTA_* variables leak into tests."""
    for name in QUOTA_ENV_VARS.values():
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def quota_env(monkeypatch):
    """quota_env(soft=None, hard=None, policy=None, max_file=None, lock=None)

    Clears all COLLECTIVE_QUOTA_* variables, then sets the ones given.
    """

    def func(**values):
        unknown = set(values) - set(QUOTA_ENV_VARS)
        if unknown:
            raise TypeError(f"Unknown quota_env arguments: {sorted(unknown)}")
        for key, name in QUOTA_ENV_VARS.items():
            monkeypatch.delenv(name, raising=False)
            value = values.get(key)
            if value is not None:
                monkeypatch.setenv(name, str(value))

    return func


@pytest.fixture
def make_blob():
    """make_blob(size_bytes, filename="f.bin", image=False) -> NamedBlobFile/Image

    Images are a valid 1x1 PNG padded with trailing bytes, so ``size_bytes``
    must be at least ``len(PNG_1X1)``.
    """

    def func(size_bytes, filename="f.bin", image=False):
        if image:
            if size_bytes < len(PNG_1X1):
                raise ValueError(f"Images need at least {len(PNG_1X1)} bytes")
            data = PNG_1X1 + b"\0" * (size_bytes - len(PNG_1X1))
            return NamedBlobImage(data=data, filename=filename)
        return NamedBlobFile(data=b"\0" * size_bytes, filename=filename)

    return func


@pytest.fixture
def make_file(portal, make_blob):
    """make_file(container, id, size_bytes, type="File") -> created object

    Uses plone.api on purpose (no form or policy validation), so tests can push
    a site over its limit before testing enforcement.
    """

    def func(container, id, size_bytes, type="File"):  # noqa: A002
        field, image = BLOB_FIELDS[type]
        filename = f"{id}.png" if image else f"{id}.bin"
        blob = make_blob(size_bytes, filename=filename, image=image)
        with api.env.adopt_roles(["Manager"]):
            return api.content.create(
                container=container, type=type, id=id, title=id, **{field: blob}
            )

    return func


@pytest.fixture
def make_image(make_file):
    """make_image(container, id, size_bytes) -> created Image"""

    def func(container, id, size_bytes):  # noqa: A002
        return make_file(container, id, size_bytes, type="Image")

    return func


def _login_as(portal, role):
    """Return basic-auth credentials for ``role`` (None for Anonymous).

    Non-Manager roles are granted to the default test user and committed so
    the functional server sees them.
    """
    if role == "Anonymous":
        return None
    if role == "Manager":
        return (SITE_OWNER_NAME, SITE_OWNER_PASSWORD)
    setRoles(portal, TEST_USER_ID, ["Member", role])
    transaction.commit()
    return (TEST_USER_NAME, TEST_USER_PASSWORD)


@pytest.fixture
def browser(functional_app, functional_portal):
    """browser(role="Manager") -> plone.testing Browser logged in as ``role``"""

    def func(role="Manager"):
        test_browser = Browser(functional_app)
        test_browser.handleErrors = False
        credentials = _login_as(functional_portal, role)
        if credentials is not None:
            test_browser.addHeader("Authorization", "Basic {}:{}".format(*credentials))
        return test_browser

    return func


@pytest.fixture
def api_session(functional_portal, request_factory):
    """api_session(role="Manager") -> RelativeSession on ``++api++`` as ``role``"""

    def func(role="Manager"):
        credentials = _login_as(functional_portal, role)
        if credentials is None:
            return request_factory(role="Anonymous")
        return request_factory(basic_auth=credentials)

    return func
