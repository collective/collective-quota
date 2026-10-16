"""Translation catalogs."""

from collective.quota.vocabularies.policies import POLICY_TITLES
from pathlib import Path
from pythongettext.msgfmt import Msgfmt

import ast
import pytest
import re


LOCALES = Path(__file__).parent.parent / "src" / "collective" / "quota" / "locales"
PO_FILES = sorted(LOCALES.glob("*/LC_MESSAGES/collective.quota.po"))
PLACEHOLDER = re.compile(r"\$\{(\w+)\}")
KEY_MSGIDS = (
    "Disk usage",
    "Quota settings",
    "Review disk usage",
    *(str(title) for title in POLICY_TITLES.values()),
)


ENTRY = re.compile(r'^msgid ((?:".*"\n)+)msgstr ((?:".*"\n)+)', re.M)


def joined(lines):
    return "".join(ast.literal_eval(line) for line in lines.splitlines())


def catalog(path):
    """{msgid: msgstr} of a .po/.pot file, without the header."""
    messages = Msgfmt(path.read_bytes().splitlines(keepends=True), name=str(path))
    assert messages.getAsFile()  # compiles
    entries = {joined(i): joined(s) for i, s in ENTRY.findall(path.read_text())}
    entries.pop("")
    return entries


def test_po_files_found():
    assert {path.parent.parent.name for path in PO_FILES} == {
        "de",
        "en",
        "es",
        "it",
        "pt_BR",
    }


@pytest.mark.parametrize("path", PO_FILES, ids=lambda p: p.parent.parent.name)
def test_po_compiles(path):
    """Msgfmt raises PoSyntaxError on a broken catalog."""
    assert catalog(path)


@pytest.mark.parametrize("msgid", KEY_MSGIDS)
def test_pot_contains_key_msgids(msgid):
    assert msgid in catalog(LOCALES / "collective.quota.pot")


@pytest.mark.parametrize("lang", ["en", "es"])
def test_fully_translated(lang):
    pot = catalog(LOCALES / "collective.quota.pot")
    po = catalog(LOCALES / lang / "LC_MESSAGES" / "collective.quota.po")
    assert set(po) == set(pot)
    assert [msgid for msgid, msgstr in po.items() if not msgstr] == []


@pytest.mark.parametrize("path", PO_FILES, ids=lambda p: p.parent.parent.name)
def test_placeholders_kept(path):
    for msgid, msgstr in catalog(path).items():
        if msgstr:
            assert set(PLACEHOLDER.findall(msgstr)) == set(PLACEHOLDER.findall(msgid))
