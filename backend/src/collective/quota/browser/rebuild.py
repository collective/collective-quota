"""``@@quota-rebuild``: recompute the usage data (POST only)."""

from collective.quota import _
from collective.quota.usage import get_total_usage
from collective.quota.usage import rebuild_usage
from collective.quota.utils import human_readable_size
from plone.protect import CheckAuthenticator
from Products.Five.browser import BrowserView
from Products.statusmessages.interfaces import IStatusMessage
from zExceptions import MethodNotAllowed
from zope.component import queryMultiAdapter


CONTROLPANEL_VIEW = "quota-controlpanel"


class QuotaRebuildView(BrowserView):
    def __call__(self):
        if self.request.method != "POST":
            raise MethodNotAllowed("POST required")
        CheckAuthenticator(self.request)
        count = rebuild_usage(self.context, update_metadata=True)
        total = get_total_usage(self.context)
        IStatusMessage(self.request).addStatusMessage(
            _(
                "Usage data rebuilt: ${count} items, ${total} in total.",
                mapping={"count": count, "total": human_readable_size(total)},
            ),
            type="info",
        )
        target = self.context.absolute_url()
        if queryMultiAdapter((self.context, self.request), name=CONTROLPANEL_VIEW):
            target = f"{target}/@@{CONTROLPANEL_VIEW}"
        return self.request.response.redirect(target)
