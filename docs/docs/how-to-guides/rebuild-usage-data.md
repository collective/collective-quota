---
myst:
  html_meta:
    "description": "Recompute the disk usage numbers, from the browser or with a script on large sites."
    "property=og:description": "Recompute the disk usage numbers, from the browser or with a script on large sites."
    "property=og:title": "Rebuild usage data on a large site"
    "keywords": "Plone, Collective Quota, rebuild, zconsole"
---

# Rebuild usage data on a large site

The catalog keeps the usage numbers up to date, so most sites never need this. Rebuild when
the total looks wrong, for example after restoring a database backup or after changing
the catalog outside Plone.

## From the browser

As a Manager or Site Administrator, select **Rebuild usage data** at the bottom of the
Quota control panel, or under the summary of the disk usage page. It re-catalogs
every item in one request, which is fine for small and medium sites.

## With a script

On large sites, one request may take too long. Use the script
[`backend/scripts/rebuild_blob_size.py`](https://github.com/collective/collective-quota/blob/main/backend/scripts/rebuild_blob_size.py)
from the source repository, which commits every 1000 items. Copy it into your
project and run it, passing the site id. With a plain `Data.fs` (FileStorage), stop
Plone first, because only one process can open the database; with ZEO or RelStorage
it can run next to the running instances.

```shell
.venv/bin/zconsole run instance/etc/zope.conf scripts/rebuild_blob_size.py Plone
```

It logs its progress every 1000 items and the new total at the end.

## From your own code

```python
from collective.quota.usage import rebuild_usage

count = rebuild_usage(portal, update_metadata=True, commit_every=1000)
```

`rebuild_usage` runs inside `guard_suspended()`, so it works on a site that is over
its quota.
