"""``@@quota-usage``: the biggest items of the site."""

from Acquisition import aq_inner
from Acquisition import aq_parent
from collective.quota.browser.summary import ALERT_CLASSES
from collective.quota.browser.summary import level_message
from collective.quota.browser.summary import usage_summary
from collective.quota.settings import get_settings
from collective.quota.usage import get_index
from collective.quota.usage import get_usage_info
from collective.quota.usage import INDEX_NAME
from collective.quota.utils import human_readable_size
from plone import api
from plone.base.utils import pretty_title_or_id
from plone.memoize.view import memoize
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope.i18n import translate


LIMITS = (10, 25, 50, 100)
DEFAULT_LIMIT = 25

MANAGE_SETTINGS = "collective.quota: Manage Quota Settings"
DELETE_OBJECTS = "Delete objects"


def item_size(brain, index) -> int:
    """``blob_size`` of a brain, from the metadata column or else the index."""
    size = getattr(brain, INDEX_NAME, None)
    if isinstance(size, int):
        return size
    # The metadata column is empty until the object is re-cataloged with
    # metadata (e.g. after ``reindexIndex``); the index has the value.
    return index.getEntryForObject(brain.getRID(), 0)


def type_title(portal_type, request) -> str:
    fti = api.portal.get_tool("portal_types").get(portal_type)
    title = fti.Title() if fti is not None else portal_type
    return translate(title, context=request)


class DiskUsageView(BrowserView):
    index = ViewPageTemplateFile("templates/usage.pt")

    def __call__(self):
        self.request.set("disable_border", True)
        return self.index()

    def limit(self) -> int:
        try:
            limit = int(self.request.form.get("limit", DEFAULT_LIMIT))
        except (TypeError, ValueError):
            return DEFAULT_LIMIT
        return limit if limit in LIMITS else DEFAULT_LIMIT

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
        index = get_index(self.context)
        if index is None:
            return []
        limit = self.limit()
        catalog = api.portal.get_tool("portal_catalog")
        brains = catalog(
            blob_size={"query": 1, "range": "min"},
            sort_on=INDEX_NAME,
            sort_order="descending",
            sort_limit=limit,
        )[:limit]
        items = []
        for brain in brains:
            # The catalog lists what the user may "Access contents information"
            # on; getObject would also require "View" on the object.
            obj = brain._unrestrictedGetObject()
            parent = aq_parent(aq_inner(obj))
            url = brain.getURL()
            size = item_size(brain, index)
            items.append({
                "uid": brain.UID,
                "title": pretty_title_or_id(self.context, brain),
                "url": url,
                "edit_url": f"{url}/edit",
                "portal_type": brain.portal_type,
                "type_title": type_title(brain.portal_type, self.request),
                "parent_url": parent.absolute_url(),
                "parent_title": pretty_title_or_id(self.context, parent),
                "size": size,
                "size_human": human_readable_size(size),
                "modified": api.portal.get_localized_time(
                    brain.modified, long_format=True
                ),
                "can_delete": api.user.has_permission(DELETE_OBJECTS, obj=obj),
            })
        return items
