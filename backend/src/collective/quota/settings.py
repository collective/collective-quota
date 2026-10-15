"""Effective quota settings.

Phase 2 stub: ``get_settings()`` returns the built-in defaults. Phase 3 merges the
registry and environment variables (see specs/00-architecture.md, §3.3).
"""

from collective.quota.utils import mb_to_bytes
from dataclasses import dataclass
from dataclasses import field


DEFAULTS = {
    "soft_limit_mb": 0,
    "hard_limit_mb": 0,
    "over_limit_policy": "block_all",
    "max_file_size_mb": 10,
}


@dataclass(frozen=True)
class QuotaSettings:
    soft_bytes: int
    hard_bytes: int
    policy: str
    max_file_bytes: int
    sources: dict[str, str] = field(default_factory=dict)
    locked: frozenset[str] = frozenset()


def get_settings() -> QuotaSettings:
    return QuotaSettings(
        soft_bytes=mb_to_bytes(DEFAULTS["soft_limit_mb"]),
        hard_bytes=mb_to_bytes(DEFAULTS["hard_limit_mb"]),
        policy=DEFAULTS["over_limit_policy"],
        max_file_bytes=mb_to_bytes(DEFAULTS["max_file_size_mb"]),
        sources=dict.fromkeys(DEFAULTS, "default"),
    )
