# Phase 2 — `blob_size` indexer, `BlobSizeIndex` with running total, install-time population

Status: Not started
Depends on: Phase 1
Last updated: 2026-10-15

## Goal

Every content item that has at least one blob field gets a `blob_size` value (bytes,
sum of all its blob fields) in `portal_catalog`, both as an index and as a metadata
column. The index keeps a site-wide running total that is O(1) to read. Installing on
a site with existing content populates everything; the ZMI catalog tools keep it right.

## Scope

In: indexer + helpers, custom index class and Zope product registration, `catalog.xml`,
`post_install` population, `usage.py` read API, `@@quota-rebuild` view, `zconsole`
script, tests.

Out: settings (phase 3), enforcement (phase 4), listing UI (phase 5).

## Design

### Indexer and helpers — `indexers/blob_size.py`

```python
from plone.dexterity.interfaces import IDexterityContent
from plone.dexterity.utils import iterSchemata
from plone.indexer import indexer
from plone.namedfile.interfaces import INamedField
from zope.schema import getFieldsInOrder


def iter_blob_fields(obj):
    """Yield (schema, name, field) for every INamedField on obj (type schema + behaviors)."""
    for schema in iterSchemata(obj):
        for name, field in getFieldsInOrder(schema):
            if INamedField.providedBy(field):
                yield schema, name, field


def get_stored_value(obj, schema, name):
    adapter = schema(obj, None)        # obj itself for the main schema, behavior adapter otherwise
    if adapter is None:
        return None
    return getattr(adapter, name, None)


def get_blob_sizes(obj) -> dict[str, int]:
    sizes = {}
    for schema, name, _field in iter_blob_fields(obj):
        value = get_stored_value(obj, schema, name)
        size = 0
        if value is not None:
            try:
                size = int(value.getSize() or 0)
            except Exception:   # corrupt blob, missing file on disk: log and count 0
                logger.warning(...)
        sizes[name] = size
    return sizes


def has_blob_fields(obj) -> bool:
    return any(True for _ in iter_blob_fields(obj))


@indexer(IDexterityContent)
def blob_size(obj):
    sizes = get_blob_sizes(obj)
    if not sizes:
        raise AttributeError("no blob fields")   # keeps the item out of the index
    return sum(sizes.values())
```

Registration in `indexers/configure.zcml`:
`<adapter factory=".blob_size.blob_size" name="blob_size" />`.

Rules:
- Items without blob fields are not indexed (`AttributeError` → ZCatalog `_marker`).
- Items with blob fields but no file stored get `0`.
- `getSize()` on `NamedBlobFile`/`NamedBlobImage` reads the stored `_size`; it does not
  open the blob. Never read `.data`.
- The Plone site root, folders, documents without lead image: not indexed.

### Index class — `catalog/blob_size_index.py`

The index is also the place where the commit guard (phase 4) learns that bytes changed:
`_index_object` and `unindex_object` call `guard.note_index_change(self, delta)` after
applying a non-zero delta. In this phase that function is a stub that records nothing;
phase 4 implements it. The call site is specified here so the index does not change
shape later.

```python
from BTrees.Length import Length
from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex


class BlobSizeIndex(FieldIndex):
    """FieldIndex that also keeps the sum of all indexed values."""

    meta_type = "BlobSizeIndex"
    _total = None

    def clear(self):
        super().clear()
        self._total = Length(0)

    def _stored(self, documentId) -> int:
        value = self._unindex.get(documentId, 0)
        return value if isinstance(value, int) else 0

    def _index_object(self, documentId, obj, threshold=None, attr=""):
        old = self._stored(documentId)
        changed = super()._index_object(documentId, obj, threshold, attr)
        if changed:
            self._ensure_total().change(self._stored(documentId) - old)
        return changed

    def unindex_object(self, documentId):
        old = self._stored(documentId)
        super().unindex_object(documentId)
        if old:
            self._ensure_total().change(-old)

    def _ensure_total(self):
        if self._total is None:
            self.rebuild_total()
        return self._total

    def total(self) -> int:
        return self._ensure_total()()

    def rebuild_total(self) -> int:
        self._total = Length(sum(v for v in self._unindex.values() if isinstance(v, int)))
        return self._total()
```

Zope product registration so GenericSetup can instantiate the meta type:

```python
# catalog/blob_size_index.py
def manage_addBlobSizeIndex(self, id, extra=None, REQUEST=None, RESPONSE=None, URL3=None):
    return self.manage_addIndex(id, "BlobSizeIndex", extra=extra, REQUEST=REQUEST, RESPONSE=RESPONSE, URL1=URL3)

manage_addBlobSizeIndexForm = PageTemplateFile("templates/add_blob_size_index.pt", globals())

# __init__.py
def initialize(context):
    from collective.quota.catalog.blob_size_index import BlobSizeIndex, manage_addBlobSizeIndex, manage_addBlobSizeIndexForm
    context.registerClass(
        BlobSizeIndex,
        permission="Add Pluggable Index",
        constructors=(manage_addBlobSizeIndexForm, manage_addBlobSizeIndex),
        visibility=None,
    )
```

`configure.zcml`: `<five:registerPackage package="." initialize=".initialize" />`
(needs `xmlns:five`). The ZMI add form is a minimal template (id field + submit),
mirroring `Products.PluginIndexes` forms; it only matters for ZMI users.

`profiles/default/catalog.xml`:

```xml
<object name="portal_catalog">
  <index name="blob_size" meta_type="BlobSizeIndex">
    <indexed_attr value="blob_size" />
  </index>
  <column value="blob_size" />
</object>
```

`profiles/uninstall/catalog.xml` removes both (`remove="True"`).

### Read API — `usage.py`

```python
@dataclass(frozen=True)
class QuotaSettings:
    soft_bytes: int
    hard_bytes: int
    policy: str
    max_file_bytes: int

@dataclass(frozen=True)
class UsageInfo:
    total: int
    soft: int
    hard: int
    percent: int | None      # of hard limit, None when hard disabled
    level: str               # "ok" | "warning" | "exceeded"

def get_index(portal=None) -> BlobSizeIndex | None    # portal_catalog._catalog.getIndex("blob_size"), None if missing
def get_total_usage(portal=None) -> int               # 0 when index missing
def get_settings() -> QuotaSettings                   # reads registry (phase 3 wires the records; until then returns zeros/defaults)
def get_usage_info(portal=None) -> UsageInfo
def rebuild_usage(portal, update_metadata=True, log_every=1000) -> int
```

`rebuild_usage` is the shared repair routine used by `post_install`, `@@quota-rebuild`,
future upgrade steps, and the `zconsole` script. It runs inside `guard_suspended()`
(phase 4) because a first population looks like a huge unapproved delta to the commit
guard; until phase 4 lands, `guard_suspended` is a no-op context manager stub in
`guard.py`:

```python
catalog = api.portal.get_tool("portal_catalog")
for i, brain in enumerate(catalog.unrestrictedSearchResults(), 1):
    obj = brain._unrestrictedGetObject()
    catalog.catalog_object(obj, idxs=["blob_size"], update_metadata=1 if update_metadata else 0)
    if i % log_every == 0: logger.info(...)
index = get_index(portal); index.rebuild_total()
return count   # number of objects visited (0 on an empty catalog)
```

`update_metadata=1` is what makes the `blob_size` **column** correct for existing
content; plain ZMI "reindex index" leaves the column empty. Consumers (phase 5) must
fall back to `index.getEntryForObject(brain.getRID(), 0)` when the metadata is
`Missing.Value`.

### Install hook — `setuphandlers/__init__.py`

Cookieplone profiles use `post_handler` on the `genericsetup:registerProfile`
directive. Add `post_handler=".setuphandlers.post_install"` to the `default` profile
registration in `profiles.zcml` and implement `post_install(context)` →
`rebuild_usage(portal, update_metadata=True)`. It runs on install **and** on reinstall
and must be resilient to objects that fail to load (log and continue).

### Manual repair entry points

- `@@quota-rebuild` (`browser/rebuild.py`): POST only, requires `plone.protect`
  authenticator and `ManageSettings`; calls `rebuild_usage`, adds a status message with
  the item count and the new total, redirects to `@@quota-controlpanel` (phase 3) or the
  portal if that view does not exist yet.
- `backend/scripts/rebuild_blob_size.py`: run with
  `.venv/bin/zconsole run instance/etc/zope.conf scripts/rebuild_blob_size.py [site-id]`;
  commits every 1000 objects; documented for very large sites.

## Files

Create:
- `backend/src/collective/quota/catalog/blob_size_index.py`
- `backend/src/collective/quota/catalog/templates/add_blob_size_index.pt`
- `backend/src/collective/quota/indexers/blob_size.py`
- `backend/src/collective/quota/usage.py`
- `backend/src/collective/quota/browser/rebuild.py`
- `backend/src/collective/quota/profiles/uninstall/catalog.xml`
- `backend/scripts/rebuild_blob_size.py`
- `backend/tests/test_indexer.py`, `test_index_total.py`, `test_install_existing_content.py`, `test_rebuild.py`

Modify:
- `backend/src/collective/quota/__init__.py` (`initialize`)
- `backend/src/collective/quota/configure.zcml` (`five:registerPackage`)
- `backend/src/collective/quota/indexers/configure.zcml`
- `backend/src/collective/quota/browser/configure.zcml` (`@@quota-rebuild`)
- `backend/src/collective/quota/profiles/default/catalog.xml`
- `backend/src/collective/quota/profiles.zcml` (`post_handler`)
- `backend/src/collective/quota/setuphandlers/__init__.py`

## Tasks

- [ ] Implement `iter_blob_fields`, `get_stored_value`, `get_blob_sizes`, `has_blob_fields`, `blob_size` indexer; register adapter
- [ ] Implement `BlobSizeIndex` with `_total`, `total()`, `rebuild_total()`
- [ ] Implement `manage_addBlobSizeIndex` + minimal add form; `initialize()` + `five:registerPackage`
- [ ] `catalog.xml` (default) and `catalog.xml` (uninstall)
- [ ] Implement `usage.py` (`get_index`, `get_total_usage`, `get_settings` stub returning defaults, `get_usage_info`, `rebuild_usage`)
- [ ] `post_install` handler wired through `profiles.zcml`
- [ ] `@@quota-rebuild` view with CSRF + permission
- [ ] `scripts/rebuild_blob_size.py`
- [ ] Verify in a running site: ZMI → portal_catalog → Indexes shows `blob_size` of type `BlobSizeIndex`; "Reindex" works; "Clear and rebuild" keeps `total()` correct
- [ ] `guard.py` stub: `note_index_change(index, delta)` no-op and `guard_suspended()` no-op context manager, both covered by tests
- [ ] `make lint` / `make format` clean; coverage 100 %

## Tests

- [ ] `test_indexer.py::test_file_indexed` — File with 10 KB blob → `blob_size == 10240` in index and metadata
- [ ] `test_indexer.py::test_image_indexed` — Image → size of the PNG
- [ ] `test_indexer.py::test_lead_image_behavior` — Document with lead image → indexed; Document without blob fields → not in index (`catalog(blob_size={...})` does not return it; `brain.blob_size is Missing.Value`)
- [ ] `test_indexer.py::test_multi_field_sum` — `quota_multi` with 3 blobs → sum; clearing one field → sum updated after reindex
- [ ] `test_indexer.py::test_empty_blob_fields_index_zero` — File with no file → `0`
- [ ] `test_indexer.py::test_corrupt_blob_counts_zero_and_logs`
- [ ] `test_index_total.py::test_total_follows_add_edit_delete` — create 3 files, assert total; replace one file, assert; delete one, assert
- [ ] `test_index_total.py::test_total_follows_move_copy_rename` — `api.content.move`, `copy`, `rename`; total changes only on copy
- [ ] `test_index_total.py::test_total_follows_folder_delete` — deleting a folder with 2 files subtracts both
- [ ] `test_index_total.py::test_clear_and_rebuild_restores_total` — `catalog.clearFindAndRebuild()` → total equals recomputed sum
- [ ] `test_index_total.py::test_reindex_index_restores_total` — zero `_total` by hand, `catalog.reindexIndex("blob_size", request)` → correct
- [ ] `test_index_total.py::test_total_lazy_rebuild_when_attribute_missing` — simulate old pickle (`del index._total`) → `total()` recomputes
- [ ] `test_install_existing_content.py` — uninstall add-on, create content, reinstall → index, metadata, and total populated by `post_install`
- [ ] `test_rebuild.py` — `@@quota-rebuild` GET → 405/redirect, POST without token → 403, POST as Manager → total rebuilt and status message; Editor → `Unauthorized`
- [ ] `test_rebuild.py::test_script_runs` — import the script's `main(app, site_id)` and run it against the test app; also the "site id not found" branch
- [ ] `test_index_zmi.py` — `manage_addBlobSizeIndex` adds an index of the right meta type through a ZMI-style call; the add form renders; `initialize()` registers the class (`Products.meta_types` contains `BlobSizeIndex`)
- [ ] `test_usage_api.py` — `get_index` returns `None` without the index; `get_total_usage` returns 0 then; `get_usage_info` levels `ok`/`warning`/`exceeded` and `percent` `None` when hard is disabled; `rebuild_usage` logs every `log_every` items and skips objects that fail to load

## Acceptance criteria

- On a site with pre-existing Files/Images, installing the add-on makes
  `portal_catalog.searchResults(sort_on="blob_size", sort_order="descending")` return
  the biggest items first, and `get_total_usage()` equals the sum of their sizes.
- Uploading, replacing, deleting, moving, copying content keeps `get_total_usage()`
  exact without any extra step.
- ZMI "Clear and rebuild" never leaves a wrong total.

## Notes / risks

- `catalog_object(..., update_metadata=1)` refreshes **all** metadata columns of the
  item, which is fine but means the install step is as expensive as a full catalog
  update of metadata. Document it in the control panel help text and README.
- If a site uses `collective.indexing`/queued indexing, the total updates when the queue
  flushes (end of request) — still within the same transaction.
- Type-check `isinstance(value, int)` when summing: a mis-registered indexer returning
  `None`/`Missing.Value` must not break the counter.
