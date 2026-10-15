"""Commit guard (hook D).

Phase 2 stub: the index already reports its changes here and ``rebuild_usage``
already runs suspended, so phase 4 can implement the guard without changing
either call site.
"""

from contextlib import contextmanager


def note_index_change(index, delta: int) -> None:
    """Called by ``BlobSizeIndex`` after it applied a non-zero ``delta``."""


@contextmanager
def guard_suspended():
    """Disable the commit guard for the current transaction (trusted code only)."""
    yield
