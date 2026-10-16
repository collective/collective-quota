---
myst:
  html_meta:
    "description": "How the commit guard of Collective Quota works."
    "property=og:description": "How the commit guard of Collective Quota works."
    "property=og:title": "Commit guard"
    "keywords": "Plone, Collective Quota, commit guard, transaction"
---

# Commit guard

Forms and the REST API check uploads before saving. The commit guard covers every
other way of changing content.

## What it checks

While a transaction runs, Collective Quota writes a small ledger into it:

- the site total when the first change happened,
- the bytes added by changes in the `blob_size` index,
- the bytes approved by the form and REST checks,
- the number of new items, and how many of them were approved.

The first change that adds bytes or an item registers a before-commit hook. At
commit, the hook cancels the transaction if the hard limit is enabled and:

- the policy is not `allow`, the site ends above the hard limit, and more bytes were
  added than approved, or
- under `block_all`, the site is at or over the hard limit and more items were added
  than approved.

Transactions that do not change file sizes or add items register nothing and cost
nothing.

## What happens when it cancels

`transaction.commit()` raises `QuotaCommitAborted` (a `zExceptions.BadRequest`), so
nothing is saved. A warning is logged with the user and the numbers. Over HTTP the
response is `400`, with a "Disk quota exceeded" page or JSON (see
{doc}`views-and-viewlet`).

## Suspending it

`guard_suspended()` exempts the changes made inside the block: their bytes are
excluded from the check and their new items are not counted. The upload checks of
forms, `plone.restapi` and `plone.exportimport` are skipped inside the block too.
Suspension applies to the current thread, can be nested, and covers commits made
inside the block. Every use is logged at INFO level with the caller.

## Known limits

- Savepoint rollbacks do not roll back the ledger. Plone does not use savepoints
  around content changes.
- Changes that never reach the catalog are not seen, since the catalog is how sizes
  are measured.
