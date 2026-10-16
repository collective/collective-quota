"""Helpers for upgrade steps.

Convention for a schema, registry or catalog change:

1. Bump ``profiles/default/metadata.xml`` (``1000`` → ``1001``).
2. Add ``upgrades/v1001.py`` with ``def upgrade(setup_tool): ...``.
3. Register it in ``upgrades/configure.zcml`` with ``source`` and ``destination``.
4. Test it in ``tests/setup/test_upgrades.py``.
"""

from collective.quota import logger
from collective.quota.usage import rebuild_usage as _rebuild_usage
from plone import api
from Products.GenericSetup.tool import SetupTool


PROFILE_ID = "profile-collective.quota:default"


def run_import_step(setup_tool: SetupTool, step: str, profile: str = PROFILE_ID):
    """Re-run one import step (``"catalog"``, ``"plone.app.registry"``,
    ``"actions"``, ...) of the add-on's default profile."""
    if not profile.startswith("profile-"):
        profile = f"profile-{profile}"
    setup_tool.runImportStepFromProfile(profile, step, run_dependencies=False)
    logger.info("Ran import step %s of %s", step, profile)


def rebuild_usage(setup_tool: SetupTool | None = None, **kwargs) -> int:
    """Recompute ``blob_size`` for every item and the site total.

    Accepts the setup tool so it can be used directly as an upgrade handler.
    Keyword arguments go to :func:`collective.quota.usage.rebuild_usage`.
    """
    return _rebuild_usage(api.portal.get(), **kwargs)
