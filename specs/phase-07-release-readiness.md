# Phase 7 — Uninstall, upgrade scaffolding, i18n, docs, changelog, manual QA

Status: Done (publishing the release is left to the maintainers)
Depends on: Phases 1–6
Last updated: 2026-10-16

## Goal

Ship `collective.quota` 1.0.0a1 for Plone 6.2 Classic: clean uninstall, an upgrade-step
convention ready for the first schema change, complete translations, user and
developer documentation, changelog, and a manual QA pass on a fresh site and on a site
with pre-existing content.

## Scope

In: uninstall profile completeness + test, upgrades package convention, locales,
README/docs, example content for the `initial` profile, towncrier fragments, release
checklist, manual QA script.

Out: Volto (phase 8), PyPI release automation beyond what cookieplone ships.

## Design

### Uninstall profile (final content)

| File | Removes |
|---|---|
| `browserlayer.xml` | `collective.quota`, `collective.quota.restapi` |
| `catalog.xml` | index `blob_size`, column `blob_size` |
| `registry.xml` | records with prefix `collective.quota` |
| `controlpanel.xml` | configlet `collective-quota` |
| `actions.xml` | user action `disk-usage` |
| `viewlets.xml` | order entry `collective.quota.warning` |

The persistent `_total` lives inside the index object, so removing the index drops it.
Content and `_size` attributes on blobs are untouched. Reinstalling runs `post_install`
and repopulates everything.

### Upgrades convention (`upgrades/`)

- Profile version stays `1000` for 1.0.0a1.
- Each future change: bump `profiles/default/metadata.xml`, add
  `upgrades/vXXXX.py` with a function `upgrade(setup_tool)`, register it in
  `upgrades/configure.zcml` with `source`/`destination`, and add a test in
  `tests/setup/test_upgrades.py` that runs it.
- Provide `upgrades/utils.py` now with the two helpers most steps need:
  `run_import_step(setup_tool, "catalog", profile="collective.quota:default")` and
  `rebuild_usage(setup_tool)` (wraps phase 2's `rebuild_usage(portal)` so it can be
  an upgrade handler directly).
- Keep the commented example step in `upgrades/configure.zcml` as the template.

### i18n

- Domain `collective.quota`; `make i18n` regenerates `locales/collective.quota.pot`
  and syncs the existing `.po` files (`de`, `en`, `es`, `it`, `pt_BR`).
- Provide full translations for `en` and `es` (both maintainers' languages); leave
  others with msgids. `en` carries `msgstr` = `msgid`.
- The ZMI "add BlobSizeIndex" form stays untranslated, like the rest of the ZMI.
- `actions.xml`, `controlpanel.xml` and templates must carry `i18n:domain="collective.quota"`.
- Policy vocabulary titles and the viewlet/validator messages are the strings to
  double-check in the `.pot`.

### Example content (`initial` profile)

Replace the Volto-flavoured export with a small Classic sample: one Folder, two Files
(≈ 2 MB and ≈ 500 KB generated binaries), one Image, one Document linking to the first
File (so the link-integrity warning can be demoed). Regenerate with
`make update-example-content PLONE_SITE_ID=<demo site>` after creating the content
on a dev site. The zero-filled sample files cost about nothing in git and the wheel
(both compress them). The importer runs under `guard_suspended()`.

### Documentation

`backend/README.md` (follow `.github/instructions/docs.instructions.md`: emoji section
titles, `make` commands only, concrete feature descriptions, keep the "Generated using"
paragraph): Features, Installation, Configuration (control panel fields with
screenshots placeholders), Permissions, Disk usage view, Warning banner, How usage is
measured (and what is not counted), Rebuilding usage data, For developers (Python API,
how to respect the quota in scripts, how the index works).

`docs/docs/` (Diátaxis skeleton already exists):

| Section | Page |
|---|---|
| Concepts | "How disk usage is measured", "Limits and policies" |
| How-to | "Configure limits", "Configure with environment variables (and lock them)", "Find and delete the biggest files", "Rebuild usage data on a large site", "Grant editors access to disk usage", "Run imports and migrations on a site over quota (`guard_suspended`)" |
| Reference | "Settings", "Environment variables", "Permissions", "Views and viewlet", "Python API", "Catalog index `blob_size`", "Commit guard" |
| Tutorials | "Set up a quota on an existing site" (end-to-end) |

### Changelog

One fragment per phase in `backend/news/` (e.g. `+index.feature`, `+controlpanel.feature`,
`+enforcement.feature`, `+usage-view.feature`, `+viewlet.feature`,
`+drop-plone-volto.breaking`). `towncrier build` happens at release time.

### Release checklist

- [x] `version.txt` / `__version__` = `1.0.0a1`
- [x] `pyproject.toml` classifiers: Plone 6.1 and 6.2, Python 3.11–3.13 (6.1 verified: the full suite passes on Plone 6.1.5)
- [x] `make lint`, `make test-coverage` at 100 % (gate enforced; only `locales/__main__.py` omitted)
- [x] Docker image builds (`make build-image`) and starts (`/ok`, collective.quota 1.0.0a1 on Plone 6.2.2)
- [x] Build sdist/wheel (`uv build`: 1.0.0a1, 108 KB wheel with templates, profiles, example content and locales, no tests)
- [ ] Tag, `towncrier build`, upload — maintainers, at release time

### Manual QA script (Classic UI)

Run twice: (A) fresh site, install add-on, then create content; (B) site with ~50 Files
and Images created **before** installing.

1. Install from Site Setup → Add-ons. No errors; in (B) `@@quota-usage` lists the right
   items immediately.
2. Control panel: set soft 20 MB, hard 30 MB, policy `block_all`. Save. Usage card shows
   totals; "Rebuild usage data" works.
3. As Editor: user menu shows "Disk usage"; view lists items; switch 10/25/50/100.
4. Upload files until > 20 MB: yellow banner appears on every page; not for anonymous.
5. Upload past 30 MB: last upload that crosses is allowed only if it fits; next upload
   is blocked with the field error; adding a Document is blocked with the form error.
6. Switch to `block_files`: Document can be added; upload still blocked.
7. Switch to `limit_file_size` with 1 MB: a 500 KB file goes in, a 2 MB file does not.
8. Switch to `allow`: everything goes in; red banner remains.
9. Replace a big file with a small one on the edit form while over the limit: saved.
10. Create a Document that links to a File; in `@@quota-usage` select that File and
    another one → Delete → warning lists the Document → confirm → both deleted, status
    message shows bytes freed, banner updates.
11. REST (`curl`): POST File with base64 over the limit → 400 with message; PATCH with
    smaller file → 204.
12. Bypass attempts at the hard limit with `block_all`: copy/paste a big File in folder
    contents → error page, nothing pasted; `zconsole` script with
    `plone.api.content.create` → commit raises; same script inside `guard_suspended()`
    → succeeds and the banner shows the new total.
13. Environment: restart with `COLLECTIVE_QUOTA_HARD_LIMIT_MB=50
    COLLECTIVE_QUOTA_OVER_LIMIT_POLICY=block_files` and no lock → control panel shows
    "from environment" and values can still be overridden; add
    `COLLECTIVE_QUOTA_LOCK_SETTINGS=1` → those two fields are read-only, REST PATCH is
    refused, enforcement uses the env values regardless of the registry.
14. Uninstall: layers, index, column, records, configlet, action, viewlet order gone;
    pages render; reinstall repopulates.

## Files

Create:
- `backend/src/collective/quota/upgrades/utils.py`
- `backend/src/collective/quota/profiles/uninstall/{catalog,registry,controlpanel,actions,viewlets}.xml` (if not created in earlier phases)
- `backend/news/*.feature|breaking`
- `docs/docs/**` pages listed above
- `backend/tests/setup/test_upgrades.py`

Modify:
- `backend/README.md`, root `README.md` (features paragraph only)
- `backend/src/collective/quota/locales/**`
- `backend/src/collective/quota/setuphandlers/examplecontent/**`
- `backend/src/collective/quota/upgrades/configure.zcml` (keep template)
- `version.txt`, `backend/src/collective/quota/__init__.py`

## Tasks

- [x] Verify every uninstall file exists and is registered by the `uninstall` profile
- [x] `upgrades/utils.py` + documented convention
- [x] `make i18n`; translate `en` and `es`; ensure no untranslated UI strings remain in templates/XML
- [x] Regenerate example content for Classic
- [x] Write `backend/README.md` sections and `docs/docs` pages; `make docs-build` (or the docs Makefile target) passes
- [x] Towncrier fragments for all phases
- [x] Coverage report at 100 % with the gate on in CI
- [x] Run the manual QA script in scenario (A) and (B); record results in this file under "QA log"
- [x] Release checklist

## Tests

- [x] `tests/setup/test_setup_uninstall.py` — after uninstall: no index, no column, no registry records, no configlet, no `disk-usage` action, no viewlet order entry, no layers; `get_total_usage()` returns 0 without raising; `@@quota-usage` is not traversable
- [x] `tests/setup/test_setup_install.py::test_reinstall_repopulates`
- [x] `tests/setup/test_upgrades.py` — upgrade registry lists no pending steps for a fresh install; the `utils` helpers run
- [x] `tests/test_i18n.py` — every `.po` file compiles (`msgfmt --check` equivalent via `python-gettext`), `.pot` contains the key msgids (`Disk usage`, `Quota settings`, policy titles)
- [x] `tests/test_example_content.py` — `initial` profile imports on a Classic site and the Files end up in the index (import runs under `guard_suspended()`)
- [x] `tests/test_docs_env_table.py` — the environment variables documented in `backend/README.md` match `settings.ENV_VARS` + `LOCK_VAR` (keeps docs honest)

## Acceptance criteria

- Install → configure → use → uninstall → reinstall leaves no trace and no errors on
  both scenarios.
- Documentation lets a site administrator configure the quota without reading code,
  and a developer extend it without reading this spec.

## Implementation notes (2026-10-16)

- **`guard_suspended()` also skips hooks A and C.** `plone.exportimport` creates
  content through the plone.restapi deserializer, so on a site over its limit the
  example-content import (and any administrator import) was refused by the upload
  validator before the commit guard was reached. Suspension is thread-local and only
  reachable from Python, so the validators now step aside inside the block too.
  Architecture §5.1 is updated.
- **REST `@search` on `blob_size` failed** (`'<' not supported between 'int' and
  'str'`): plone.restapi parses query strings per index class and leaves values of
  `FieldIndex` subclasses as strings. `restapi/query.py` registers an integer
  `IIndexQueryParser` for `BlobSizeIndex`. Found during QA.
- **Plone 6.1** pins `pytest-plone==1.0.0a2`, which lacks `functional_app`; `mx.ini`
  overrides it to `1.1.0` and the test extra requires `pytest-plone>=1.1.0`, so the CI
  matrix (6.1 and 6.2) installs a working test runner.
- The package description (cookieplone placeholder) is replaced everywhere in the
  backend, the root README and the docs; the frontend keeps it until phase 8.
- `plone.exportimport` commits while importing, so `test_example_content.py` runs on
  the functional layer. The scaffold's Volto example-content test is replaced by it.
- `backend/scripts/rebuild_blob_size.py` is not in the wheel; the docs link to it in
  the repository and say that a FileStorage site must be stopped first.
- Docs: Diátaxis pages written; `make html` builds without warnings and `make vale`
  reports 0 errors (style warnings such as "click" are kept, like Plone's own docs).
  Project words are in `docs/styles/config/vocabularies/Base/accept.txt`.

## QA log

The manual script was automated over HTTP (`requests`, port 8091) plus `zconsole`
for step 12's script checks, on temporary sites deleted afterwards. Users: `admin`
(Manager) and `editor` (Editor + Contributor).

| Date | Scenario | Plone | Result | Notes |
|---|---|---|---|---|
| 2026-10-16 | A: fresh site, install, then content | 6.2.2 | 14/14 steps pass | Steps 4–5 with 7 MB uploads against soft 20 / hard 30 MB |
| 2026-10-16 | B: 40 Files + 10 Images created before install | 6.2.2 | 14/14 steps pass | Right after install `@@quota-usage` listed `file39`, `file38`, `file37`… (25 rows) |

Per step, both scenarios:

1. Installed from **Add-ons**; (B) listing and total correct immediately.
2. Control panel saved soft 20 / hard 30 / `block_all`; usage card showed 30.0 MB;
   "Rebuild usage data" reported the item count.
3. Editor's user menu had "Disk usage"; limits 10/50/100 preselected.
4. Over 20 MB: yellow banner on the site root and a folder for the editor, none for
   anonymous.
5. The upload that still fitted (30 MB − 64 KB) was saved; the next 1 MB and a 2 MB
   upload got "This file cannot be saved…" on the field; adding a Document got "New
   content cannot be added…".
6. `block_files`: Document added, 500 KB upload refused.
7. `limit_file_size` 1 MB: 500 KB saved, 2 MB refused ("only files up to 1.0 MB").
8. `allow`: uploads over the limit saved, red banner.
9. Edit form, `block_all`, over the limit: 7 MB file replaced with 100 KB, "Changes
   saved".
10. Selected a File linked from a Document plus another file: confirmation listed 2
    items with the link-integrity warning naming the Document; confirm → "Deleted 2
    items, freeing 9.0 MB."; total went down.
11. REST: POST of a file larger than the room left → 400 with the quota message;
    PATCH with a 10 KB file → 204.
12. `object_copy`/`object_paste` over the limit → 400 "Disk quota exceeded", nothing
    pasted. zconsole: `plone.api.content.create` of 2 MB over an 18 MB hard limit →
    `transaction.commit()` raised `QuotaCommitAborted` and left nothing; the same
    create inside `guard_suspended()` committed and the red banner showed the new
    19.4 MB total.
13. Restart with `COLLECTIVE_QUOTA_HARD_LIMIT_MB=50`,
    `COLLECTIVE_QUOTA_OVER_LIMIT_POLICY=block_files`: control panel showed both as
    "env" and saving 60 overrode the hard limit ("registry"). Restart with hard 1,
    `block_files` and `COLLECTIVE_QUOTA_LOCK_SETTINGS=1`, registry set to 100 MB /
    `allow`: lock alert, fields read-only, REST PATCH → 400, `effective` = 1 /
    `block_files`, a 1 MB upload refused, a Document allowed.
14. Uninstall: pages render, no banner, no user action, `@@quota-usage` and
    `@@quota-controlpanel` → 404, configlet gone, 3 MB upload saved without limits.
    Reinstall: the file uploaded while uninstalled is listed and counted. Uninstalled
    again at the end. (The first pass of this check used a regex that could not match
    `afteruninstall.bin`; it was rerun with the fixed regex.)

Bugs found by the QA run, in the QA script itself, were fixed and the affected steps
rerun on freshly created sites; the add-on bugs it found (REST `@search` on
`blob_size`) are listed in the implementation notes.
