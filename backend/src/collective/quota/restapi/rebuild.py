"""``POST @quota-rebuild``: re-catalog every item and recompute the total."""

from collective.quota.usage import get_total_usage
from collective.quota.usage import rebuild_usage
from collective.quota.utils import human_readable_size
from plone.protect.interfaces import IDisableCSRFProtection
from plone.restapi.services import Service
from zope.interface import alsoProvides


class QuotaRebuildPost(Service):
    def reply(self):
        # Like plone.restapi's own write services: authentication and the
        # ManageSettings permission are the guards, not a form token.
        alsoProvides(self.request, IDisableCSRFProtection)
        count = rebuild_usage(self.context)
        total = get_total_usage(self.context)
        return {
            "items": count,
            "total": total,
            "total_human": human_readable_size(total),
        }
