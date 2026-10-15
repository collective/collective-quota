"""Commit guard internals: ledger storage, hook registration, check matrix."""

from collective.quota import guard
from collective.quota.guard import check_quota
from collective.quota.guard import get_ledger
from collective.quota.guard import guard_suspended
from collective.quota.guard import is_suspended
from collective.quota.guard import Ledger
from collective.quota.guard import LEDGER_KEY
from collective.quota.guard import note_index_change
from collective.quota.guard import on_item_added
from collective.quota.guard import QuotaCommitAborted
from collective.quota.guard import record_approved_add
from collective.quota.guard import record_approved_bytes
from zope.component.hooks import getSite
from zope.component.hooks import setSite

import logging
import pytest
import transaction


MB = 1024 * 1024


def hooks():
    return [hook for hook, _args, _kws in transaction.get().getBeforeCommitHooks()]


def fresh_ledger(**fields):
    ledger = Ledger(**fields)
    transaction.get().set_data(LEDGER_KEY, ledger)
    return ledger


class FakeIndex:
    def __init__(self, total):
        self._total = total

    def total(self):
        return self._total


class TestLedgerStorage:
    def test_ledger_created_once_per_transaction_and_cleared_after_commit(self):
        tm = transaction.TransactionManager()
        txn = tm.begin()
        ledger = get_ledger(txn)
        assert get_ledger(txn) is ledger
        ledger.approved_bytes = 5
        tm.commit()
        assert get_ledger(tm.begin()) == Ledger()
        tm.abort()

    def test_fallback_storage_when_transaction_lacks_set_data(self):
        class OldTransaction:
            pass

        txn = OldTransaction()
        ledger = get_ledger(txn)
        assert get_ledger(txn) is ledger
        assert guard._fallback[txn] is ledger
        del txn
        assert len(guard._fallback) == 0  # weak keys: gone with the transaction

    def test_default_is_current_transaction(self):
        assert get_ledger() is get_ledger(transaction.get())

    def test_record_helpers(self):
        record_approved_bytes(10)
        record_approved_bytes(5)
        record_approved_add()
        ledger = get_ledger()
        assert (ledger.approved_bytes, ledger.approved_items) == (15, 1)


class TestHookRegistration:
    def test_note_index_change_sets_start_total_once_and_registers_hook_once(
        self, portal
    ):
        fresh_ledger()
        note_index_change(FakeIndex(1000), 300)
        note_index_change(FakeIndex(1500), 500)
        ledger = get_ledger()
        assert ledger.start_total == 700
        assert ledger.hook_registered
        assert hooks().count(check_quota) == 1
        (args,) = [
            a
            for h, a, _k in transaction.get().getBeforeCommitHooks()
            if h is check_quota
        ]
        assert args == (portal.getPhysicalRoot(), portal.getPhysicalPath())

    def test_item_added_counts_and_registers_once(self, portal):
        fresh_ledger()
        on_item_added(portal, None)
        on_item_added(portal, None)
        assert get_ledger().added_items == 2
        assert hooks().count(check_quota) == 1

    def test_suspended_changes_are_exempt_and_register_nothing(self, portal):
        fresh_ledger()
        with guard_suspended():
            note_index_change(FakeIndex(1000), 300)
            on_item_added(portal, None)
        ledger = get_ledger()
        assert (ledger.start_total, ledger.exempt_bytes, ledger.added_items) == (
            700,
            300,
            0,
        )
        assert check_quota not in hooks()

    def test_portal_found_from_object_without_site(self, portal):
        fresh_ledger()
        site = getSite()
        setSite(None)
        try:
            on_item_added(portal, None)
        finally:
            setSite(site)
        assert check_quota in hooks()

    def test_no_portal_no_hook(self, portal):
        fresh_ledger()
        site = getSite()
        setSite(None)
        try:
            on_item_added(object(), None)
        finally:
            setSite(site)
        assert check_quota not in hooks()
        assert not get_ledger().hook_registered


class TestSuspension:
    def test_guard_suspended_restores_previous_state_and_logs_caller(self, caplog):
        assert not is_suspended()
        with (
            caplog.at_level(logging.INFO, logger="collective.quota"),
            guard_suspended(),
        ):
            with guard_suspended():
                assert is_suspended()
            assert is_suspended()
        assert not is_suspended()
        messages = [r.getMessage() for r in caplog.records]
        assert len(messages) == 2
        assert "quota guard suspended by " in messages[0]
        assert (
            "test_guard_suspended_restores_previous_state_and_logs_caller"
            in (messages[0])
        )
        assert "test_guard_unit.py" in messages[0]

    def test_suspension_restored_on_error(self):
        with pytest.raises(RuntimeError), guard_suspended():
            raise RuntimeError
        assert not is_suspended()


class TestCheckQuota:
    @pytest.fixture
    def site_2mb(self, portal, make_file, set_quota):
        """A site holding 2 MB, with a clean ledger and the given limits."""
        make_file(portal, "a", 2 * MB)

        def func(hard_mb=1, policy="block_all", **ledger):
            set_quota(hard_mb=hard_mb, policy=policy)
            fresh_ledger(**ledger)

        return func

    def run(self, portal):
        check_quota(portal.getPhysicalRoot(), portal.getPhysicalPath())

    @pytest.mark.parametrize(
        "hard_mb,policy,ledger",
        [
            (0, "block_all", {"start_total": 0, "added_items": 3}),  # disabled
            (1, "block_files", {"start_total": 2 * MB}),  # net 0
            (1, "block_files", {"start_total": 3 * MB}),  # net < 0 (deletion)
            (10, "block_all", {"start_total": 0}),  # under the limit
            (1, "block_all", {"start_total": 0, "approved_bytes": 2 * MB}),
            (1, "allow", {"start_total": 0, "added_items": 1}),
            (1, "block_files", {"start_total": 2 * MB, "added_items": 1}),
            (
                1,
                "block_all",
                {"start_total": 2 * MB, "added_items": 1, "approved_items": 1},
            ),
            (10, "block_all", {"start_total": 2 * MB, "added_items": 1}),  # below hard
            (1, "block_all", {"start_total": 0, "exempt_bytes": 2 * MB}),
            (1, "block_all", {}),  # no index change in this transaction
        ],
    )
    def test_allowed(self, portal, site_2mb, hard_mb, policy, ledger):
        site_2mb(hard_mb=hard_mb, policy=policy, **ledger)
        self.run(portal)

    @pytest.mark.parametrize(
        "hard_mb,policy,ledger,reason",
        [
            (1, "block_all", {"start_total": 0}, "unapproved_bytes"),
            (
                1,
                "block_files",
                {"start_total": 0, "approved_bytes": MB},
                "unapproved_bytes",
            ),
            (1, "limit_file_size", {"start_total": 0}, "unapproved_bytes"),
            (
                2,
                "block_all",
                {"start_total": 2 * MB, "added_items": 1},
                "unapproved_items",
            ),
            (
                1,
                "block_all",
                {"start_total": 2 * MB, "added_items": 2, "approved_items": 1},
                "unapproved_items",
            ),
        ],
    )
    def test_aborted(self, portal, site_2mb, hard_mb, policy, ledger, reason, caplog):
        site_2mb(hard_mb=hard_mb, policy=policy, **ledger)
        with (
            caplog.at_level(logging.WARNING, logger="collective.quota"),
            pytest.raises(QuotaCommitAborted) as excinfo,
        ):
            self.run(portal)
        assert excinfo.value.reason == reason
        assert f"quota guard aborted a transaction ({reason}" in caplog.text

    def test_portal_gone(self, portal, site_2mb):
        site_2mb(start_total=0)
        check_quota(portal.getPhysicalRoot(), ("", "nonexistent"))

    def test_index_missing(self, portal, site_2mb):
        site_2mb(start_total=0)
        portal.portal_catalog.delIndex("blob_size")
        self.run(portal)


class TestQuotaCommitAborted:
    def test_quota_commit_aborted_message_translated(self):
        error = QuotaCommitAborted(
            "unapproved_bytes", {"delta": "2.0 MB", "used": "3.0 MB", "limit": "1.0 MB"}
        )
        assert str(error) == (
            "The change was cancelled: it would add 2.0 MB to the site and exceed "
            "the disk quota (3.0 MB of 1.0 MB)."
        )
        assert error.message.domain == "collective.quota"

    def test_items_message(self):
        error = QuotaCommitAborted(
            "unapproved_items", {"used": "3.0 MB", "limit": "1.0 MB"}
        )
        assert str(error) == (
            "The change was cancelled: new content cannot be added while the site "
            "exceeds its disk quota (3.0 MB of 1.0 MB)."
        )
