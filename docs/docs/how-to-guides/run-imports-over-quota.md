---
myst:
  html_meta:
    "description": "Use guard_suspended() to load content in trusted code without hitting the quota."
    "property=og:description": "Use guard_suspended() to load content in trusted code without hitting the quota."
    "property=og:title": "Run imports and migrations on a site over quota"
    "keywords": "Plone, Collective Quota, guard_suspended, migration, import"
---

# Run imports and migrations on a site over quota

The {term}`commit guard` cancels any transaction that crosses the hard limit, also
in scripts. That is what you want for normal code, but not for an administrator who
must load content into a site that is already full, for example during a migration.

Wrap the trusted code in `guard_suspended()`:

```python
from collective.quota.guard import guard_suspended
from plone import api

import transaction

with guard_suspended():
    for item in items_to_import:
        api.content.create(container=folder, type="File", **item)
    transaction.commit()
```

Changes made inside the block are not checked: not by the commit guard, and not by
the upload checks that `plone.restapi` and `plone.exportimport` run. Changes made
outside the block, in the same transaction or later, are checked as usual. Commits
made inside the block are covered too.

Each use is logged at INFO level with the caller. There is no way to reach
`guard_suspended()` from a browser or the REST API.

When you can, prefer raising the hard limit for the duration of the job instead, for
example with `COLLECTIVE_QUOTA_HARD_LIMIT_MB`, so that the quota keeps applying to
everyone else.
