"""``@@quota-delete``: delete items picked in ``@@quota-usage``.

Two steps, like Plone's own delete: a confirmation page with the link
integrity warnings, then the deletion (POST with a CSRF token).
"""

from collective.quota import _
from collective.quota.listing import DELETE_OBJECTS
from collective.quota.listing import item_size
from collective.quota.listing import type_title
from collective.quota.usage import get_index
from collective.quota.usage import get_total_usage
from collective.quota.utils import human_readable_size
from plone import api
from plone.base.utils import pretty_title_or_id
from plone.locking.interfaces import ILockable
from plone.protect import CheckAuthenticator
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from zope.component import getMultiAdapter


USAGE_VIEW = "quota-usage"

REASON_NO_PERMISSION = _("you are not allowed to delete it")
REASON_LOCKED = _("it is locked by another user")


class QuotaDeleteView(BrowserView):
    index = ViewPageTemplateFile("templates/delete_confirmation.pt")

    def __call__(self):
        form = self.request.form
        if "form.button.cancel" in form:
            return self._redirect()
        uids = form.get("uids", [])
        if isinstance(uids, str):
            uids = [uids]
        if not uids:
            self._message(_("No items selected."), "warning")
            return self._redirect()
        self.items, self.skipped = self._resolve(uids)
        if "form.button.confirm" in form:
            CheckAuthenticator(self.request)
            return self._delete()
        self.request.set("disable_border", True)
        return self.index()

    def _message(self, message, type_):
        IStatusMessage(self.request).addStatusMessage(message, type=type_)

    def _redirect(self):
        url = f"{self.context.absolute_url()}/@@{USAGE_VIEW}"
        return self.request.response.redirect(url)

    def _resolve(self, uids):
        """``(deletable, skipped)`` items among those the user can see."""
        index = get_index(self.context)
        catalog = api.portal.get_tool("portal_catalog")
        items, skipped = [], []
        for brain in catalog(UID=list(uids)):
            obj = brain._unrestrictedGetObject()  # see DiskUsageView.items
            size = item_size(brain, index) if index is not None else 0
            item = {
                "uid": brain.UID,
                "title": pretty_title_or_id(self.context, brain),
                "url": brain.getURL(),
                "type_title": type_title(brain.portal_type, self.request),
                "size": size,
                "size_human": human_readable_size(size),
                "obj": obj,
            }
            if api.user.has_permission(DELETE_OBJECTS, obj=obj):
                items.append(item)
            else:
                skipped.append({**item, "reason": REASON_NO_PERMISSION})
        return items, skipped

    def total_size(self) -> str:
        return human_readable_size(sum(item["size"] for item in self.items))

    def breaches_html(self) -> str:
        """The link integrity snippet of ``plone.app.linkintegrity``, or ``""``
        when link integrity is off or nothing would break."""
        info = getMultiAdapter(
            (self.context, self.request), name="delete_confirmation_info"
        )
        if not info.linkintegrity_enabled:
            return ""
        objects = [item["obj"] for item in self.items]
        info.breaches = info.get_breaches(objects)
        if not info.breaches and not info.breach_count:
            return ""
        return info.template()

    def _delete(self):
        deletable = []
        for item in self.items:
            obj = item["obj"]
            lock_info = obj.restrictedTraverse("@@plone_lock_info", None)
            if lock_info is not None and lock_info.is_locked():
                if lock_info.is_locked_for_current_user():
                    self.skipped.append({**item, "reason": REASON_LOCKED})
                    continue
                # Locked by the current user: unlock, as Plone's delete does.
                ILockable(obj).unlock()
            deletable.append(obj)
        if deletable:
            before = get_total_usage(self.context)
            api.content.delete(objects=deletable, check_linkintegrity=False)
            freed = before - get_total_usage(self.context)
            self._message(
                _(
                    "Deleted ${count} items, freeing ${size}.",
                    mapping={
                        "count": len(deletable),
                        "size": human_readable_size(freed),
                    },
                ),
                "info",
            )
        for item in self.skipped:
            self._message(
                _(
                    "Skipped ${title}: ${reason}.",
                    mapping={"title": item["title"], "reason": item["reason"]},
                ),
                "warning",
            )
        return self._redirect()
