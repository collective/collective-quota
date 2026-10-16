"""The biggest items of the site, shared by ``@@quota-usage`` and ``@quota-usage``."""

from Acquisition import aq_inner
from Acquisition import aq_parent
from collective.quota.usage import get_index
from collective.quota.usage import INDEX_NAME
from dataclasses import dataclass
from DateTime import DateTime
from plone import api
from plone.base.utils import pretty_title_or_id
from zope.i18n import translate


LIMITS = (10, 25, 50, 100)
DEFAULT_LIMIT = 25

DELETE_OBJECTS = "Delete objects"


def parse_limit(value) -> int:
    """``value`` from a request; one of LIMITS, else DEFAULT_LIMIT."""
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return limit if limit in LIMITS else DEFAULT_LIMIT


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


@dataclass(frozen=True)
class Item:
    uid: str
    title: str
    url: str
    portal_type: str
    type_title: str
    parent_url: str
    parent_title: str
    size: int
    modified: DateTime  # raw; each UI formats it
    can_delete: bool


def biggest_items(portal, request, limit: int) -> list[Item]:
    """Items with blob fields, biggest first, among those the user can see."""
    index = get_index(portal)
    if index is None:
        return []
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
        items.append(
            Item(
                uid=brain.UID,
                title=pretty_title_or_id(portal, brain),
                url=brain.getURL(),
                portal_type=brain.portal_type,
                type_title=type_title(brain.portal_type, request),
                parent_url=parent.absolute_url(),
                parent_title=pretty_title_or_id(portal, parent),
                size=item_size(brain, index),
                modified=brain.modified,
                can_delete=api.user.has_permission(DELETE_OBJECTS, obj=obj),
            )
        )
    return items
