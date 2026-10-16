"""``@@quota-usage``: the biggest items of the site."""

from collective.quota.listing import biggest_items
from collective.quota.listing import DEFAULT_LIMIT
from collective.quota.listing import LIMITS
from collective.quota.listing import parse_limit
from collective.quota.settings import get_settings
from collective.quota.summary import ALERT_CLASSES
from collective.quota.summary import level_message
from collective.quota.summary import usage_summary
from collective.quota.usage import get_usage_info
from collective.quota.utils import human_readable_size
from plone import api
from plone.memoize.view import memoize
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile


__all__ = ["DEFAULT_LIMIT", "DiskUsageView"]

MANAGE_SETTINGS = "collective.quota: Manage Quota Settings"


class DiskUsageView(BrowserView):
    index = ViewPageTemplateFile("templates/usage.pt")

    def __call__(self):
        self.request.set("disable_border", True)
        return self.index()

    def limit(self) -> int:
        return parse_limit(self.request.form.get("limit"))

    def limits(self):
        return LIMITS

    @memoize
    def usage(self):
        return get_usage_info(self.context)

    def summary(self) -> dict:
        return usage_summary(self.usage(), get_settings())

    def alert(self) -> dict | None:
        info = self.usage()
        message = level_message(info, get_settings())
        if message is None:
            return None
        return {"message": message, "css_class": ALERT_CLASSES[info.level]}

    def can_manage(self) -> bool:
        return api.user.has_permission(MANAGE_SETTINGS, obj=self.context)

    def controlpanel_url(self) -> str:
        return f"{self.context.absolute_url()}/@@quota-controlpanel"

    def rebuild_url(self) -> str:
        return f"{self.context.absolute_url()}/@@quota-rebuild"

    def delete_url(self) -> str:
        return f"{self.context.absolute_url()}/@@quota-delete"

    def items(self) -> list[dict]:
        return [
            {
                "uid": item.uid,
                "title": item.title,
                "url": item.url,
                "edit_url": f"{item.url}/edit",
                "portal_type": item.portal_type,
                "type_title": item.type_title,
                "parent_url": item.parent_url,
                "parent_title": item.parent_title,
                "size": item.size,
                "size_human": human_readable_size(item.size),
                "modified": api.portal.get_localized_time(
                    item.modified, long_format=True
                ),
                "can_delete": item.can_delete,
            }
            for item in biggest_items(self.context, self.request, self.limit())
        ]
