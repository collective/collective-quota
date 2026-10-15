"""Over-limit policies: pure decision logic shared by every enforcement hook.

See specs/00-architecture.md, §4 (normative semantics).
"""

from collective.quota import _
from collective.quota.utils import human_readable_size
from dataclasses import dataclass
from dataclasses import field
from zope.schema import ValidationError


BLOCK_ALL = "block_all"
BLOCK_FILES = "block_files"
LIMIT_FILE_SIZE = "limit_file_size"
ALLOW = "allow"

POLICIES = (BLOCK_ALL, BLOCK_FILES, LIMIT_FILE_SIZE, ALLOW)

UPLOAD_BLOCKED = "upload_blocked"
FILE_TOO_LARGE = "file_too_large"
ADD_BLOCKED = "add_blocked"

MESSAGES = {
    UPLOAD_BLOCKED: _(
        "This file cannot be saved: the site has reached its disk quota "
        "(${used} of ${limit}). Delete or shrink existing files first."
    ),
    FILE_TOO_LARGE: _(
        "The site has reached its disk quota (${used} of ${limit}); only files "
        "up to ${max_size} can be added now. This file is ${size}."
    ),
    ADD_BLOCKED: _(
        "New content cannot be added: the site has reached its disk quota "
        "(${used} of ${limit}). Delete or shrink existing files first."
    ),
}


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str | None = None  # UPLOAD_BLOCKED | FILE_TOO_LARGE | ADD_BLOCKED
    mapping: dict = field(default_factory=dict)  # human-readable sizes

    @property
    def message(self):
        """Translatable message (domain ``collective.quota``), None if allowed."""
        if self.reason is None:
            return None
        return _(MESSAGES[self.reason], mapping=self.mapping)


def _sizes(total, settings, **extra):
    mapping = {
        "used": human_readable_size(total),
        "limit": human_readable_size(settings.hard_bytes),
    }
    mapping.update({key: human_readable_size(value) for key, value in extra.items()})
    return mapping


def evaluate_upload(total: int, old_size: int, new_size: int, settings) -> Decision:
    """Decide whether one blob field may change from ``old_size`` to ``new_size``."""
    delta = new_size - old_size
    if settings.hard_bytes <= 0 or delta <= 0 or total + delta <= settings.hard_bytes:
        return Decision(True)
    if settings.policy == ALLOW:
        return Decision(True)
    if settings.policy == LIMIT_FILE_SIZE:
        if new_size <= settings.max_file_bytes:
            return Decision(True)
        mapping = _sizes(
            total, settings, max_size=settings.max_file_bytes, size=new_size
        )
        return Decision(False, FILE_TOO_LARGE, mapping)
    return Decision(False, UPLOAD_BLOCKED, _sizes(total, settings))


def evaluate_add(total: int, settings) -> Decision:
    """Decide whether a new item may be created (only ``block_all`` refuses)."""
    if (
        settings.policy == BLOCK_ALL
        and settings.hard_bytes > 0
        and total >= settings.hard_bytes
    ):
        return Decision(False, ADD_BLOCKED, _sizes(total, settings))
    return Decision(True)


class QuotaExceeded(ValidationError):
    """Raised by the upload validator; carries the Decision."""

    def __init__(self, decision: Decision):
        super().__init__(decision.message)
        self.decision = decision

    def doc(self):
        return self.decision.message
