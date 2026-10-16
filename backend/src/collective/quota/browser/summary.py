"""Usage summary and alert texts shared by the control panel, ``@@quota-usage``
and the warning viewlet."""

from collective.quota import _
from collective.quota.policy import ALLOW
from collective.quota.policy import BLOCK_ALL
from collective.quota.policy import BLOCK_FILES
from collective.quota.policy import LIMIT_FILE_SIZE
from collective.quota.settings import QuotaSettings
from collective.quota.usage import LEVEL_EXCEEDED
from collective.quota.usage import LEVEL_WARNING
from collective.quota.usage import UsageInfo
from collective.quota.utils import human_readable_size
from collective.quota.vocabularies.policies import POLICY_TITLES
from zope.i18nmessageid import Message


LEVEL_BARS = {
    LEVEL_EXCEEDED: "bg-danger",
    LEVEL_WARNING: "bg-warning",
}

ALERT_CLASSES = {
    LEVEL_WARNING: "alert-warning",
    LEVEL_EXCEEDED: "alert-danger",
}


POLICY_HINTS = {
    BLOCK_ALL: _("New content and uploads are blocked until files are removed."),
    BLOCK_FILES: _("Uploads are blocked until files are removed."),
    ALLOW: _("Uploads are still allowed."),
}


def policy_hint(settings: QuotaSettings) -> Message:
    if settings.policy == LIMIT_FILE_SIZE:
        return _(
            "Only files up to ${max_size} can be uploaded until files are removed.",
            mapping={"max_size": human_readable_size(settings.max_file_bytes)},
        )
    return POLICY_HINTS[settings.policy]


def level_message(info: UsageInfo, settings: QuotaSettings) -> Message | None:
    """Alert text for the usage level; ``None`` when usage is below the limits."""
    used = human_readable_size(info.total)
    if info.level == LEVEL_EXCEEDED:
        return _(
            "Disk quota exceeded: this site uses ${used} of ${limit}. ${policy_hint}",
            mapping={
                "used": used,
                "limit": human_readable_size(info.hard),
                "policy_hint": policy_hint(settings),
            },
        )
    if info.level == LEVEL_WARNING:
        # Measure against the hard limit when there is one, else the soft one.
        limit = info.hard or info.soft
        return _(
            "Disk usage warning: this site uses ${used} of ${limit} (${percent}%). "
            "Please review large files before the limit is reached.",
            mapping={
                "used": used,
                "limit": human_readable_size(limit),
                "percent": info.total * 100 // limit,
            },
        )
    return None


def usage_summary(info: UsageInfo, settings: QuotaSettings) -> dict:
    """Display values for the usage card."""
    return {
        "total": human_readable_size(info.total),
        "hard": human_readable_size(info.hard) if info.hard else None,
        "soft": human_readable_size(info.soft) if info.soft else None,
        "percent": info.percent,
        "width": min(info.percent or 0, 100),
        "level": info.level,
        "bar_class": LEVEL_BARS.get(info.level, "bg-success"),
        "policy": POLICY_TITLES.get(settings.policy, settings.policy),
    }
