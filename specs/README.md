# collective.quota — Specification

Last updated: 2026-10-16

`collective.quota` is a Plone add-on that measures the disk space used by uploaded
files and images, lets site administrators configure a soft limit (warnings) and a
hard limit (enforced policy), warns editors when the site is getting full, and gives
them a view to find and delete the biggest items.

This folder is the single source of truth for *what* gets built and *in which order*.
Code lives in `backend/` (Python, Plone 6.2) and, in a later iteration, `frontend/`
(Volto). This iteration is **backend + Classic UI only**.

## How to use these specs

1. Read `00-architecture.md` first. It fixes every name (permissions, views, index,
   registry keys, viewlet, action) and the quota policy semantics. Phase files refer
   to those names and never redefine them.
2. Implement phases in order. Each phase file has a `Status` line and checkboxes.
   Update them as work lands (`[ ]` → `[x]`, `Not started` → `In progress` → `Done`).
3. A phase is `Done` only when all its tasks and tests are checked and its acceptance
   criteria hold on a fresh site **and** on a site with pre-existing content.
4. If implementation reveals that a design detail in a spec is wrong, fix the spec in
   the same change set so the documents never lag behind the code.

### Status legend

| Status | Meaning |
|---|---|
| `Not started` | No code written for this phase |
| `In progress` | Some tasks checked |
| `Done` | All tasks + tests checked, acceptance criteria verified |
| `Deferred` | Out of scope for this iteration; kept for context |

## Phases

| # | File | Title | Status | Depends on |
|---|---|---|---|---|
| 0 | [00-architecture.md](00-architecture.md) | Architecture & canonical names | Reference | — |
| 1 | [phase-01-foundation.md](phase-01-foundation.md) | Foundation: package cleanup, permissions, layers, test fixtures | Done | — |
| 2 | [phase-02-blob-size-index.md](phase-02-blob-size-index.md) | `blob_size` indexer, `BlobSizeIndex` with running total, install-time population | Done | 1 |
| 3 | [phase-03-settings-control-panel.md](phase-03-settings-control-panel.md) | Settings: registry + environment variables + lock flag, control panel, REST control panel adapter | Done | 1, 2 |
| 4 | [phase-04-policy-enforcement.md](phase-04-policy-enforcement.md) | Quota policy, enforcement in Classic forms and REST, transaction commit guard | Done | 2, 3 |
| 5 | [phase-05-disk-usage-view.md](phase-05-disk-usage-view.md) | `@@quota-usage` biggest-items view, multi-delete with link integrity, user-menu entry | Done | 2, 3 |
| 6 | [phase-06-warning-viewlet.md](phase-06-warning-viewlet.md) | Soft/hard limit warning viewlet for editors | Done | 2, 3, 5 |
| 7 | [phase-07-release-readiness.md](phase-07-release-readiness.md) | Uninstall, upgrade scaffolding, i18n, docs, changelog, manual QA | Done | 1–6 |
| 8 | [phase-08-volto-future.md](phase-08-volto-future.md) | REST endpoints and Volto UI | Deferred | 1–7 |

Phases 5 and 6 can be developed in parallel once 2 and 3 are done.

## Conventions

- **Package**: `collective.quota`, code under `backend/src/collective/quota/`, tests under
  `backend/tests/`. Keep the cookieplone sub-package layout (`browser/`, `controlpanels/`,
  `indexers/`, `vocabularies/`, `upgrades/`, `setuphandlers/`, `profiles/`, `locales/`).
- **Commands** (run inside `backend/`): `make install`, `make test`, `make test-coverage`,
  `make lint`, `make format`, `make i18n`, `make create-site`, `make start`.
  Never call `pip`, `uv add` or `pytest` directly in docs; recommend the `make` targets.
- **Tests**: pytest with `pytest-plone` fixtures. Integration layer for unit-ish tests,
  functional layer for browser (`plone.testing.zope.Browser`) and REST (`RelativeSession`).
  **Coverage must be 100 % (lines and branches)**; `make test-coverage` enforces it and
  CI runs it. No `# pragma: no cover`.
- **Configuration**: every setting has a registry record and an environment variable
  (`COLLECTIVE_QUOTA_*`); `COLLECTIVE_QUOTA_LOCK_SETTINGS` makes environment values
  fixed. See `00-architecture.md` §3.3.
- **Style**: ruff (config in `backend/pyproject.toml`), zpretty for XML/ZCML. Single-line
  imports, `from` imports first (ruff isort settings already enforce this).
- **i18n**: message domain `collective.quota`, factory `from collective.quota import _`.
  All user-facing strings go through it. Run `make i18n` after adding strings.
- **Changelog**: one towncrier fragment per change in `backend/news/` (types: `breaking`,
  `feature`, `bugfix`, `internal`, `documentation`, `tests`).
- **Units**: bytes everywhere in code, the catalog, and the registry-derived helpers.
  The control panel is the only place where megabytes (`1 MB = 1024 * 1024 bytes`) are
  entered. Display always goes through `plone.base.utils.human_readable_size`.

## Glossary

| Term | Meaning |
|---|---|
| Blob field | A Dexterity schema field providing `plone.namedfile.interfaces.INamedField` (`NamedFile`, `NamedImage`, `NamedBlobFile`, `NamedBlobImage`), from the type schema or any behavior |
| `blob_size` | Catalog index + metadata column: sum, in bytes, of all blob fields of one content item |
| Total usage | Sum of `blob_size` over the whole site, kept as a running counter inside the index |
| Soft limit | Usage threshold that only triggers warnings |
| Hard limit | Usage threshold above which the configured policy applies |
| Policy | What happens to saves once the hard limit would be exceeded (see architecture doc) |
| Delta | `new_size - old_size` of a save; only saves with a positive delta can be blocked |
| Upload | A new or replaced value for a blob field in a single save |
| Ledger | Per-transaction integers (start total, approved bytes, added/approved items) that validators write and the commit guard checks |
| Commit guard | Before-commit hook that aborts any transaction crossing the hard limit without validator approval |
| Locked setting | A setting whose environment variable is set while `COLLECTIVE_QUOTA_LOCK_SETTINGS` is truthy; the control panel cannot change it |
