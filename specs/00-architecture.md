# 00 — Architecture and canonical names

Status: Reference (keep in sync with code)
Last updated: 2026-10-16

## 1. Problem and goals

Hosted Plone sites need a way to cap the disk space consumed by uploaded files and
images, warn editors before the cap is reached, and make cleanup easy. Measuring the
true size of arbitrary persistent Python objects is impractical, so this add-on counts
**only the bytes stored in blob fields** (files and images). That number is exact,
cheap to compute per item, and covers the overwhelming majority of real disk usage.

Goals for this iteration:

1. Per-item size in a catalog index (`blob_size`) that is populated for existing content
   by a normal catalog update.
2. A site-wide total that is O(1) to read, so it can be checked on every save and
   rendered on every editor page.
3. Configurable soft limit (warn) and hard limit (enforce) with four policies.
4. Enforcement in Classic UI forms and in the REST API (`plone.restapi`), plus a
   transaction-level guard so that **no code path** can push the site past a
   configured hard limit without the policy allowing it.
5. A "biggest items" view with multi-select delete that honours link integrity.
6. A warning banner for editors and a "Disk usage" entry in the user menu.
7. Every setting configurable through environment variables, optionally locked so the
   control panel cannot override them.
8. Everything installable, uninstallable, upgradeable, translatable, and covered by
   automated tests at 100 % line and branch coverage.

Non-goals (this iteration): Volto UI, per-folder or per-navigation-root quotas,
counting CMFEditions versions or image scales, measuring non-blob content.

## 2. Canonical names

These are the only names to use. Phase files reference them; do not invent variants.

### Permissions (`permissions.zcml` + `profiles/default/rolemap.xml`)

| ZCML id | Title (used in rolemap, actions, templates) | Default roles |
|---|---|---|
| `collective.quota.ManageSettings` | `collective.quota: Manage Quota Settings` | Manager, Site Administrator |
| `collective.quota.ViewDiskUsage` | `collective.quota: View Disk Usage` | Manager, Site Administrator, Editor, Contributor, Reviewer |

Deleting from the usage view additionally requires the standard `Delete objects`
permission on each item. The control panel requires `ManageSettings`.

### Browser layers (`interfaces.py`, `profiles/default/browserlayer.xml`)

| Interface | Base | Layer name | Purpose |
|---|---|---|---|
| `collective.quota.interfaces.IBrowserLayer` | `IDefaultBrowserLayer` | `collective.quota` | Classic views, viewlet, form validators |
| `collective.quota.interfaces.IQuotaRestapiLayer` | `plone.restapi.interfaces.IPloneRestapiLayer` | `collective.quota.restapi` | REST adapter overrides and control panel adapter |

Why a second layer: `plone.restapi` registers its adapters for `IPloneRestapiLayer`.
An override registered for a layer that *subclasses* it is always more specific
(C3 linearization places a derived interface before its base no matter which order
the layers were applied to the request), so our adapters win deterministically.

### Catalog

| Thing | Name |
|---|---|
| Index name and metadata column | `blob_size` |
| Index meta_type | `BlobSizeIndex` |
| Index class | `collective.quota.catalog.blob_size_index.BlobSizeIndex` |
| Indexer | `collective.quota.indexers.blob_size.blob_size` (adapter name `blob_size`, for `plone.dexterity.interfaces.IDexterityContent`) |

### Registry (`interfaces.py` schema, `profiles/default/registry/main.xml`)

Schema: `collective.quota.interfaces.IQuotaSettings`, prefix `collective.quota`.

| Record | Type | Registry default | Built-in default | Meaning |
|---|---|---|---|---|
| `collective.quota.soft_limit_mb` | Int ≥ 0, optional | `None` | `0` | Warning threshold in MB; `0` disables |
| `collective.quota.hard_limit_mb` | Int ≥ 0, optional | `None` | `0` | Enforcement threshold in MB; `0` disables |
| `collective.quota.over_limit_policy` | Choice (`collective.quota.OverLimitPolicies`), optional | `None` | `block_all` | See §4 |
| `collective.quota.max_file_size_mb` | Int ≥ 0, optional | `None` | `10` | Per-file cap used only by `limit_file_size` |

A registry value of `None` means "not set in the control panel", which lets the
environment variable or the built-in default apply (see §3.3).

### Environment variables

| Variable | Maps to | Accepted values |
|---|---|---|
| `COLLECTIVE_QUOTA_SOFT_LIMIT_MB` | `soft_limit_mb` | integer ≥ 0 |
| `COLLECTIVE_QUOTA_HARD_LIMIT_MB` | `hard_limit_mb` | integer ≥ 0 |
| `COLLECTIVE_QUOTA_OVER_LIMIT_POLICY` | `over_limit_policy` | `block_all`, `block_files`, `limit_file_size`, `allow` |
| `COLLECTIVE_QUOTA_MAX_FILE_SIZE_MB` | `max_file_size_mb` | integer ≥ 0 |
| `COLLECTIVE_QUOTA_LOCK_SETTINGS` | lock flag | truthy: `1`, `true`, `yes`, `on` (case-insensitive); anything else or unset = not locked |

Unset or empty variables are ignored. Invalid values are logged once per process as a
warning and treated as unset. Variables are read from `os.environ` on every
`get_settings()` call (a few dict lookups; no caching, so tests can monkeypatch them).

### Vocabulary

`collective.quota.OverLimitPolicies` with tokens `block_all`, `block_files`,
`limit_file_size`, `allow`.

### Views, viewlet, actions, control panel

| Thing | Name | Context | Permission |
|---|---|---|---|
| Biggest items view | `@@quota-usage` | `IPloneSiteRoot` | `collective.quota.ViewDiskUsage` |
| Delete confirmation/action | `@@quota-delete` | `IPloneSiteRoot` | `collective.quota.ViewDiskUsage` (+ `Delete objects` per item) |
| Rebuild usage data | `@@quota-rebuild` | `IPloneSiteRoot` | `collective.quota.ManageSettings` |
| Control panel | `@@quota-controlpanel` | `IPloneSiteRoot` | `collective.quota.ManageSettings` |
| Control panel configlet id | `collective-quota` (category `Products`) | | |
| REST control panel | `@controlpanels/collective-quota` | | `collective.quota.ManageSettings` |
| Viewlet | `collective.quota.warning` in manager `plone.globalstatusmessage` | any | `collective.quota.ViewDiskUsage` |
| User menu action | `disk-usage` in category `user` | | `collective.quota: View Disk Usage` |

### Python API (public helpers other code may import)

| Symbol | Module |
|---|---|
| `get_total_usage(portal=None) -> int` | `collective.quota.usage` |
| `get_settings() -> QuotaSettings` | `collective.quota.settings` (re-exported by `collective.quota.usage`) |
| `read_env() -> EnvSettings`, `is_locked(name) -> bool`, `ENV_VARS`, `LOCK_VAR`, `resolve_all`, `invariant_errors`, `set_registry_value` | `collective.quota.settings` |
| `record_approved_bytes(n)`, `record_approved_add()`, `guard_suspended()` | `collective.quota.guard` |
| `get_usage_info(portal=None) -> UsageInfo` | `collective.quota.usage` |
| `rebuild_usage(portal, update_metadata=True) -> int` | `collective.quota.usage` |
| `get_blob_sizes(obj) -> dict[str, int]`, `has_blob_fields(obj) -> bool` | `collective.quota.indexers.blob_size` |
| `evaluate_upload(...)`, `evaluate_add(...)`, `Decision` | `collective.quota.policy` |
| `QuotaExceeded` (ValidationError) | `collective.quota.policy` |
| `MB`, `mb_to_bytes()` | `collective.quota.utils` |

Human-readable formatting: reuse `plone.base.utils.human_readable_size` (verified to
exist in Plone 6; `Products.CMFPlone.utils` only re-exports it with a deprecation).

## 3. Data model

### 3.1 Per-item size: the `blob_size` index

- Indexer walks `plone.dexterity.utils.iterSchemata(obj)` (type schema + behaviors),
  takes every field providing `INamedField`, reads the stored value through the schema
  adapter (`schema(obj)`, which is `obj` itself for the main schema and the behavior
  adapter for behaviors), and sums `value.getSize()` (cheap: `plone.namedfile` stores
  `_size`; the blob is not opened).
- Items with **no** blob fields raise `AttributeError` from the indexer. ZCatalog treats
  that as "no value" and keeps them out of the index. Items *with* blob fields are always
  indexed, even when the value is `0` (empty field), so `blob_size` metadata is `0` for
  them rather than `Missing.Value`.
- Value type: Python `int`, bytes.
- The index is a `FieldIndex` subclass, so `sort_on="blob_size"`, `sort_limit`, and
  range queries (`{"query": 1, "range": "min"}`) all work.

What is counted / not counted:

| Counted | Not counted |
|---|---|
| `File.file`, `Image.image`, lead image behavior `image`, any `NamedBlob*`/`Named*` field in custom types and behaviors | CMFEditions history, image scales (`plone.scale` annotations), ZODB object overhead, rich text, blocks JSON |
| Working copies (they are regular items) | The Plone site root (no blob fields) |
| Every item individually; folders do **not** aggregate children | Content not in `portal_catalog` |

### 3.2 Site total: running counter inside the index

`BlobSizeIndex` keeps a `BTrees.Length.Length` named `_total`:

- `_index_object(docid, obj, threshold, attr)`: read the old stored value from
  `self._unindex` (0 if absent), call the base implementation, read the new stored
  value, apply the difference to `_total`.
- `unindex_object(docid)`: subtract the old stored value, then call the base.
- `clear()`: call the base, reset `_total` to `Length(0)`.
- `total()`: return `_total()`; lazily call `rebuild_total()` if `_total` is missing
  (instances created before the attribute existed).
- `rebuild_total()`: `Length(sum(_unindex.values()))`.

Why this instead of a counter in annotations updated by event subscribers:

- The catalog is the only path every add/edit/delete/move/copy/paste already goes
  through, so the counter can never miss a change that reaches the index.
- Ordering of event subscribers is irrelevant.
- `Length` resolves ZODB write conflicts, so concurrent uploads do not retry.
- "Clear and rebuild" or "reindex index" in the ZMI automatically repairs the total.

Reading the total is O(1) and loads no content objects.

### 3.3 Settings: registry, environment, lock

Two sources feed every setting: the registry (control panel) and environment
variables. `collective.quota.settings.get_settings()` resolves them per field:

```
env      = parsed environment value, or None when unset/invalid
registry = registry record value, or None when never saved
locked   = COLLECTIVE_QUOTA_LOCK_SETTINGS is truthy AND env is not None

if locked:               effective = env,      source = "env-locked"
elif registry is not None: effective = registry, source = "registry"
elif env is not None:    effective = env,      source = "env"
else:                    effective = built-in default, source = "default"
```

Consequences:

- Without the lock flag, environment variables act as **defaults** that the control
  panel can override. A value saved in the control panel wins until it is cleared
  ("Reset to defaults" sets the registry record back to `None`).
- With the lock flag, every variable that is set is **fixed**: the control panel shows
  it read-only with its source, and both the Classic form and the REST control panel
  refuse to change it. Variables that are not set stay editable.
- `QuotaSettings` (frozen dataclass) carries `soft_bytes`, `hard_bytes`, `policy`,
  `max_file_bytes`, plus `sources: dict[str, str]` and `locked: frozenset[str]` so UIs
  can explain where each value comes from. `0` MB means "disabled" for soft and hard.
- Invariants (soft ≤ hard when both are > 0, max file size > 0 for `limit_file_size`)
  are checked on the **effective** values in the control panel and the REST PATCH.
  They only reject a save when a violated invariant involves a value stored in the
  control panel; conflicts coming purely from the environment are logged once as
  warnings by `get_settings()` and still applied (the operator owns the environment).
- `QuotaSettings.values` also carries the effective value of each field (MB / policy
  token) for display.
- REST `@controlpanels/collective-quota`: `data` holds the **stored** values (locked
  fields show their environment value and are `readonly` in the schema), plus
  top-level `effective`, `sources` and `locked`. PATCH refuses a locked field sent with
  a different value (400) and ignores it when sent with its locked value.

## 4. Policy semantics

Definitions for a single save of one blob field:

- `old_size`: bytes currently stored in that field (0 for a new item or empty field)
- `new_size`: bytes of the incoming value
- `delta = new_size - old_size`
- `total`: current site total (before this save)

Rules, in order:

1. If `hard_limit` is disabled (`0`) → **allowed**.
2. If `delta <= 0` → **allowed** (removing, or replacing with a smaller/equal file, is
   always possible so editors can clean up).
3. If `total + delta <= hard_limit` → **allowed** (the save stays under the limit).
4. Otherwise the save would cross or stay above the hard limit; apply the policy:

| Policy token | Title | New item **without** files when `total >= hard` | Upload with `delta > 0` that crosses/stays above hard | Upload replacing with smaller |
|---|---|---|---|---|
| `block_all` | Block new items and any upload that adds bytes | **denied** | **denied** | allowed |
| `block_files` | Allow new items, block uploads that add bytes | allowed | **denied** | allowed |
| `limit_file_size` | Allow uploads up to a maximum file size | allowed | allowed iff `new_size <= max_file_size` | allowed |
| `allow` | Allow everything, only show warnings | allowed | allowed | allowed |

The "new item without files" column is the only object-level rule. It is evaluated
once per add (Classic add form, REST `POST`), independent of fields.

Soft limit: never blocks. It only switches the warning viewlet and the usage view
into "warning" state. Levels: `ok` (below soft or soft disabled), `warning`
(`total >= soft`), `exceeded` (`total >= hard`, hard enabled). `exceeded` wins.

Worked examples (hard = 100 MB, total = 95 MB):

| Action | Policy | Result |
|---|---|---|
| Upload 3 MB file to a new File item | any | allowed (98 ≤ 100) |
| Upload 10 MB file | `block_all` / `block_files` | denied |
| Upload 10 MB file | `limit_file_size`, max 20 MB | allowed (file ≤ 20 MB) |
| Upload 30 MB file | `limit_file_size`, max 20 MB | denied |
| Replace a 40 MB file with a 20 MB one at total 120 MB | any | allowed (delta < 0) |
| Create a Document (no blob fields) at total 120 MB | `block_all` | denied |
| Create a Document at total 120 MB | `block_files` | allowed |
| Edit a Document title at total 120 MB | any | allowed |

## 5. Enforcement architecture

Three validation hooks give users early, friendly errors. A fourth, transaction-level
guard makes the hard limit impossible to bypass. All four share `policy.py`:

| Hook | Covers | Where it runs | Error surface |
|---|---|---|---|
| A. Pluggable field validator (`IPluggableFileFieldValidation` + `IPluggableImageFieldValidation`, named `collective.quota`, for `(INamedField, Interface)`) | Every upload: Classic add/edit forms, REST `POST`/`PATCH` (base64 and multipart), TUS uploads | Inside `NamedField.validate(value)`, which `plone.namedfile` fields call and which both z3c.form (`SimpleFieldValidator`) and `plone.restapi` (`NamedFieldDeserializer`) invoke | Classic: field error on the form. REST: HTTP 400 with the field error list |
| B. Add-form guard (`IManagerValidator` subclass for `(Interface, IBrowserLayer, z3c.form.interfaces.IAddForm, IInterface, Interface)`) | "No new items" part of `block_all` in Classic | z3c.form `extractData()` of Dexterity add forms | Form-level error, nothing is created |
| C. REST add guard (`IDeserializeFromJson` override for `(IDexterityContent, IQuotaRestapiLayer)`; plone.restapi has one deserializer for items and containers) | "No new items" part of `block_all` in REST | `__call__(..., create=True)` before delegating to `plone.restapi` | HTTP 400 `BadRequest` |
| D. Commit guard (`guard.py`: transaction before-commit hook + per-transaction ledger) | Everything that reaches the catalog or fires `IObjectAddedEvent`: `plone.api`, `invokeFactory`, copy/paste, imports, scripts, custom widgets, future REST services | `transaction.addBeforeCommitHook`, registered lazily by the index and by the added-event subscriber | Transaction aborted; `QuotaCommitAborted(BadRequest)` → Classic error page / REST 400 |

Hook A details that make it correct in both UIs:

- `value is None` → skip (field cleared).
- When the field is bound (`field.context` is not None), read the stored value through
  `field.interface(context)`; if the incoming value **is** the stored object (identity),
  skip: this is z3c.form's "keep existing file" and `plone.restapi`'s "representation
  re-sent without `data`" case.
- Unbound field (Classic add form ignores context) → `old_size = 0`.
- Site total comes from `get_total_usage()` using `zope.component.hooks.getSite()`.
  If there is no site or no `blob_size` index (add-on not installed), allow.
- Denial raises `QuotaExceeded(zope.schema.ValidationError)` whose `doc()` returns a
  translated message with human-readable sizes; z3c.form error snippets and
  `plone.restapi` both render `error.doc()`.

### 5.1 Hook D: the commit guard and the approval ledger

Hooks A–C can be bypassed by any code that writes blobs without going through field
validation. Hook D closes that gap with a cheap bookkeeping scheme:

**Ledger.** A per-transaction record stored with `transaction.get().set_data(KEY, ledger)`
(`transaction` ≥ 2.0 transaction-scoped data; falls back to a `WeakKeyDictionary` keyed
by the transaction if unavailable). Fields:

| Field | Written by | Meaning |
|---|---|---|
| `start_total` | `BlobSizeIndex` on its first change in the transaction, **before** applying it | Site total at the start of the transaction |
| `approved_bytes` | Hook A, when it allows an upload with `delta > 0` | Sum of positive deltas that the policy explicitly allowed |
| `added_items` | `IObjectAddedEvent` subscriber (any `IDexterityContent`) | Number of new items in this transaction (copies count; moves do not) |
| `approved_items` | Hooks B and C when `evaluate_add` allows | Number of adds the policy explicitly allowed |
| `exempt_bytes` | `BlobSizeIndex` changes made inside `guard_suspended()` | Bytes excluded from the check (trusted code only) |
| `hook_registered` | guard | The before-commit hook was added once |

Validators write only integers: "validation adds something to the request that is
quickly and cheaply checked later".

**Hook registration.** The first time the index applies a non-zero delta, or an item is
added, the guard calls `transaction.get().addBeforeCommitHook(check_quota, args=(portal_path,))`
exactly once per transaction. Transactions that touch no blobs and add no items never
register anything, so the common case costs nothing.

**Check at commit (`check_quota`)**, runs before the ZODB two-phase commit:

```
settings = get_settings()             # with the portal as the active site
if settings.hard_bytes <= 0: return
total = get_total_usage(portal)       # flushes the indexing queue; includes this transaction
net_delta = total - ledger.start_total - ledger.exempt_bytes   # 0 when only moves/renames happened
if net_delta > 0 and total > settings.hard_bytes and settings.policy != ALLOW:
    if net_delta > ledger.approved_bytes:
        raise QuotaCommitAborted("unapproved bytes", mapping=...)
if settings.policy == BLOCK_ALL and total >= settings.hard_bytes:
    if ledger.added_items > ledger.approved_items:
        raise QuotaCommitAborted("unapproved new items", mapping=...)
```

Raising inside a before-commit hook makes `transaction.commit()` raise; the publisher
aborts the transaction, nothing is written (blob files staged by `ZODB.blob` are
discarded on abort), and the exception is rendered with status 400 (registered in
`ZPublisher.HTTPResponse.status_codes`, which maps exception class names): Classic shows
a "Disk quota exceeded" page with the translated message to every user (exception
view `index.html` for `QuotaCommitAborted`), REST returns the usual JSON error.

**Why `net_delta` and not per-object deltas:** a move or rename re-catalogs the item
under a new record id (`−S` then `+S`), which is net 0. A copy is net `+S` and has no
approval, so it is blocked when over the limit, which is the intended behaviour.

**Why validators record approvals instead of the guard re-evaluating the policy:** the
guard cannot know which bytes belong to which field or whether a file was replaced, so
re-evaluating per upload at commit time would be unreliable. The ledger lets the guard
answer the only question that matters: "did every byte that crossed the hard limit go
through a validator that said yes?" Under `limit_file_size`, validators approve only
files within the cap, so unapproved bytes from bypass paths are rejected even when
they would individually be small. This is deliberately stricter for bypass paths.

**Escape hatch.** `with guard_suspended():` exempts the changes made inside the block
(index deltas go to `exempt_bytes`, added items are not counted); the scope is the
current thread, across commits made inside the block, and changes made outside it are
still checked. It is a Python-only API meant for `rebuild_usage()` (a fresh install
would otherwise look like a huge unapproved delta), migrations, and imports run by an
administrator. It is not reachable from any view or REST endpoint, and every use is
logged at INFO with the caller. Inside the block the upload validator (hook A) and the
REST add guard (hook C) also step aside: `plone.exportimport` creates content through
the plone.restapi deserializer, so an import into a full site would otherwise be
refused before the guard is even reached. Hook B only runs in Classic add forms,
which never run inside a Python `with` block.

**Interplay with "Clear and rebuild" / reindex:** those run through `rebuild_usage` or
the ZMI; the ZMI buttons are Manager-only and their changes are net 0 for an already
populated index. A first population through the ZMI on a site already over the limit is
rejected by the guard; the control panel's "Rebuild usage data" button (which uses
`guard_suspended()`) is the documented path.

Known, accepted limitations:

- Hook A validates one field at a time. A single form uploading several files can
  overshoot the hard limit by at most that one save (the guard sees the sum of approved
  deltas, so it allows it). The next save is blocked.
- Two concurrent transactions can each be validated below the limit and together land
  above it (`BTrees.Length` merges both on commit). The overshoot is bounded by one
  upload per concurrent request and the next save is blocked. Avoiding it would require
  a non-conflict-resolving counter and retries, which is not worth it.
- The index total lags by one transaction: the check uses the committed total plus
  this transaction's delta, which is the intended semantics.

## 6. Runtime flows

**Install on a site with existing content**: GenericSetup `catalog.xml` adds index +
column (empty). `post_install` iterates every brain, resolves the object, and calls
`catalog.catalog_object(obj, idxs=["blob_size"], update_metadata=1)`; the index keeps
`_total` current while doing so; finally `rebuild_total()` as a safety net. The ZMI
"Reindex" button on the index, or `catalog.reindexIndex("blob_size", request)`, also
populates the index (but not the metadata column); the usage view tolerates missing
metadata by falling back to `index.getEntryForObject(rid)`.

**Save with upload (Classic)**: widget → converter builds `NamedBlobFile` → z3c.form
`SimpleFieldValidator` → `field.validate(value)` → hook A → policy → error or continue →
`applyChanges` → `ObjectModifiedEvent` → catalog reindex → `_total` updated.

**Save with upload (REST)**: `PATCH` JSON → `DeserializeFromJson` (ours, delegating) →
`NamedFieldDeserializer` builds value → `field.validate(value)` → hook A → 400 or
continue → event → reindex → `_total` updated.

**Add item (REST)**: `POST` → `FolderPost` creates the object → our deserializer with
`create=True` → hook C → `evaluate_add` → 400 (transaction aborted) or continue.

**Biggest items**: `catalog(blob_size={"query": 1, "range": "min"}, sort_on="blob_size",
sort_order="descending", sort_limit=N)[:N]` with the user's permissions.

**Delete selected**: `@@quota-usage` form → `@@quota-delete` step 1 (resolve UIDs, split
deletable/skipped, render confirmation with `@@delete_confirmation_info(items)` breach
snippet from `plone.app.linkintegrity`) → step 2 (`plone.protect` authenticator check,
unlock own locks, `api.content.delete(objects=..., check_linkintegrity=False)`, status
message with bytes freed, redirect).

**Every editor page**: viewlet reads `get_usage_info()` (O(1)); renders only for
authenticated users with `ViewDiskUsage` when level is `warning` or `exceeded`.

**Any transaction that adds bytes or items** (including scripts): the index and the
added-event subscriber fill the ledger and register the before-commit hook once; at
commit the guard compares the net delta with the approved bytes and aborts if the hard
limit would be crossed without approval (§5.1).

**Settings read**: `get_settings()` merges registry + environment per §3.3; the control
panel displays the source of every value and locks fields fixed by the environment.

## 7. Package layout (target state after phase 7)

```
backend/src/collective/quota/
  __init__.py                 _ (MessageFactory), logger, initialize() registering BlobSizeIndex
  configure.zcml              + five:registerPackage, includes browser/, restapi/, catalog/
  permissions.zcml            two permissions
  interfaces.py               IBrowserLayer, IQuotaRestapiLayer, IQuotaSettings
  utils.py                    MB, mb_to_bytes, human_readable_size re-export
  settings.py                 ENV_VARS, read_env, QuotaSettings, get_settings (registry + env + lock)
  usage.py                    UsageInfo, get_index, get_total_usage, get_usage_info, rebuild_usage
  policy.py                   policy tokens, Decision, evaluate_upload, evaluate_add, QuotaExceeded
  guard.py                    ledger, before-commit hook, added-event subscriber, guard_suspended (hook D)
  validators.py               QuotaUploadValidator (hook A)
  catalog/__init__.py
  catalog/blob_size_index.py  BlobSizeIndex, manage_addBlobSizeIndex(+Form)
  catalog/configure.zcml
  indexers/blob_size.py       indexer + get_blob_sizes/has_blob_fields/iter_blob_fields
  indexers/configure.zcml
  vocabularies/policies.py    OverLimitPolicies vocabulary
  vocabularies/configure.zcml
  controlpanels/quota.py      QuotaControlPanelForm + wrapper
  controlpanels/restapi.py    RegistryConfigletPanel adapter
  controlpanels/configure.zcml
  browser/__init__.py
  browser/configure.zcml      views, viewlet, add-form guard adapter
  browser/usage.py            DiskUsageView
  browser/delete.py           QuotaDeleteView
  browser/summary.py          usage card values, warning/exceeded texts (shared)
  browser/rebuild.py          QuotaRebuildView
  browser/viewlets.py         QuotaWarningViewlet
  browser/addform_guard.py    QuotaAddFormValidator (hook B)
  browser/templates/usage.pt, delete_confirmation.pt, warning_viewlet.pt, controlpanel.pt
  restapi/__init__.py
  restapi/configure.zcml
  restapi/deserializer.py     QuotaAwareDeserializer(s) (hook C)
  restapi/query.py            BlobSizeIndexQueryParser (integer @search queries on blob_size)
  setuphandlers/__init__.py   HiddenProfiles, post_install (populate index)
  upgrades/                   utils.py (run_import_step, rebuild_usage) + configure.zcml
  profiles/default/           metadata.xml, browserlayer.xml, catalog.xml, rolemap.xml,
                              registry/main.xml, controlpanel.xml, actions.xml, viewlets.xml
  profiles/uninstall/         mirrors of the above with remove="True"
  locales/                    collective.quota.pot + .po files
backend/scripts/rebuild_blob_size.py   zconsole script for very large sites
backend/tests/                conftest.py + test modules per phase
```

## 8. Performance notes

- Total read: O(1). Viewlet and validators never touch the catalog's BTrees beyond the
  `Length`.
- Usage view: one sorted catalog query bounded by `sort_limit` (≤ 100), then at most
  100 object loads (`_unrestrictedGetObject()`) to check `Delete objects`. Acceptable.
- Install/rebuild: O(n) object loads once. Log progress every 1000 items; provide a
  `zconsole` script with periodic `transaction.savepoint()`/commit for very large sites.
- Writes: `Length` conflict resolution avoids retries on concurrent uploads; the
  FieldIndex BTrees have standard bucket-level conflict handling.
- Commit guard: zero cost for transactions without blob changes or adds; otherwise one
  registry read, a handful of `os.environ` lookups and one `Length` read at commit.

## 9. Security

- All quota information (totals, listing, banner) is behind `ViewDiskUsage`; anonymous
  users never see it. Templates additionally check `portal_state.anonymous()` so a
  mis-mapped permission still hides the banner.
- `@@quota-usage` uses a restricted catalog search: users only see items they can view
  (Plone's catalog security follows "Access contents information").
- `@@quota-delete` enforces `Delete objects` per item and `plone.protect` CSRF tokens on
  the confirm step; `@@quota-rebuild` is POST-only with a token.
- `@@quota-controlpanel` is behind `ManageSettings`.

## 10. Install, upgrade, uninstall

- Profile dependencies: `plone.app.registry:default` and `plone.restapi:default` (a
  plain Classic site does not install restapi on its own; see phase 1). No `plone.volto`.
- Profile version starts at `1000`. Every schema/registry/catalog change bumps it and
  ships an upgrade step (`upgrades/`). `rebuild_usage()` is the reusable repair step.
- Uninstall removes: both browser layers, index + column, registry records, configlet,
  user action, viewlet order entry. Content is untouched.
- Reinstall is safe: `post_install` populates the index again.

## 11. Verified references

Facts the design relies on, checked against upstream sources on 2026-10-15:

- `plone.namedfile.field.NamedField.validate` calls `getAdapters((field, value), IPluggableFileFieldValidation | IPluggableImageFieldValidation)` and invokes each adapter (`plone.namedfile` ≥ 6.1; confirm the exact minimum version in the installed constraints).
- `plone.restapi.deserializer.dxfields.NamedFieldDeserializer` converts to the field's `_type` then validates via the field; a dict without `data` returns the stored attribute (identity check works).
- `Products.PluginIndexes.unindex.UnIndex`: `_index_object` returns 1 on change and maintains `_unindex[docid]`; `unindex_object` reads `_unindex`; `clear()` recreates `_index`, `_unindex`, `_length`; missing attribute → `_marker` → entry removed. `getEntryForObject(docid, default)` reads `_unindex`.
- `ZCatalog.addIndex(name, type)` resolves the class via `all_meta_types(interfaces=(IPluggableIndex,))` by product `name`, so the index class must be registered through a product `initialize(context)`.
- `ZCatalog.reindexIndex` loads each object and calls `catalog_object(..., update_metadata=0)`.
- `plone.app.linkintegrity.browser.info.DeleteConfirmationInfo`: `__call__(items=None)` renders the breach snippet (HTML under the `plone.app.layout` layer, `""` when link integrity is disabled); `get_breaches(items)` returns the list of breaches. Registered as `@@delete_confirmation_info` for `*`.
- `plone.api.content.delete(obj=None, objects=None, check_linkintegrity=True)`; with `check_linkintegrity=False` it deletes via `manage_delObjects` without raising `LinkIntegrityNotificationException`.
- `plone.app.content.browser.contents.delete.DeleteActionView.action` shows the lock handling pattern (`@@plone_lock_info`, `ILockable(obj).unlock()`).
- Viewlet manager `plone.globalstatusmessage` (`plone.app.layout.viewlets.interfaces.IGlobalStatusMessage`) hosts `plone.globalstatusmessage` and `plone.app.dexterity.defaultpagewarning`. Plone stores no order for it; ordered viewlets render before unordered ones, so our `viewlets.xml` pins `plone.globalstatusmessage` first and the quota banner right after it.
- The `preferences` user action in `Products.CMFPlone` uses `url_expr` `python:f"{plone_portal_state.navigation_root_url()}/@@personal-preferences"` and `available_expr` `python:member is not None`.
- z3c.form `FieldWidgets.validate` looks up `IManagerValidator` with `(content, request, form, schema, manager)` once per schema interface present in the manager; `InvariantsValidator` adapts `(Interface, Interface, Interface, IInterface, Interface)`.
- `transaction.interfaces.ITransaction`: `addBeforeCommitHook(hook, args=(), kws=None)` runs hooks before the two-phase commit and an exception aborts the transaction; `set_data(ob, data)` / `data(ob)` provide transaction-scoped storage (`transaction` ≥ 2.0; Plone 6 ships ≥ 3.1). Confirm both on the installed version.
- `OFS` fires `ObjectAddedEvent` for adds and copy/paste targets, and `ObjectMovedEvent` (not an added event) for moves and renames.

## 12. Testing policy

- Coverage gate: `[tool.coverage.report] fail_under = 100` with `branch = true` on the
  `collective.quota` package. `make test-coverage` fails below 100 % and CI runs it.
- The only file excluded from measurement is the cookieplone-generated
  `locales/__main__.py` (i18n tooling that shells out to `i18ndude`). Everything else,
  including ZMI add forms, the `zconsole` script and error branches, is tested.
- `# pragma: no cover` is not allowed; untestable code is a design smell to fix.
- Each phase file lists its test modules; a phase is not `Done` until the gate passes
  with that phase's modules included.
- Environment-dependent code is tested with pytest's `monkeypatch.setenv` /
  `monkeypatch.delenv` through the `quota_env` fixture.
- The commit guard is tested both at the unit level (ledger + `check_quota` with fake
  totals) and end to end (real `transaction.commit()` in the integration layer, with
  `plone.api.content.create`, copy/paste, and a direct `obj.file = ...; obj.reindexObject()`
  all aborted when over the limit).
