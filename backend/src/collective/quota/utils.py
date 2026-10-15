"""Shared helpers."""

from plone.base.utils import human_readable_size


__all__ = ["MB", "human_readable_size", "mb_to_bytes"]

MB = 1024 * 1024


def mb_to_bytes(value: int | None) -> int:
    """Convert a size in megabytes to bytes; ``None`` counts as ``0``."""
    return int(value or 0) * MB
