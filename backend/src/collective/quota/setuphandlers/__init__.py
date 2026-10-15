from plone.base.interfaces.installable import INonInstallable
from zope.interface import implementer


@implementer(INonInstallable)
class HiddenProfiles:
    def getNonInstallableProfiles(self):
        """Hide uninstall profile from site-creation and quickinstaller."""
        return [
            "collective.quota:uninstall",
        ]

    def getNonInstallableProducts(self):
        """Hide the upgrades package from site-creation and quickinstaller."""
        return [
            "collective.quota.upgrades",
        ]


def post_install(context):
    """Populate the blob_size index, its metadata column and the total."""
    from collective.quota.usage import rebuild_usage
    from plone import api

    rebuild_usage(api.portal.get(), update_metadata=True)
