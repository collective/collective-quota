"""Commit guard (hook D): no transaction may cross the hard limit unapproved.

Bookkeeping per transaction (a ``Ledger``): the site total before the first
change, the bytes and new items the validators approved, the new items added.
The before-commit hook is registered lazily, only by transactions that change
the ``blob_size`` total or add items. See specs/00-architecture.md, §5.1.
"""

from AccessControl.SecurityManagement import getSecurityManager
from collective.quota import _
from collective.quota import logger
from collective.quota.policy import ALLOW
from collective.quota.policy import BLOCK_ALL
from collective.quota.settings import get_settings
from collective.quota.utils import human_readable_size
from contextlib import contextmanager
from dataclasses import dataclass
from Products.CMFCore.utils import getToolByName
from weakref import WeakKeyDictionary
from zExceptions import BadRequest
from zope.component.hooks import getSite
from zope.component.hooks import site as site_context
from zope.globalrequest import getRequest
from zope.i18n import translate
from ZPublisher.HTTPResponse import status_codes

import inspect
import threading
import transaction


UNAPPROVED_BYTES = "unapproved_bytes"
UNAPPROVED_ITEMS = "unapproved_items"

MESSAGES = {
    UNAPPROVED_BYTES: _(
        "The change was cancelled: it would add ${delta} to the site and exceed "
        "the disk quota (${used} of ${limit})."
    ),
    UNAPPROVED_ITEMS: _(
        "The change was cancelled: new content cannot be added while the site "
        "exceeds its disk quota (${used} of ${limit})."
    ),
}


class _LedgerKey:
    """Key object for ``Transaction.set_data`` (which keys by ``id()``)."""


LEDGER_KEY = _LedgerKey()

# Transactions without set_data()/data() (transaction < 2.0, custom managers).
_fallback: WeakKeyDictionary = WeakKeyDictionary()

# Depth of nested guard_suspended() blocks in this thread.
_suspension = threading.local()


@dataclass
class Ledger:
    start_total: int | None = None
    exempt_bytes: int = 0  # changes made inside guard_suspended()
    approved_bytes: int = 0
    added_items: int = 0
    approved_items: int = 0
    hook_registered: bool = False


def get_ledger(txn=None) -> Ledger:
    txn = txn if txn is not None else transaction.get()
    if hasattr(txn, "set_data"):
        try:
            return txn.data(LEDGER_KEY)
        except KeyError:
            ledger = Ledger()
            txn.set_data(LEDGER_KEY, ledger)
            return ledger
    ledger = _fallback.get(txn)
    if ledger is None:
        ledger = _fallback[txn] = Ledger()
    return ledger


def is_suspended() -> bool:
    return getattr(_suspension, "depth", 0) > 0


@contextmanager
def guard_suspended():
    """Exempt the changes made inside the block from the commit guard.

    Trusted, Python-only API (rebuilds, migrations, imports run by an
    administrator). Applies to the current thread, across commits made inside
    the block; changes made outside the block are still checked.
    """
    caller = inspect.stack(context=0)[2]
    logger.info(
        "quota guard suspended by %s (%s:%d)",
        caller.function,
        caller.filename,
        caller.lineno,
    )
    _suspension.depth = getattr(_suspension, "depth", 0) + 1
    try:
        yield
    finally:
        _suspension.depth -= 1


def _find_portal(*candidates):
    for candidate in (getSite(), *candidates):
        if candidate is None:
            continue
        tool = getToolByName(candidate, "portal_url", None)
        if tool is not None:
            return tool.getPortalObject()
    return None


def _ensure_hook(ledger, context):
    if ledger.hook_registered:
        return
    portal = _find_portal(context)
    if portal is None:
        return
    transaction.get().addBeforeCommitHook(
        check_quota,
        args=(portal.getPhysicalRoot(), portal.getPhysicalPath()),
    )
    ledger.hook_registered = True


def note_index_change(index, delta: int) -> None:
    """Called by ``BlobSizeIndex`` after it applied a non-zero ``delta``."""
    ledger = get_ledger()
    if ledger.start_total is None:
        ledger.start_total = index.total() - delta
    if is_suspended():
        ledger.exempt_bytes += delta
        return
    _ensure_hook(ledger, index)


def record_approved_bytes(n: int) -> None:
    get_ledger().approved_bytes += n


def record_approved_add() -> None:
    get_ledger().approved_items += 1


def on_item_added(obj, event):
    """``IObjectAddedEvent`` subscriber (copies count, moves do not)."""
    if is_suspended():
        return
    ledger = get_ledger()
    ledger.added_items += 1
    _ensure_hook(ledger, obj)


class QuotaCommitAborted(BadRequest):
    """Raised at commit when unapproved changes would cross the hard limit."""

    def __init__(self, reason, mapping):
        self.reason = reason
        self.mapping = mapping
        super().__init__(self.message)

    @property
    def message(self):
        return _(MESSAGES[self.reason], mapping=self.mapping)

    def __str__(self):
        return translate(self.message, context=getRequest())


# ZPublisher derives the response status from the exception class *name*
# (HTTPResponse.setStatus); without this, the subclass would be a 500.
status_codes.setdefault(QuotaCommitAborted.__name__.lower(), 400)


def check_quota(root, portal_path):
    """Before-commit hook: abort unapproved changes that cross the hard limit."""
    portal = root.unrestrictedTraverse(portal_path, None)
    if portal is None:
        return
    # Imported here: usage imports this module (rebuild_usage is suspended).
    from collective.quota.usage import get_index
    from collective.quota.usage import get_total_usage

    with site_context(portal):
        settings = get_settings()
        if settings.hard_bytes <= 0 or get_index(portal) is None:
            return
        total = get_total_usage(portal)  # flushes the indexing queue first
    ledger = get_ledger()
    start = ledger.start_total if ledger.start_total is not None else total
    net_delta = total - start - ledger.exempt_bytes
    mapping = {
        "used": human_readable_size(total),
        "limit": human_readable_size(settings.hard_bytes),
    }
    if (
        net_delta > 0
        and total > settings.hard_bytes
        and settings.policy != ALLOW
        and net_delta > ledger.approved_bytes
    ):
        _abort(UNAPPROVED_BYTES, dict(mapping, delta=human_readable_size(net_delta)))
    if (
        settings.policy == BLOCK_ALL
        and total >= settings.hard_bytes
        and ledger.added_items > ledger.approved_items
    ):
        _abort(UNAPPROVED_ITEMS, mapping)


def _abort(reason, mapping):
    logger.warning(
        "quota guard aborted a transaction (%s, user %s): %s",
        reason,
        getSecurityManager().getUser().getId(),
        mapping,
    )
    raise QuotaCommitAborted(reason, mapping)
