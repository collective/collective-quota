# Phase 8 — REST API for Volto

Status: Done
Depends on: Phases 1–7
Last updated: 2026-10-16

## Goal

Expose over `plone.restapi` everything the Volto add-on (phase 9) needs, without adding
any Volto package to the runtime dependencies of `collective.quota`:

1. `GET @quota-usage`: usage summary + biggest items (the JSON twin of `@@quota-usage`).
2. `POST @quota-rebuild`: the JSON twin of `@@quota-rebuild`.
3. A `quota` expansion element so every content request Volto already makes can carry
   the usage level for the banner, with no extra round trip.
4. Development and acceptance plumbing so the Volto add-on can be developed and tested
   against this backend (`plone.volto` only in an `acceptance` extra).

Classic UI behaviour does not change. A site without Volto simply has three more REST
endpoints behind the same permissions as the Classic views.

## Scope

In: the services and expander above, a shared listing module used by both the Classic
view and the service, the control panel group fix, the `acceptance` extra, tests, docs,
changelog fragment.

Out: deletion endpoint (plone.restapi's `DELETE` and `@linkintegrity` already cover it,
see "Deletion"), the Volto add-on itself (phase 9), per-navigation-root totals.

## Product rules this phase enforces (see `00-architecture.md` §1.1)

- **Never for anonymous.** Every service requires `ViewDiskUsage` (or `ManageSettings`);
  the expander returns nothing at all for anonymous users or users without
  `ViewDiskUsage`, so no quota data ever reaches a response they can read.
- **No limits, no noise.** When neither a soft nor a hard limit is configured the JSON
  still works (total + listing) but says `limits_configured: false`, `level: "ok"`,
  `message: null`, `percent: null`, `policy_hint: null`. Clients render nothing
  limit-related from that.
- **Backend stands alone.** No import of `plone.volto` anywhere in `src/`; it is only an
  `acceptance` extra used to run the Volto acceptance server.

## Design

### Shared listing: `collective.quota.listing`

The biggest-items query and its per-item permission checks currently live in
`browser/usage.py`. Move them to a UI-neutral module so the Classic view and the REST
service cannot drift:

```python
LIMITS = (10, 25, 50, 100)
DEFAULT_LIMIT = 25


def parse_limit(value) -> int:
    """``value`` from a request; one of LIMITS, else DEFAULT_LIMIT."""


@dataclass(frozen=True)
class Item:
    uid: str
    title: str
    url: str
    portal_type: str
    type_title: str
    parent_url: str
    parent_title: str
    size: int
    modified: DateTime      # raw; each UI formats it
    can_delete: bool


def biggest_items(portal, request, limit: int) -> list[Item]:
    """Restricted catalog query on ``blob_size`` (same query as phase 5), objects
    loaded with ``_unrestrictedGetObject()``, ``Delete objects`` checked per item."""
```

`DiskUsageView.items()` becomes a thin mapping from `Item` to the template dict it uses
today (`edit_url`, `size_human`, localized `modified`), and `limit()`/`limits()` call
`parse_limit`/`LIMITS`. The phase 5 tests must pass unchanged.

### `GET @quota-usage` — `restapi/usage.py`

```xml
<plone:service
    method="GET"
    name="@quota-usage"
    for="plone.base.interfaces.IPloneSiteRoot"
    factory=".usage.QuotaUsageGet"
    permission="collective.quota.ViewDiskUsage"
    layer="collective.quota.interfaces.IQuotaRestapiLayer"
    />
```

Query string: `limit` (one of 10/25/50/100, default 25, anything else → default).

Response (`200`):

```json
{
  "@id": "http://localhost:8080/Plone/@quota-usage",
  "total": 3650722201,
  "total_human": "3.4 GB",
  "soft": 4294967296,
  "soft_human": "4.0 GB",
  "hard": 5368709120,
  "hard_human": "5.0 GB",
  "percent": 68,
  "level": "ok",
  "limits_configured": true,
  "message": null,
  "policy": "block_all",
  "policy_title": "Block new items and any upload that adds bytes",
  "policy_hint": "New content and uploads are blocked until files are removed.",
  "can_manage": true,
  "controlpanel": "http://localhost:8080/Plone/@controlpanels/collective-quota",
  "limit": 25,
  "limits": [10, 25, 50, 100],
  "items": [
    {
      "@id": "http://localhost:8080/Plone/reports/annual-report",
      "UID": "afb0a2ccbeb240f9baa9f0e64feed7e5",
      "title": "Annual report",
      "@type": "File",
      "type_title": "File",
      "parent": {"@id": "http://localhost:8080/Plone/reports", "title": "Reports"},
      "blob_size": 2097152,
      "blob_size_human": "2.0 MB",
      "modified": "2026-10-16T14:02:11+00:00",
      "can_delete": true
    }
  ]
}
```

Field rules:

| Field | Source | Notes |
|---|---|---|
| `total`, `soft`, `hard`, `percent`, `level` | `get_usage_info()` | bytes; `soft`/`hard` are `0` when disabled; `percent` is `null` when hard is disabled |
| `*_human` | `human_readable_size` | `soft_human`/`hard_human` are `null` when the limit is `0` |
| `limits_configured` | `soft > 0 or hard > 0` | |
| `message` | `browser/summary.py:level_message`, translated with the request | `null` when level is `ok` |
| `policy`, `policy_title` | `get_settings().policy`, `POLICY_TITLES` translated | always present (the policy exists even when disabled) |
| `policy_hint` | `browser/summary.py:policy_hint` translated | `null` when `hard == 0` |
| `can_manage` | `ManageSettings` on the site root | |
| `controlpanel` | REST control panel URL | present only when `can_manage` |
| `items[].modified` | `json_compatible(DateTime)` (ISO 8601) | clients format it |
| `items[]` | `listing.biggest_items` | `UID`, `@id` and `@type` use plone.restapi's naming so Volto helpers (`flattenToAppURL`, delete actions, link-integrity modal) work unchanged |

The summary part (everything except `items`, `limit`, `limits`) is built by one helper,
`usage_payload(portal, request) -> dict`, which the expander reuses. `summary.py` moves
from `browser/` to the package root (`collective.quota.summary`) because it is no
longer Classic-only; `browser/summary.py` keeps a re-export so phase 5/6 imports work.

Errors: `401` for anonymous **and** for authenticated users without the permission
(plone.restapi answers `401 Unauthorized` for both, as its own services and our
`@controlpanels/collective-quota` do); no other error cases.

### Expansion element `quota` — `restapi/expansion.py`

```xml
<adapter factory=".expansion.Quota" name="quota" />
```

```python
@implementer(IExpandableElement)
@adapter(Interface, IQuotaRestapiLayer)
class Quota:
    def __init__(self, context, request): ...

    def __call__(self, expand=False):
        portal = api.portal.get()
        if api.user.is_anonymous() or not _can_view_usage(portal):
            return {}                       # key absent: nothing to see
        result = {"quota": {"@id": f"{portal.absolute_url()}/@quota-usage"}}
        if expand:
            result["quota"].update(usage_payload(portal, self.request))
        return result
```

- Registered for `Interface`, so it is available on every content object and on the
  site root, exactly like `navroot`. `plone.restapi` merges the returned dict into
  `@components`; an empty dict adds nothing, so unauthorised responses carry no `quota`
  key at all.
- Expanded payload = the summary keys of `@quota-usage` (no `items`, `limit`, `limits`).
  Volto asks for it with `?expand=quota` on the content requests it already issues.
- Cost per request when expanded: `get_usage_info()` (indexing-queue flush + one
  `Length` read + registry/environment lookup) and one permission check. Nothing loads
  content objects.
- Permission check uses `getSecurityManager().checkPermission(VIEW_DISK_USAGE, portal)`
  on the **site root**, because the services live there; a user who only holds the
  permission through a local role on a folder gets no banner there (and would get `401`
  on the service). Documented limitation; same as Classic.

### `POST @quota-rebuild` — `restapi/rebuild.py`

```xml
<plone:service
    method="POST"
    name="@quota-rebuild"
    for="plone.base.interfaces.IPloneSiteRoot"
    factory=".rebuild.QuotaRebuildPost"
    permission="collective.quota.ManageSettings"
    layer="collective.quota.interfaces.IQuotaRestapiLayer"
    />
```

Runs `rebuild_usage(portal)` (already under `guard_suspended()`), then returns `200`:

```json
{"items": 1234, "total": 3650722201, "total_human": "3.4 GB"}
```

No body is required or read. The service marks the request with
`plone.protect.interfaces.IDisableCSRFProtection` before rebuilding, exactly like
plone.restapi's own write services do (`services/content/add.py`,
`services/workflow/transition.py`); without it `plone.protect` rejects the reindexing
writes for lack of a form token. Authentication plus `ManageSettings` are the guards,
as for every plone.restapi write.

### Deletion: no new endpoint

The client flow (phase 9) is the same as Volto's folder contents:

1. `GET @linkintegrity?uids=<uid>&uids=<uid>…` for the preview of breaches.
2. `DELETE <item @id>` per selected item, serially (`plone.restapi`'s `ContentDelete`
   swallows `LinkIntegrityNotificationException`, so breaches never block).
3. `GET @quota-usage` again; the client computes "freed" as the difference of `total`.

Items locked by **another** user: `manage_delObjects` raises for WebDAV-locked objects
and plone.restapi turns that into an error response for that one item. The client
reports the failed items and continues. We do not replicate the Classic view's
"unlock my own locks" step: Volto's own delete does not either.

### Control panel group

`controlpanels/restapi.py` sets `group = "Products"`. `RegistryConfigletPanel.__init__`
replaces `group` with the configlet category title whenever the configlet exists, and
Plone 6 titles the `Products` category **"Add-on Configuration"**, which is the section
Volto's Site Setup shows for add-ons. The class attribute stays: it is the only value
when the configlet is not registered (for example on a site installed before the
control panel existed), and without it `@controlpanels/collective-quota` fails with
`AttributeError` (500). Tests assert the derived group in the `@controlpanels` listing
and the fallback without the configlet (Classic is unaffected: it reads
`controlpanel.xml`).

### Acceptance extra and `plone.volto`

`plone.volto` is **not** a runtime dependency (dropped in phase 1, see
`news/+drop-plone-volto.breaking`). The Volto acceptance server (`make
acceptance-backend-start` in `backend/`, `Dockerfile.acceptance`) configures
`plone.restapi,plone.volto,plone.volto.cors,collective.quota`, which currently fails in
the local virtualenv because `plone.volto` is not installed.

- `pyproject.toml`: add `[project.optional-dependencies] acceptance = ["plone.volto"]`.
- `mx.ini`: `main-package = -e .[test,acceptance]` so `make install` can run the
  acceptance server. `plone.app.testing` disables `z3c.autoinclude` in test layers, so
  having `plone.volto` importable does not change what the unit/functional tests load.
  `tests/test_scaffold.py` gets an assertion that `plone.volto` is **not** in the
  runtime `dependencies` list (keeps the rule honest).
- `Dockerfile.acceptance`: update the `sed` that strips the extras so it turns
  `-e .[test,acceptance]` into `.[acceptance]`. Verify at build time whether the
  `plone/server-builder` image already ships `plone.volto` (the `Plone` meta package
  may pull it); the extra is harmless either way.
- Nothing in the `default` profile changes: `plone.volto:default` is **not** a
  dependency. The Volto acceptance server applies it through `APPLY_PROFILES`
  (`plone.volto:default,collective.quota:default`) the way the Volto project templates
  do.
- The robot fixture only runs a package's Zope product `initialize()` for names in
  `INSTALL_PRODUCTS`; without it `BlobSizeIndex` is not registered and applying
  `catalog.xml` fails with "Index of type BlobSizeIndex not found". Both the Makefile
  target and `Dockerfile.acceptance` set `INSTALL_PRODUCTS=collective.quota`.

### Documentation and changelog

- `backend/README.md`: "REST API" section listing the three endpoints and the
  expander with example requests (`curl` with `Accept: application/json`).
- `docs/docs/reference/rest-api.md`: full field tables from this spec; link from the
  reference index and from "Views and viewlet".
- `backend/news/+rest-api.feature`.

## Files

Create:
- `backend/src/collective/quota/listing.py`
- `backend/src/collective/quota/summary.py` (moved from `browser/summary.py`; the old
  module re-exports)
- `backend/src/collective/quota/restapi/usage.py`
- `backend/src/collective/quota/restapi/expansion.py`
- `backend/src/collective/quota/restapi/rebuild.py`
- `backend/tests/test_listing.py`
- `backend/tests/test_restapi_usage.py`
- `backend/tests/test_restapi_expansion.py`
- `backend/tests/test_restapi_rebuild.py`
- `docs/docs/reference/rest-api.md`
- `backend/news/+rest-api.feature`

Modify:
- `backend/src/collective/quota/browser/usage.py` (use `listing`)
- `backend/src/collective/quota/browser/summary.py` (re-export shim)
- `backend/src/collective/quota/restapi/configure.zcml`
- `backend/src/collective/quota/controlpanels/restapi.py` (comment on the `group` fallback)
- `backend/pyproject.toml`, `backend/mx.ini`, `backend/Dockerfile.acceptance`,
  `backend/Makefile` (`INSTALL_PRODUCTS`, `plone.volto:default`)
- `backend/tests/test_scaffold.py`, `backend/tests/test_controlpanel_restapi.py` (group)
- `backend/README.md`, `docs/docs/reference/index.md`, `docs/docs/reference/views-and-viewlet.md`
- `specs/00-architecture.md` (only if implementation changes a name)

## Tasks

- [x] `listing.py` with `LIMITS`, `DEFAULT_LIMIT`, `parse_limit`, `Item`, `biggest_items`; `browser/usage.py` uses it; phase 5 tests still green
- [x] `summary.py` at package root, `browser/summary.py` re-exports; `usage_payload()`
- [x] `GET @quota-usage` service + ZCML
- [x] `quota` expander + ZCML
- [x] `POST @quota-rebuild` service + ZCML
- [x] Control panel group: REST listing shows "Add-on Configuration"; `group` kept as the fallback when the configlet is missing
- [x] `acceptance` extra, `mx.ini`, `Dockerfile.acceptance` sed; `make acceptance-backend-start` starts locally and answers `GET /plone/@quota-usage` with the admin user
- [x] README "REST API" section, docs reference page, news fragment
- [x] `make lint`, `make test-coverage` at 100 %

## Tests

Functional layer with `RelativeSession` (as in `test_enforcement_restapi.py`), users
`admin` (Manager), `editor` (Editor), `member` (Member, no `ViewDiskUsage`), anonymous.

- [x] `tests/test_listing.py` — `parse_limit` (valid, invalid, missing); `biggest_items` ordering, limit, restricted search hides private items from the editor, `can_delete` false without `Delete objects`, metadata fallback when the `blob_size` column is `Missing.Value`
- [x] `tests/test_restapi_usage.py` — 200 shape for editor (all keys, `can_manage` false, no `controlpanel`); admin gets `can_manage` true + `controlpanel`; `limit` query handling; anonymous → 401; member → 401; `limits_configured` false and `message`/`percent`/`policy_hint`/`soft_human`/`hard_human` null with no limits; `level`/`message` for warning and exceeded; `modified` is ISO 8601; item `@id`/`UID`/`@type` naming
- [x] `tests/test_restapi_expansion.py` — `GET /plone/folder` as editor: `@components.quota` has only `@id`; with `?expand=quota` it has the summary keys; anonymous and member responses have **no** `quota` key with and without `expand`; site root works; after uninstall the key is absent (layer gone)
- [x] `tests/test_restapi_rebuild.py` — admin POST → 200 with counts, total matches `get_total_usage()`; editor → 401; anonymous → 401; GET → 405/404 (whatever plone.restapi returns for an unregistered method; assert it is not 200)
- [x] `tests/test_controlpanel_restapi.py` — `@controlpanels` lists `collective-quota` with group "Add-on Configuration"
- [x] `tests/test_scaffold.py` — `plone.volto` absent from `[project].dependencies`, present in the `acceptance` extra

## Acceptance criteria

- Classic UI unchanged (phase 5/6/7 suites green, manual QA steps 3 and 10 behave as before).
- A Volto developer can read `docs/docs/reference/rest-api.md` and build the phase 9 UI
  without reading Python.
- `curl` as anonymous against any content with `?expand=quota` never returns a `quota`
  key; as editor it does, as member it does not.
- With no limits configured, the `@quota-usage` payload has `limits_configured: false`
  and null `message`, and the listing still works.
- `make acceptance-backend-start` works from a fresh `make install` in `backend/`.
