---
myst:
  html_meta:
    "description": "Public Python API of Collective Quota."
    "property=og:description": "Public Python API of Collective Quota."
    "property=og:title": "Python API"
    "keywords": "Plone, Collective Quota, Python, API"
---

# Python API

## `collective.quota.usage`

`get_total_usage(portal=None) -> int`
:   Bytes used by all file and image fields of the site. `0` when the index is
    missing. Flushes Plone's indexing queue first, so changes made earlier in the same
    request are counted.

`get_usage_info(portal=None) -> UsageInfo`
:   Frozen dataclass with `total`, `soft`, `hard` (bytes), `percent` (of the hard
    limit, or `None` when it is disabled) and `level` (`"ok"`, `"warning"` or
    `"exceeded"`).

`rebuild_usage(portal, update_metadata=True, log_every=1000, commit_every=0) -> int`
:   Re-catalogs every item for `blob_size` and recomputes the total, with the commit
    guard suspended. `commit_every` > 0 commits every that many items. Returns the
    number of items processed.

`get_index(portal=None) -> BlobSizeIndex | None`
:   The `blob_size` index.

## `collective.quota.settings`

`get_settings() -> QuotaSettings`
:   Effective settings: `soft_bytes`, `hard_bytes`, `policy`, `max_file_bytes`,
    `values` (in MB and tokens, per setting), `sources` and `locked`.

`ENV_VARS`, `LOCK_VAR`
:   Environment variable names per setting, and of the lock flag.

`set_registry_value(name, value)`
:   Store one setting; `None` clears it.

## `collective.quota.policy`

`evaluate_upload(total, old_size, new_size, settings) -> Decision`
:   Whether one upload is allowed (see {doc}`../concepts/limits-and-policies`).

`evaluate_add(total, settings) -> Decision`
:   Whether a new item may be added.

`Decision`
:   `allowed`, `reason` and `mapping`; `message` is a translatable message.

`QuotaExceeded`
:   A `zope.schema` `ValidationError` carrying the `decision`.

## `collective.quota.guard`

`guard_suspended()`
:   Context manager that exempts the changes made inside it from all quota checks.
    See {doc}`commit-guard`.

`QuotaCommitAborted`
:   Raised by `transaction.commit()` when the commit guard cancels a transaction.
    Has `reason`, `mapping` and a translated `message`.

`record_approved_bytes(n)`, `record_approved_add()`
:   For custom forms or endpoints that check the policy themselves: tell the commit
    guard that `n` bytes, or one new item, were approved in this transaction.

## `collective.quota.indexers.blob_size`

`get_blob_sizes(obj) -> dict[str, int]`
:   Size per file or image field of one item.

`has_blob_fields(obj) -> bool`
:   Whether the item's type has any file or image field.
