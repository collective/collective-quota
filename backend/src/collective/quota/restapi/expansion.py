"""``quota`` expansion element: the usage summary in ``@components``."""

from AccessControl import getSecurityManager
from collective.quota.interfaces import IQuotaRestapiLayer
from collective.quota.restapi.usage import usage_payload
from collective.quota.restapi.usage import VIEW_DISK_USAGE
from plone import api
from plone.restapi.interfaces import IExpandableElement
from zope.component import adapter
from zope.interface import implementer
from zope.interface import Interface


@implementer(IExpandableElement)
@adapter(Interface, IQuotaRestapiLayer)
class Quota:
    def __init__(self, context, request):
        self.context = context
        self.request = request

    def __call__(self, expand=False):
        portal = api.portal.get()
        # The permission is checked on the site root, where the services live.
        if api.user.is_anonymous() or not getSecurityManager().checkPermission(
            VIEW_DISK_USAGE, portal
        ):
            return {}  # no key at all: nothing to see
        result = {"quota": {"@id": f"{portal.absolute_url()}/@quota-usage"}}
        if expand:
            result["quota"].update(usage_payload(portal, self.request))
        return result
