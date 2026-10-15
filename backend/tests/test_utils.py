from collective.quota.utils import human_readable_size
from collective.quota.utils import MB
from collective.quota.utils import mb_to_bytes

import pytest


def test_mb_constant():
    assert MB == 1024 * 1024


@pytest.mark.parametrize(
    "value,expected",
    [(None, 0), (0, 0), (3, 3 * 1024 * 1024)],
)
def test_mb_to_bytes(value, expected):
    assert mb_to_bytes(value) == expected


def test_human_readable_size_reexport():
    assert human_readable_size(3 * MB) == "3.0 MB"
