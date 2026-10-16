"""The documented environment variables match the code."""

from collective.quota.settings import ENV_VARS
from collective.quota.settings import LOCK_VAR
from pathlib import Path

import re


ROOT = Path(__file__).parent.parent.parent
DOCUMENTS = (
    ROOT / "backend" / "README.md",
    ROOT / "docs" / "docs" / "reference" / "environment-variables.md",
)
ROW = re.compile(r"^\| `(COLLECTIVE_QUOTA_\w+)` \|", re.M)


def documented(path):
    return set(ROW.findall(path.read_text()))


def test_env_tables_match_settings():
    expected = {*ENV_VARS.values(), LOCK_VAR}
    for path in DOCUMENTS:
        assert documented(path) == expected, path
