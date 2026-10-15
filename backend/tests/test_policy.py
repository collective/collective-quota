"""Policy decisions: the semantics table of specs/00-architecture.md, §4."""

from collective.quota.policy import ADD_BLOCKED
from collective.quota.policy import ALLOW
from collective.quota.policy import BLOCK_ALL
from collective.quota.policy import BLOCK_FILES
from collective.quota.policy import Decision
from collective.quota.policy import evaluate_add
from collective.quota.policy import evaluate_upload
from collective.quota.policy import FILE_TOO_LARGE
from collective.quota.policy import LIMIT_FILE_SIZE
from collective.quota.policy import QuotaExceeded
from collective.quota.policy import UPLOAD_BLOCKED
from collective.quota.settings import QuotaSettings
from zope.i18n import translate

import pytest


MB = 1024 * 1024


def settings(policy=BLOCK_ALL, hard=100, max_file=20):
    return QuotaSettings(
        soft_bytes=0,
        hard_bytes=hard * MB,
        policy=policy,
        max_file_bytes=max_file * MB,
    )


ALL = (BLOCK_ALL, BLOCK_FILES, LIMIT_FILE_SIZE, ALLOW)


class TestEvaluateUpload:
    # (total MB, old MB, new MB) -> expected per policy
    @pytest.mark.parametrize("policy", ALL)
    @pytest.mark.parametrize(
        "total,old,new",
        [
            (95, 0, 3),  # stays under the limit
            (95, 0, 5),  # exactly at the limit
            (120, 40, 20),  # replace with a smaller file, over the limit
            (120, 20, 20),  # same size
            (120, 20, 0),  # cleared
        ],
    )
    def test_always_allowed(self, policy, total, old, new):
        decision = evaluate_upload(total * MB, old * MB, new * MB, settings(policy))
        assert decision == Decision(True)
        assert decision.message is None

    @pytest.mark.parametrize("policy", ALL)
    def test_hard_disabled(self, policy):
        decision = evaluate_upload(500 * MB, 0, 300 * MB, settings(policy, hard=0))
        assert decision.allowed

    @pytest.mark.parametrize(
        "policy,new,allowed,reason",
        [
            (BLOCK_ALL, 10, False, UPLOAD_BLOCKED),
            (BLOCK_FILES, 10, False, UPLOAD_BLOCKED),
            (LIMIT_FILE_SIZE, 10, True, None),
            (LIMIT_FILE_SIZE, 20, True, None),  # exactly the cap
            (LIMIT_FILE_SIZE, 30, False, FILE_TOO_LARGE),
            (ALLOW, 30, True, None),
        ],
    )
    def test_crossing_the_limit(self, policy, new, allowed, reason):
        decision = evaluate_upload(95 * MB, 0, new * MB, settings(policy))
        assert decision.allowed is allowed
        assert decision.reason == reason

    @pytest.mark.parametrize(
        "policy,allowed",
        [
            (BLOCK_ALL, False),
            (BLOCK_FILES, False),
            (LIMIT_FILE_SIZE, True),
            (ALLOW, True),
        ],
    )
    def test_staying_above_the_limit(self, policy, allowed):
        """Replacing a 1 MB file with a 2 MB one at 120 MB adds bytes."""
        decision = evaluate_upload(120 * MB, 1 * MB, 2 * MB, settings(policy))
        assert decision.allowed is allowed


class TestEvaluateAdd:
    @pytest.mark.parametrize(
        "policy,total,allowed",
        [
            (BLOCK_ALL, 99, True),
            (BLOCK_ALL, 100, False),
            (BLOCK_ALL, 120, False),
            (BLOCK_FILES, 120, True),
            (LIMIT_FILE_SIZE, 120, True),
            (ALLOW, 120, True),
        ],
    )
    def test_policies(self, policy, total, allowed):
        decision = evaluate_add(total * MB, settings(policy))
        assert decision.allowed is allowed
        assert decision.reason == (None if allowed else ADD_BLOCKED)

    def test_hard_disabled(self):
        assert evaluate_add(500 * MB, settings(BLOCK_ALL, hard=0)).allowed


class TestMessages:
    def test_messages_have_human_readable_sizes(self):
        decision = evaluate_upload(
            95 * MB, 0, 30 * MB, settings(LIMIT_FILE_SIZE, max_file=20)
        )
        text = translate(decision.message)
        assert text == (
            "The site has reached its disk quota (95.0 MB of 100.0 MB); only files "
            "up to 20.0 MB can be added now. This file is 30.0 MB."
        )
        assert decision.message.domain == "collective.quota"

    def test_upload_blocked_message(self):
        decision = evaluate_upload(95 * MB, 0, 10 * MB, settings(BLOCK_FILES))
        assert translate(decision.message) == (
            "This file cannot be saved: the site has reached its disk quota "
            "(95.0 MB of 100.0 MB). Delete or shrink existing files first."
        )

    def test_add_blocked_message(self):
        decision = evaluate_add(2 * 1024 * MB, settings(BLOCK_ALL, hard=1024))
        assert translate(decision.message) == (
            "New content cannot be added: the site has reached its disk quota "
            "(2.0 GB of 1.0 GB). Delete or shrink existing files first."
        )

    def test_quota_exceeded_carries_decision(self):
        decision = evaluate_upload(95 * MB, 0, 10 * MB, settings(BLOCK_ALL))
        error = QuotaExceeded(decision)
        assert error.decision is decision
        assert error.doc() == decision.message
        assert error.doc().mapping == decision.mapping
