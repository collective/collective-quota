"""Read API for disk usage: total, usage level, and the repair routine."""

from collective.quota import logger
from collective.quota.catalog.blob_size_index import BlobSizeIndex
from collective.quota.guard import guard_suspended
from collective.quota.settings import get_settings
from collective.quota.settings import QuotaSettings
from dataclasses import dataclass
from plone import api
from Products.CMFCore.indexing import processQueue
from Products.CMFCore.utils import getToolByName
from ZODB.POSException import ConflictError

import transaction


__all__ = [
    "INDEX_NAME",
    "QuotaSettings",
    "UsageInfo",
    "get_index",
    "get_settings",
    "get_total_usage",
    "get_usage_info",
    "rebuild_usage",
]

INDEX_NAME = "blob_size"

LEVEL_OK = "ok"
LEVEL_WARNING = "warning"
LEVEL_EXCEEDED = "exceeded"


@dataclass(frozen=True)
class UsageInfo:
    total: int
    soft: int
    hard: int
    percent: int | None  # of the hard limit; None when the hard limit is disabled
    level: str  # "ok" | "warning" | "exceeded"


def get_index(portal=None) -> BlobSizeIndex | None:
    """Return the ``blob_size`` index, or None when it is missing."""
    portal = portal if portal is not None else api.portal.get()
    catalog = getToolByName(portal, "portal_catalog")
    try:
        index = catalog._catalog.getIndex(INDEX_NAME)
    except KeyError:
        return None
    return index if isinstance(index, BlobSizeIndex) else None


def get_total_usage(portal=None) -> int:
    """Bytes used by all blob fields of the site. 0 when the index is missing.

    Flushes Plone's indexing queue first, so changes made earlier in the same
    request (queued reindex/unindex) are counted.
    """
    processQueue()
    index = get_index(portal)
    return index.total() if index is not None else 0


def get_usage_info(portal=None) -> UsageInfo:
    total = get_total_usage(portal)
    settings = get_settings()
    soft, hard = settings.soft_bytes, settings.hard_bytes
    if hard and total >= hard:
        level = LEVEL_EXCEEDED
    elif soft and total >= soft:
        level = LEVEL_WARNING
    else:
        level = LEVEL_OK
    percent = total * 100 // hard if hard else None
    return UsageInfo(total=total, soft=soft, hard=hard, percent=percent, level=level)


def _reindex_brain(catalog, brain, update_metadata) -> bool:
    try:
        obj = brain._unrestrictedGetObject()
    except ConflictError:
        raise
    except Exception:
        logger.warning("Cannot load %s; skipped", brain.getPath(), exc_info=True)
        return False
    catalog.catalog_object(
        obj, idxs=[INDEX_NAME], update_metadata=1 if update_metadata else 0
    )
    return True


def rebuild_usage(portal, update_metadata=True, log_every=1000, commit_every=0) -> int:
    """Re-catalog every item for ``blob_size`` and recompute the total.

    ``update_metadata`` also refreshes the metadata columns (needed to fill the
    ``blob_size`` column for existing content). ``commit_every`` > 0 commits a
    transaction every that many items (scripts on very large sites only).
    Runs with the commit guard suspended. Returns the number of items
    re-cataloged; objects that fail to load are logged and skipped.
    """
    index = get_index(portal)
    if index is None:
        return 0
    catalog = getToolByName(portal, "portal_catalog")
    processQueue()  # unrestrictedSearchResults does not flush the queue
    # An empty query returns nothing in ZCatalog; query everything under the site.
    site_path = "/".join(portal.getPhysicalPath())
    brains = iter(catalog.unrestrictedSearchResults(path=site_path))
    count = 0
    while True:
        with guard_suspended():
            for in_batch, brain in enumerate(brains, 1):
                if _reindex_brain(catalog, brain, update_metadata):
                    count += 1
                    if count % log_every == 0:
                        logger.info("rebuild_usage: %d items processed", count)
                if commit_every and in_batch >= commit_every:
                    break
            else:
                total = index.rebuild_total()
                logger.info("rebuild_usage: %d items, total %d bytes", count, total)
                return count
        transaction.commit()
