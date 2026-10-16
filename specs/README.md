# collective.quota — Specification

Last updated: 2026-10-16

`collective.quota` is a Plone add-on that measures the disk space used by uploaded
files and images, lets site administrators configure a soft limit (warnings) and a
hard limit (enforced policy), warns editors when the site is getting full, and gives
them a view to find and delete the biggest items.

This folder is the single source of truth for *what* gets built and *in which order*.
Code lives in `backend/` (Python, Plone 6.2) and `frontend/` (Volto 19 add-on).
Phases 1–8 (backend, Classic UI and REST API) are done. Phase 9 adds the Volto
add-on. The backend package works on its own; the Volto add-on needs the backend
add-on installed, and neither one changes how the other behaves (`00-architecture.md`
§1.1 fixes the rules).

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
| 8 | [phase-08-rest-api.md](phase-08-rest-api.md) | REST API for Volto: `@quota-usage`, `@quota-rebuild`, `quota` expansion, shared listing, `acceptance` extra | Done | 1–7 |
| 9 | [phase-09-volto-addon.md](phase-09-volto-addon.md) | Volto add-on: user-menu entry, banner, disk usage page with delete, control panel, i18n, Cypress | In progress | 8 |

Phases 5 and 6 can be developed in parallel once 2 and 3 are done. Phase 9's components
can be built against the JSON documented in phase 8 while phase 8 is in progress, but
phase 9 is `Done` only against the real services.

## Conventions

- **Package**: `collective.quota`, code under `backend/src/collective/quota/`, tests under
  `backend/tests/`. Keep the cookieplone sub-package layout (`browser/`, `controlpanels/`,
  `indexers/`, `vocabularies/`, `upgrades/`, `setuphandlers/`, `profiles/`, `locales/`).
- **Commands** (run inside `backend/`): `make install`, `make test`, `make test-coverage`,
  `make lint`, `make format`, `make i18n`, `make create-site`, `make start`,
  `make acceptance-backend-start`.
  Never call `pip`, `uv add` or `pytest` directly in docs; recommend the `make` targets.
- **Frontend package**: `volto-collective-quota`, code under
  `frontend/packages/volto-collective-quota/src/` (cookieplone layout: `actions/`,
  `reducers/`, `components/`, `helpers/`, `locales/`). Volto core is checked out by
  mrs-developer at the version in `frontend/mrs.developer.json` (19.5.0).
- **Frontend commands** (run inside `frontend/`): `make install`, `make start`,
  `make test`, `make lint`, `make format`, `make i18n`, `make acceptance-backend-start`,
  `make acceptance-frontend-dev-start`, `make acceptance-test`. Never call `pnpm`
  directly in docs.
- **Frontend tests**: vitest for reducers, helpers and component rendering; Cypress for
  user flows against the acceptance backend. Coverage gate: vitest `--coverage` with a
  90 % lines threshold on `src/` (excluding `src/index.ts` and `src/config/`),
  enforced by `make test` and CI. Cypress flows are not counted, so on top of the
  number every reducer/helper has a unit test, every component a render test, and
  every user-visible flow a Cypress test (phase 9 lists them).
- **No Docker images**: this is an add-on, shipped as a Python package and an npm
  package. The repository has no Dockerfiles, no Compose stack and no image jobs in
  CI; development, acceptance and CI servers run from the backend virtualenv and the
  frontend checkout.
- **Frontend dependencies**: the add-on declares no runtime `dependencies`; everything
  comes from `@plone/volto`. The backend never depends on `plone.volto` at runtime
  (only the `acceptance` extra, phase 8).
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
  All user-facing strings go through it. Run `make i18n` after adding strings. The Volto
  add-on uses `react-intl` `defineMessages` and `make i18n` in `frontend/`; strings the
  backend already translates (banner text, policy titles, action title) are sent
  translated in the JSON and are **not** duplicated in the add-on.
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
| Expansion element | A `plone.restapi` `IExpandableElement` adapter; ours is named `quota` and adds the usage summary to `@components` of any content response when asked with `?expand=quota` |
| Banner | The editor-only warning: Classic viewlet `collective.quota.warning` or the Volto slot component `collective-quota-banner`; both render `summary.level_message` |
| Level | `ok`, `warning` or `exceeded`, computed by `get_usage_info()`; the only thing UIs branch on |
