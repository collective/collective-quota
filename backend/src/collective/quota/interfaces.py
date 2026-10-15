"""Module where all interfaces, events and exceptions live."""

from plone.restapi.interfaces import IPloneRestapiLayer
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class IBrowserLayer(IDefaultBrowserLayer):
    """Classic UI layer."""


class IQuotaRestapiLayer(IPloneRestapiLayer):
    """REST layer: overrides of plone.restapi adapters are registered for it."""
