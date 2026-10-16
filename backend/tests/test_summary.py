from collective.quota.browser.summary import level_message
from collective.quota.browser.summary import usage_summary
from collective.quota.settings import QuotaSettings
from collective.quota.usage import UsageInfo
from zope.i18n import translate

import pytest


MB = 1024 * 1024


def settings(policy="block_all", max_file_mb=10):
    return QuotaSettings(
        soft_bytes=0, hard_bytes=0, policy=policy, max_file_bytes=max_file_mb * MB
    )


def info(total, soft=0, hard=0, level="ok"):
    percent = total * 100 // hard if hard else None
    return UsageInfo(total=total, soft=soft, hard=hard, percent=percent, level=level)


class TestLevelMessage:
    def test_none_when_ok(self):
        assert level_message(info(MB, hard=10 * MB), settings()) is None

    def test_warning_against_hard_limit(self):
        message = level_message(
            info(6 * MB, soft=5 * MB, hard=10 * MB, level="warning"), settings()
        )
        assert translate(message) == (
            "Disk usage warning: this site uses 6.0 MB of 10.0 MB (60%). "
            "Please review large files before the limit is reached."
        )

    def test_warning_against_soft_limit_without_hard(self):
        message = level_message(info(6 * MB, soft=4 * MB, level="warning"), settings())
        assert "uses 6.0 MB of 4.0 MB (150%)" in translate(message)

    @pytest.mark.parametrize(
        "policy,hint",
        [
            (
                "block_all",
                "New content and uploads are blocked until files are removed.",
            ),
            ("block_files", "Uploads are blocked until files are removed."),
            (
                "limit_file_size",
                "Only files up to 3.0 MB can be uploaded until files are removed.",
            ),
            ("allow", "Uploads are still allowed."),
        ],
    )
    def test_exceeded_with_policy_hint(self, policy, hint):
        message = level_message(
            info(12 * MB, hard=10 * MB, level="exceeded"),
            settings(policy=policy, max_file_mb=3),
        )
        assert translate(message) == (
            f"Disk quota exceeded: this site uses 12.0 MB of 10.0 MB. {hint}"
        )


class TestUsageSummary:
    def test_values(self):
        summary = usage_summary(
            info(12 * MB, soft=5 * MB, hard=10 * MB, level="exceeded"), settings()
        )
        assert summary == {
            "total": "12.0 MB",
            "hard": "10.0 MB",
            "soft": "5.0 MB",
            "percent": 120,
            "width": 100,
            "level": "exceeded",
            "bar_class": "bg-danger",
            "policy": "Block new items and any upload that adds bytes",
        }

    def test_limits_disabled(self):
        summary = usage_summary(info(MB), settings(policy="unknown"))
        assert summary["hard"] is None
        assert summary["soft"] is None
        assert summary["width"] == 0
        assert summary["bar_class"] == "bg-success"
        assert summary["policy"] == "unknown"
