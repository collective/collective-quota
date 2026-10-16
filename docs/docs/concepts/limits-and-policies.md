---
myst:
  html_meta:
    "description": "The soft limit, the hard limit and the four over-limit policies of Collective Quota."
    "property=og:description": "The soft limit, the hard limit and the four over-limit policies of Collective Quota."
    "property=og:title": "Limits and policies"
    "keywords": "Plone, Collective Quota, soft limit, hard limit, policy"
---

# Limits and policies

Collective Quota has two thresholds and a policy.

{term}`Soft limit`
:   Only warns. When the total reaches it, people who can see disk usage get a yellow
    banner on every page.

{term}`Hard limit`
:   When a save would push the total above it, the {term}`policy` decides what
    happens. The banner turns red.

Both are in megabytes (1 MB = 1024 × 1024 bytes); `0` disables a limit.

## How a save is judged

For each upload, Collective Quota compares the size of the new file with the size of
the file it replaces (0 for a new item). Then:

1. With the hard limit disabled, the save is allowed.
2. If the upload does not add bytes (removing a file, or replacing it with a smaller
   or equal one), it is allowed. Editors can always clean up.
3. If the site stays at or below the hard limit after the save, it is allowed.
4. Otherwise the policy applies.

| Policy | New items without files | Uploads that add bytes |
|---|---|---|
| `block_all`: Block new items and any upload that adds bytes | refused | refused |
| `block_files`: Allow new items, block uploads that add bytes | allowed | refused |
| `limit_file_size`: Allow uploads up to a maximum file size | allowed | allowed if the file is not bigger than the maximum file size |
| `allow`: Allow everything, only show warnings | allowed | allowed |

"New items without files" is checked once per add, for example when an editor adds a
Document while the site is already over the hard limit.

## Examples

With a hard limit of 100 MB and 95 MB in use:

| Action | Policy | Result |
|---|---|---|
| Upload a 3 MB file | any | allowed (98 MB ≤ 100 MB) |
| Upload a 10 MB file | `block_all`, `block_files` | refused |
| Upload a 10 MB file | `limit_file_size`, maximum 20 MB | allowed |
| Upload a 30 MB file | `limit_file_size`, maximum 20 MB | refused |
| Replace a 40 MB file with a 20 MB one, at 120 MB in use | any | allowed |
| Add a Document, at 120 MB in use | `block_all` | refused |
| Add a Document, at 120 MB in use | `block_files` | allowed |

## Where the limit is enforced

Classic add and edit forms check uploads before saving and show the error on the
field. The REST API checks the same way and answers `400 Bad Request`.

Everything else (copy and paste, `plone.api` calls in scripts, imports, other
add-ons) is checked by the {term}`commit guard` when the transaction ends. If the
change crossed the hard limit without a form or the REST API having approved it,
the whole transaction is cancelled. Bypass paths are judged more strictly than forms:
under `limit_file_size`, a paste of small files that crosses the limit is cancelled
too, because no form approved it.

Administrators who must load content on a site that is over its quota (migrations,
imports) can run their code inside `guard_suspended()`; see
{doc}`../how-to-guides/run-imports-over-quota`.
