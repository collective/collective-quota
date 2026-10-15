# Phase 7 — Uninstall, upgrade scaffolding, i18n, docs, changelog, manual QA

Status: Not started
Depends on: Phases 1–6
Last updated: 2026-10-15

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
  `run_import_step(setup_tool, "collective.quota:default", "catalog")` and
  `rebuild_usage(portal)` (from phase 2).
- Keep the commented example step in `upgrades/configure.zcml` as the template.

### i18n

- Domain `collective.quota`; `make i18n` regenerates `locales/collective.quota.pot`
  and syncs the existing `.po` files (`de`, `en`, `es`, `it`, `pt_BR`).
- Provide full translations for `en` and `es` (both maintainers' languages); leave
  others with msgids.
- `actions.xml`, `controlpanel.xml` and templates must carry `i18n:domain="collective.quota"`.
- Policy vocabulary titles and the viewlet/validator messages are the strings to
  double-check in the `.pot`.

### Example content (`initial` profile)

Replace the Volto-flavoured export with a small Classic sample: one Folder, two Files
(≈ 2 MB and ≈ 500 KB generated binaries), one Image, one Document linking to the first
File (so the link-integrity warning can be demoed). Regenerate with
`make update-example-content` after creating the content on a dev site.

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

- [ ] `version.txt` / `__version__` = `1.0.0a1`
- [ ] `pyproject.toml` classifiers: Plone 6.1 and 6.2, Python 3.11–3.13 (verify 6.1 actually works or drop it)
- [ ] `make lint`, `make test-coverage` at 100 % (gate enforced; only `locales/__main__.py` omitted)
- [ ] Docker image builds (`make build-image`)
- [ ] Tag, `towncrier build`, build sdist/wheel, upload

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

- [ ] Verify every uninstall file exists and is registered by the `uninstall` profile
- [ ] `upgrades/utils.py` + documented convention
- [ ] `make i18n`; translate `en` and `es`; ensure no untranslated UI strings remain in templates/XML
- [ ] Regenerate example content for Classic
- [ ] Write `backend/README.md` sections and `docs/docs` pages; `make docs-build` (or the docs Makefile target) passes
- [ ] Towncrier fragments for all phases
- [ ] Coverage report at 100 % with the gate on in CI
- [ ] Run the manual QA script in scenario (A) and (B); record results in this file under "QA log"
- [ ] Release checklist

## Tests

- [ ] `tests/setup/test_setup_uninstall.py` — after uninstall: no index, no column, no registry records, no configlet, no `disk-usage` action, no viewlet order entry, no layers; `get_total_usage()` returns 0 without raising; `@@quota-usage` is not traversable
- [ ] `tests/setup/test_setup_install.py::test_reinstall_repopulates`
- [ ] `tests/setup/test_upgrades.py` — upgrade registry lists no pending steps for a fresh install; the `utils` helpers run
- [ ] `tests/test_i18n.py` — every `.po` file compiles (`msgfmt --check` equivalent via `python-gettext`), `.pot` contains the key msgids (`Disk usage`, `Quota settings`, policy titles)
- [ ] `tests/test_example_content.py` — `initial` profile imports on a Classic site and the Files end up in the index (import runs under `guard_suspended()`)
- [ ] `tests/test_docs_env_table.py` — the environment variables documented in `backend/README.md` match `settings.ENV_VARS` + `LOCK_VAR` (keeps docs honest)

## Acceptance criteria

- Install → configure → use → uninstall → reinstall leaves no trace and no errors on
  both scenarios.
- Documentation lets a site administrator configure the quota without reading code,
  and a developer extend it without reading this spec.

## QA log

| Date | Scenario | Plone | Result | Notes |
|---|---|---|---|---|
| | | | | |
