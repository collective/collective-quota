---
myst:
  html_meta:
    "description": "The blob_size catalog index and metadata column."
    "property=og:description": "The blob_size catalog index and metadata column."
    "property=og:title": "Catalog index blob_size"
    "keywords": "Plone, Collective Quota, catalog, index, blob_size"
---

# Catalog index `blob_size`

| | |
|---|---|
| Index name | `blob_size` |
| Index type | `BlobSizeIndex` (a `FieldIndex` subclass, addable in the ZMI) |
| Metadata column | `blob_size` |
| Value | Sum in bytes of the stored sizes of all file and image fields of the item |
| Not indexed | Items whose type has no file or image field |

Queries work like any field index:

```python
catalog(blob_size={"query": 1, "range": "min"}, sort_on="blob_size",
        sort_order="descending", sort_limit=25)
```

The index keeps a `BTrees.Length.Length` counter of the site total, updated on every
index and unindex call. `total()` returns it; `rebuild_total()` recomputes it from the
indexed values. Clearing the index resets it. "Clear and rebuild" or "Reindex" in the
ZMI therefore also repair the total.

The metadata column is filled when an item is cataloged with metadata. If the column
is empty for old items (for example after `reindexIndex`), `@@quota-usage` falls back
to the value in the index.
