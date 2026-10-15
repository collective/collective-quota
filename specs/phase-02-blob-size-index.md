# Phase 2 — `blob_size` indexer, `BlobSizeIndex` with running total, install-time population

Status: Done
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
script, `guard.py` and `settings.py` stubs, tests.

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
        # bool is an int subclass but never a size
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        return 0

    def _apply_delta(self, delta):
        if delta:
            self._ensure_total().change(delta)
            guard.note_index_change(self, delta)

    def _index_object(self, documentId, obj, threshold=None, attr=""):
        # Compare stored values; do NOT trust the return status (see below).
        old = self._stored(documentId)
        changed = super()._index_object(documentId, obj, threshold, attr)
        self._apply_delta(self._stored(documentId) - old)
        return changed

    def unindex_object(self, documentId):
        old = self._stored(documentId)
        super().unindex_object(documentId)
        self._apply_delta(-old)

    def _ensure_total(self):
        if self._total is None:
            self.rebuild_total()
        return self._total

    def total(self) -> int:
        return self._ensure_total()()

    def rebuild_total(self) -> int:
        self._total = Length(sum(self._stored(rid) for rid in self._unindex))
        return self._total()
```

Why the delta is always computed from stored values: `UnIndex._index_object` removes
an existing entry when the new datum is `None` but **returns 0**, so a total that only
moved when the base reported a change would miss those removals.

`ZCatalog.reindexIndex` (ZMI "Reindex" on the index) only re-catalogs each path; the
index gets no "pass started/finished" signal. So "Reindex" populates an empty index and
keeps a correct total correct, but it does **not** repair a corrupted total. Repair
paths: ZMI "Clear" + "Reindex" on the index, "Clear and rebuild" on the catalog, or
`@@quota-rebuild` / `rebuild_usage()` (which calls `rebuild_total()`).

Zope product registration so GenericSetup can instantiate the meta type:

```python
# catalog/blob_size_index.py
def manage_addBlobSizeIndex(self, id, extra=None, REQUEST=None, RESPONSE=None, URL3=None):
    return self.manage_addIndex(id, "BlobSizeIndex", extra=extra, REQUEST=REQUEST, RESPONSE=RESPONSE, URL1=URL3)

manage_addBlobSizeIndexForm = PageTemplateFile(
    "templates/add_blob_size_index.pt", globals(), __name__="manage_addBlobSizeIndexForm"
)  # without __name__ the product registers the form as "add_blob_size_index"

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

Test layer: `five:registerPackage` initializers only run for installed products, so
`setUpZope` calls `plone.testing.zope.installProduct(app, "collective.quota")` (and
`tearDownZope` uninstalls it). Without it GenericSetup cannot find the meta type.

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

`QuotaSettings` and `get_settings()` live in `settings.py` (architecture §2) and are
re-exported by `usage.py`. In this phase `settings.py` is a stub: `DEFAULTS`, the frozen
`QuotaSettings` dataclass (`soft_bytes`, `hard_bytes`, `policy`, `max_file_bytes`,
`sources`, `locked`) and `get_settings()` returning the built-in defaults with every
source `default`. Phase 3 replaces `get_settings()`.

```python
@dataclass(frozen=True)
class UsageInfo:
    total: int
    soft: int
    hard: int
    percent: int | None      # of hard limit, None when hard disabled
    level: str               # "ok" | "warning" | "exceeded"

def get_index(portal=None) -> BlobSizeIndex | None    # None if missing or not a BlobSizeIndex
def get_total_usage(portal=None) -> int               # flushes the indexing queue; 0 when index missing
def get_usage_info(portal=None) -> UsageInfo          # percent = total * 100 // hard (floor; may exceed 100)
def rebuild_usage(portal, update_metadata=True, log_every=1000, commit_every=0) -> int
```

**Indexing queue.** Plone queues `reindexObject()`, content creation and deletion
(`Products.CMFCore.indexing`), and flushes the queue on the next catalog *search* or in
its own before-commit hook. Reading the index directly does neither, so
`get_total_usage()` and `rebuild_usage()` call `processQueue()` first (cheap when the
queue is empty). Without it the total lags behind changes made earlier in the same
request.

`rebuild_usage` is the shared repair routine used by `post_install`, `@@quota-rebuild`,
future upgrade steps, and the `zconsole` script. It runs inside `guard_suspended()`
(phase 4) because a first population looks like a huge unapproved delta to the commit
guard; until phase 4 lands, `guard_suspended` is a no-op context manager stub in
`guard.py`:

```python
index = get_index(portal)
if index is None: return 0
processQueue()
# An empty query returns NOTHING in current ZCatalog: query by the site path.
brains = catalog.unrestrictedSearchResults(path="/".join(portal.getPhysicalPath()))
for each brain (in batches of commit_every when > 0, each batch inside guard_suspended()):
    obj = brain._unrestrictedGetObject()   # ConflictError re-raised; other errors logged, skipped
    catalog.catalog_object(obj, idxs=["blob_size"], update_metadata=1 if update_metadata else 0)
    log every log_every items
    after a full batch: transaction.commit()
index.rebuild_total()
return count   # items re-cataloged, including the site root
```

`commit_every` exists for the zconsole script; the suspension is re-entered for each
batch because the guard ledger is per transaction.

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

- `@@quota-rebuild` (`browser/rebuild.py`): POST only (other methods raise
  `zExceptions.MethodNotAllowed`, HTTP 405), requires `plone.protect`
  authenticator and `ManageSettings`; calls `rebuild_usage`, adds a status message with
  the item count and the new total, redirects to `@@quota-controlpanel` (phase 3) or the
  portal if that view does not exist yet.
- `backend/scripts/rebuild_blob_size.py`: run with
  `.venv/bin/zconsole run instance/etc/zope.conf scripts/rebuild_blob_size.py [site-id]`;
  commits every 1000 objects; documented for very large sites. `zconsole run` does not
  pass extra arguments to the script, so the site id is read from the last `sys.argv`
  entry (default `Plone`). `main(app, site_id)` returns 0, or 1 if the site is missing.

## Files

Create:
- `backend/src/collective/quota/catalog/blob_size_index.py`
- `backend/src/collective/quota/catalog/templates/add_blob_size_index.pt`
- `backend/src/collective/quota/indexers/blob_size.py`
- `backend/src/collective/quota/usage.py`
- `backend/src/collective/quota/browser/rebuild.py`
- `backend/src/collective/quota/profiles/uninstall/catalog.xml`
- `backend/scripts/rebuild_blob_size.py`
- `backend/src/collective/quota/guard.py` (stub), `settings.py` (stub)
- `backend/tests/test_indexer.py`, `test_index_total.py`, `test_install_existing_content.py`, `test_rebuild.py`, `test_index_zmi.py`, `test_usage_api.py`

Modify:
- `backend/src/collective/quota/__init__.py` (`initialize`)
- `backend/src/collective/quota/configure.zcml` (`five:registerPackage`)
- `backend/src/collective/quota/indexers/configure.zcml`
- `backend/src/collective/quota/browser/configure.zcml` (`@@quota-rebuild`)
- `backend/src/collective/quota/profiles/default/catalog.xml`
- `backend/src/collective/quota/profiles.zcml` (`post_handler`)
- `backend/src/collective/quota/setuphandlers/__init__.py`
- `backend/src/collective/quota/testing.py` (`installProduct`)
- `backend/tests/test_scaffold.py` (`initial` profile test moved to the functional layer)

## Tasks

- [x] Implement `iter_blob_fields`, `get_stored_value`, `get_blob_sizes`, `has_blob_fields`, `blob_size` indexer; register adapter
- [x] Implement `BlobSizeIndex` with `_total`, `total()`, `rebuild_total()`
- [x] Implement `manage_addBlobSizeIndex` + minimal add form; `initialize()` + `five:registerPackage`
- [x] `catalog.xml` (default) and `catalog.xml` (uninstall)
- [x] Implement `usage.py` (`get_index`, `get_total_usage`, `get_settings` stub returning defaults, `get_usage_info`, `rebuild_usage`)
- [x] `post_install` handler wired through `profiles.zcml`
- [x] `@@quota-rebuild` view with CSRF + permission
- [x] `scripts/rebuild_blob_size.py`
- [x] Verify in a running site: `blob_size` is a `BlobSizeIndex`; "Reindex" and "Clear and rebuild" keep `total()` correct; the script repairs a zeroed total
- [x] `guard.py` stub: `note_index_change(index, delta)` no-op and `guard_suspended()` no-op context manager, both covered by tests
- [x] `make lint` / `make format` clean; coverage 100 %

## Tests

- [x] `test_indexer.py::test_file_indexed` — File with 10 KB blob → `blob_size == 10240` in index and metadata
- [x] `test_indexer.py::test_image_indexed` — Image → size of the PNG
- [x] `test_indexer.py::test_lead_image_behavior` — Document with lead image → indexed. In the test layer Document *has* the lead image field, so a Document without an image is indexed as `0`; the "not in index" case uses Folder and Link (`catalog(blob_size={...})` does not return them; `brain.blob_size is Missing.Value`)
- [x] `test_indexer.py::test_multi_field_sum` — `quota_multi` with 3 blobs → sum; clearing one field → sum updated after reindex
- [x] `test_indexer.py::test_empty_blob_fields_index_zero` — File with no file → `0`
- [x] `test_indexer.py::test_corrupt_blob_counts_zero_and_logs`
- [x] `test_index_total.py::test_total_follows_add_edit_delete` — create 3 files, assert total; replace one file, assert; delete one, assert
- [x] `test_index_total.py::test_total_follows_move_copy_rename` — `api.content.move`, `copy`, `rename`; total changes only on copy
- [x] `test_index_total.py::test_total_follows_folder_delete` — deleting a folder with 2 files subtracts both
- [x] `test_index_total.py::test_clear_and_rebuild_restores_total` — corrupt `_total`, `catalog.clearFindAndRebuild()` (queued in Plone 6) → `get_total_usage()` equals recomputed sum
- [x] `test_index_total.py::test_reindex_index_populates_empty_index` — `manage_clearIndex` then `reindexIndex("blob_size", request)` → correct total
- [x] `test_index_total.py::test_reindex_index_keeps_correct_total`
- [x] `test_index_total.py::TestIndexUnit` — standalone index: index/reindex/unindex deltas, datum `None` removal subtracts, missing attribute kept out, non-int values (`True`, `1.5`) ignored, `clear()`, `note_index_change` called only for non-zero deltas
- [x] `test_index_total.py::test_total_lazy_rebuild_when_attribute_missing` — simulate old pickle (`del index._total`) → `total()` recomputes
- [x] `test_install_existing_content.py` — uninstall add-on, create content, reinstall → index, metadata, and total populated by `post_install`
- [x] `test_rebuild.py` — `@@quota-rebuild` GET → `MethodNotAllowed`, POST without token → `Forbidden`, POST as Manager → total rebuilt, status message, redirect to the portal (or to `@@quota-controlpanel` when that view exists); Editor/Contributor/Reviewer/Member → `Unauthorized`, Manager/Site Administrator allowed (integration `restrictedTraverse`; the testbrowser hits a closed-connection error while re-raising `Unauthorized`)
- [x] `test_rebuild.py::test_script_runs` — import the script's `main(app, site_id)` and run it against the test app; also the "site id not found" branch
- [x] `test_index_zmi.py` — `manage_addBlobSizeIndex` adds an index of the right meta type through a ZMI-style call; the add form renders; `initialize()` registers the class (`Products.meta_types` contains `BlobSizeIndex`)
- [x] `test_usage_api.py` — `get_index` returns `None` without the index; `get_total_usage` returns 0 then; `get_usage_info` levels `ok`/`warning`/`exceeded` and `percent` `None` when hard is disabled; `rebuild_usage` logs every `log_every` items and skips objects that fail to load

## Acceptance criteria

- On a site with pre-existing Files/Images, installing the add-on makes
  `portal_catalog.searchResults(sort_on="blob_size", sort_order="descending")` return
  the biggest items first, and `get_total_usage()` equals the sum of their sizes.
- Uploading, replacing, deleting, moving, copying content keeps `get_total_usage()`
  exact without any extra step.
- ZMI "Clear and rebuild" never leaves a wrong total.

## Notes / risks

Implementation notes (2026-10-15):

- Verified with zconsole on a real instance: a bare site with 3 Files + 1 Image and no
  add-on; installing through the Add-ons installer populated index, column and total
  (biggest-first sort correct); replace/delete/move/copy kept the total exact after
  commit; `manage_catalogRebuild` and `manage_reindexIndex` kept it exact; the script
  repaired a hand-zeroed total. The ZMI screens themselves were not clicked through;
  the add form is covered by a render test.
- `plone.exportimport` commits during import, which leaked example content out of the
  integration sandbox into later tests; the `initial` profile test now runs on the
  functional layer.

- `catalog_object(..., update_metadata=1)` refreshes **all** metadata columns of the
  item, which is fine but means the install step is as expensive as a full catalog
  update of metadata. Document it in the control panel help text and README.
- If a site uses `collective.indexing`/queued indexing, the total updates when the queue
  flushes (end of request) — still within the same transaction.
- Type-check `isinstance(value, int)` when summing: a mis-registered indexer returning
  `None`/`Missing.Value` must not break the counter.
