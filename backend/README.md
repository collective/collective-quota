# collective.quota 💾

Disk quota for Plone sites: measures the space used by uploaded files and images, warns editors near the limit, enforces a hard limit, and helps find and delete the biggest items.

`collective.quota` works with Plone 6.1 and 6.2 in Classic UI. Uploads made through
the REST API (`plone.restapi`) follow the same limits.

## Features ✨

- Measures the size of every file and image field (`File`, `Image`, lead images and
  any `NamedFile`/`NamedImage` field in custom types and behaviors) in a `blob_size`
  catalog index, and keeps a running site-wide total that costs nothing to read.
- Adds a **Quota** control panel with a soft limit (warnings only), a hard limit, the
  policy that applies once the hard limit is reached, and a maximum file size. Every
  setting can also come from an environment variable, and can be locked so that only
  the server operator can change it.
- Enforces the hard limit with four policies, from "block new items and any upload
  that adds bytes" to "only show warnings". Classic edit and add forms show the error
  on the field, and REST clients get `400 Bad Request`.
- Cancels any other change that would cross the hard limit (copy/paste, scripts,
  imports, other add-ons) with a transaction guard, so the limit cannot be bypassed.
- Adds a **Disk usage** page to the user menu that lists the 10, 25, 50 or 100
  biggest items. Editors can open or edit any of them, or select several and delete
  them in one go, with Plone's usual link-integrity warning.
- Shows editors a yellow banner on every page when usage reaches the soft limit, and
  a red one at the hard limit that says what is blocked.
- Ships English and Spanish translations.

## Installation 🔧

Add `collective.quota` to the dependencies of your project's backend package
(the `dependencies` list in its `pyproject.toml`), then install.

```shell
make install
```

Start Plone, then activate **Collective Quota** in **Site Setup → Add-ons**.

```shell
make start
```

Installing measures the files and images that already exist, so the numbers are
right immediately. On sites with hundreds of thousands of items, see
[Rebuilding usage data](#rebuilding-usage-data-).

The `collective.quota:initial` profile adds example content: a folder with two
sample files (2 MB and 500 KB) and an image, and a page that links to the bigger
file, so you can try the disk usage page and the link-integrity warning. To import
it, open `portal_setup` in the ZMI, go to the **Import** tab, select "Collective
Quota: Example content" and click **Import all steps**. When you develop the add-on
itself, `make create-site` imports it for you.

## Configuration ⚙️

Site administrators configure the add-on in **Site Setup → Add-on Configuration →
Quota** (`@@quota-controlpanel`). The page shows the current usage, where every
value comes from, and has buttons to rebuild the usage data and to reset the
settings. The same settings are available to REST clients at
`@controlpanels/collective-quota`.

| Setting | Default | Meaning |
|---|---|---|
| Soft limit (MB) | `0` (disabled) | Editors see a warning when total usage reaches it |
| Hard limit (MB) | `0` (disabled) | Saves that would push usage above it follow the policy |
| Policy when the hard limit is reached | `block_all` | `block_all`, `block_files`, `limit_file_size` or `allow` |
| Maximum file size over the limit (MB) | `10` | Only used by `limit_file_size` |

1 MB is 1024 × 1024 bytes. The soft limit cannot be higher than the hard limit, and
`limit_file_size` needs a maximum file size greater than 0.

### Environment variables 🌍

Every setting can also come from an environment variable of the Zope process
(`environment:` in `docker-compose.yml`, the systemd unit, or the shell that runs
`make start`). No change to `zope.conf` or `instance.yaml` is needed.

| Variable | Setting | Accepted values |
|---|---|---|
| `COLLECTIVE_QUOTA_SOFT_LIMIT_MB` | Soft limit | integer ≥ 0 |
| `COLLECTIVE_QUOTA_HARD_LIMIT_MB` | Hard limit | integer ≥ 0 |
| `COLLECTIVE_QUOTA_OVER_LIMIT_POLICY` | Policy | `block_all`, `block_files`, `limit_file_size`, `allow` |
| `COLLECTIVE_QUOTA_MAX_FILE_SIZE_MB` | Maximum file size | integer ≥ 0 |
| `COLLECTIVE_QUOTA_LOCK_SETTINGS` | Lock flag | `1`, `true`, `yes`, `on` (any case) lock; anything else does not |

Each value is resolved in this order:

1. With `COLLECTIVE_QUOTA_LOCK_SETTINGS` on, a variable that is set wins and is
   read-only in the control panel and over REST.
2. A value saved in the control panel.
3. The environment variable.
4. The built-in default.

Without the lock flag, environment variables act as defaults that the control panel
can override; "Reset to defaults" clears the saved values so they apply again.
Empty variables are ignored. Invalid values are logged once as a warning and
ignored.

```shell
COLLECTIVE_QUOTA_HARD_LIMIT_MB=5000 \
COLLECTIVE_QUOTA_SOFT_LIMIT_MB=4500 \
COLLECTIVE_QUOTA_LOCK_SETTINGS=1 \
make start
```

### Policies 🚦

When a save would push total usage above the hard limit, the policy decides:

| Policy | New items without files | Uploads that add bytes | Replacing with a smaller file |
|---|---|---|---|
| `block_all` | refused | refused | allowed |
| `block_files` | allowed | refused | allowed |
| `limit_file_size` | allowed | allowed up to the maximum file size | allowed |
| `allow` | allowed | allowed (warnings only) | allowed |

An upload that still fits under the hard limit is always allowed. Deleting content
and replacing a file with a smaller one always work, so editors can clean up.
Classic forms show the error on the file field (or at the top of the add form);
REST clients get `400 Bad Request` with the message.

## Permissions 🔐

| Permission | Default roles | Grants |
|---|---|---|
| `collective.quota: Manage Quota Settings` | Manager, Site Administrator | Control panel, "Rebuild usage data" |
| `collective.quota: View Disk Usage` | Manager, Site Administrator, Editor, Contributor, Reviewer | Disk usage page, warning banner, user-menu entry |

Members and anonymous visitors never see usage information. Deleting from the disk
usage page also needs Plone's `Delete objects` permission on each item. To let more
people see the disk usage page, grant `collective.quota: View Disk Usage` to their
role, either on the **Security** tab of the site in the ZMI or in the `rolemap.xml`
of your policy package.

## Disk usage page 📊

"Disk usage" in the user menu opens `@@quota-usage` on the site root. The page shows
the current usage, the limits and the policy, then the 10, 25, 50 or 100 biggest
items the user can see, with links to view or edit each one.

Tick several items and click "Delete selected" (or use an item's "Delete" link): a
confirmation page lists them with their total size and Plone's usual link-integrity
warnings. Items you may not delete, or that another user has locked, are skipped and
reported. Deleting always works, even over the hard limit, and the status message
says how much space was freed.

## Warning banner 🔔

Users with `collective.quota: View Disk Usage` see a banner below the status
messages on every page once usage reaches the soft limit (yellow) or the hard limit
(red, with what the policy now blocks), with a "Review disk usage" button. It is not
shown on the disk usage page or the control panel, which show the numbers anyway.
Anonymous visitors never see it. The banner reads only the running total, so it
costs no catalog query.

Themes with a custom `main_template` that does not render the
`plone.globalstatusmessage` viewlet manager can register `collective.quota.warning`
in another manager through their own `viewlets.xml`.

## How usage is measured 📏

The usage of an item is the sum of the sizes of all its file and image fields, as
stored by `plone.namedfile`. The site total is the sum over all cataloged items.

| Counted | Not counted |
|---|---|
| `File.file`, `Image.image`, the lead image behavior and any `NamedFile`, `NamedImage`, `NamedBlobFile` or `NamedBlobImage` field of custom types and behaviors | Older versions kept by CMFEditions, image scales, rich text and other non-file data, ZODB overhead |
| Working copies (they are regular items) | Content that is not in `portal_catalog` |

Folders do not add up their contents in the listing: each item counts on its own.
The total is therefore lower than the size of `Data.fs` plus the blob storage on
disk.

## Rebuilding usage data 🔄

The catalog keeps the total up to date. If it ever looks wrong (for example after
restoring a database or changing the catalog outside Plone), click **Rebuild usage
data** in the control panel or on the disk usage page. It walks the whole catalog,
so it takes a while on big sites.

For very large sites, the source repository has a script,
[`backend/scripts/rebuild_blob_size.py`](https://github.com/collective/collective-quota/blob/main/backend/scripts/rebuild_blob_size.py),
that commits every 1000 items. Copy it into your project and run it with
`zconsole`, passing the site id. With a plain `Data.fs`, stop Plone first; with ZEO
or RelStorage it can run next to the running instances.

```shell
.venv/bin/zconsole run instance/etc/zope.conf scripts/rebuild_blob_size.py Plone
```

## REST API 🔌

For Volto and other REST clients, on top of `@controlpanels/collective-quota`:

| Endpoint | Permission | Returns |
|---|---|---|
| `GET @quota-usage?limit=25` | View Disk Usage | Usage summary and the biggest items (`limit`: 10, 25, 50 or 100) |
| `POST @quota-rebuild` | Manage Quota Settings | Rebuilds the usage data; `{"items", "total", "total_human"}` |
| `?expand=quota` on any content | View Disk Usage | The usage summary in `@components.quota` |

```shell
curl -u admin:secret -H "Accept: application/json" \
  "http://localhost:8080/Plone/@quota-usage?limit=10"
curl -u admin:secret -H "Accept: application/json" \
  "http://localhost:8080/Plone/news?expand=quota"
curl -X POST -u admin:secret -H "Accept: application/json" \
  http://localhost:8080/Plone/@quota-rebuild
```

Anonymous users and users without the permission never get quota data: the services
answer `401` and the `quota` key is left out of `@components`. With no limits
configured, `limits_configured` is `false` and `message` is `null`. See the
[REST API reference](https://github.com/collective/collective-quota/blob/main/docs/docs/reference/rest-api.md)
for every field.

## For developers 🧑‍💻

### Python API

| Function | Module | Returns |
|---|---|---|
| `get_total_usage(portal=None)` | `collective.quota.usage` | Site total in bytes |
| `get_usage_info(portal=None)` | `collective.quota.usage` | `UsageInfo(total, soft, hard, percent, level)`; `level` is `ok`, `warning` or `exceeded` |
| `get_settings()` | `collective.quota.settings` | Effective settings: `soft_bytes`, `hard_bytes`, `policy`, `max_file_bytes`, plus `sources` and `locked` |
| `rebuild_usage(portal, update_metadata=True)` | `collective.quota.usage` | Number of items re-cataloged |
| `get_blob_sizes(obj)` | `collective.quota.indexers.blob_size` | `{field name: bytes}` for one item |
| `evaluate_upload(total, old, new, settings)`, `evaluate_add(total, settings)` | `collective.quota.policy` | A `Decision` with `allowed`, `reason` and a translated `message` |
| `guard_suspended()` | `collective.quota.guard` | Context manager, see below |

```python
from collective.quota.usage import get_usage_info

info = get_usage_info()
if info.level == "exceeded":
    ...
```

### Respecting the quota in scripts

Forms and REST requests check the policy before saving. Code that creates or
changes content directly (`plone.api`, imports, migrations) is checked when the
transaction commits: if it crossed the hard limit, `transaction.commit()` raises
`collective.quota.guard.QuotaCommitAborted` and nothing is saved. Over HTTP the
same error is a `400` page that says "The change was cancelled: …".

Trusted administrator code can exempt its own changes:

```python
from collective.quota.guard import guard_suspended

import transaction

with guard_suspended():
    ...  # changes made here are not checked, not even by the upload validators
transaction.commit()
```

Each use is logged. Prefer raising the hard limit temporarily (for example with
`COLLECTIVE_QUOTA_HARD_LIMIT_MB`) when you can. `guard_suspended()` is a Python
API only: no view or REST endpoint reaches it.

### How the index works

`blob_size` is a `BlobSizeIndex`, a `FieldIndex` subclass, plus a metadata column of
the same name. The indexer sums the stored size of every file and image field of an
item; items without such fields are not indexed. The index keeps a `BTrees.Length`
counter that changes with every index and unindex call. That is why reading the total
is constant time, and why "Clear and rebuild" in the ZMI also fixes the total. You
can query and sort on it like any field index:

```python
from plone import api

biggest = api.content.find(
    blob_size={"query": 1, "range": "min"},
    sort_on="blob_size",
    sort_order="descending",
    sort_limit=10,
)[:10]
```

### Upgrade steps

The profile version is `1000`. `collective.quota.upgrades.utils` has
`run_import_step(setup_tool, "catalog")` and `rebuild_usage(setup_tool)` for future
upgrade steps; the module docstring describes the convention.

## Uninstall 🧹

Deactivating the add-on in **Site Setup → Add-ons** removes the index and its
metadata column, the settings, the control panel, the user-menu entry and the banner.
Content is not touched. Installing again measures everything anew.

## Contribute 🤝

- [Issue tracker](https://github.com/collective/collective-quota/issues)
- [Source code](https://github.com/collective/collective-quota/)
- [Developer setup](https://github.com/collective/collective-quota/#readme)

### Prerequisites ✅

-   An [operating system](https://6.docs.plone.org/install/create-project-cookieplone.html#prerequisites-for-installation) that runs all the requirements mentioned.
-   [uv](https://6.docs.plone.org/install/create-project-cookieplone.html#uv)
-   [Make](https://6.docs.plone.org/install/create-project-cookieplone.html#make)
-   [Git](https://6.docs.plone.org/install/create-project-cookieplone.html#git)

### Installation for development 🛠️

1.  Clone this repository.

    ```shell
    git clone git@github.com:collective/collective-quota.git
    cd collective-quota/backend
    ```

2.  Install this code base.

    ```shell
    make install
    ```

3.  Create a site with example content, then start Plone at http://localhost:8080/.

    ```shell
    make create-site
    make start
    ```

4.  Run the tests and the linters. Coverage must stay at 100 %.

    ```shell
    make test-coverage
    make lint
    ```

## License 📜

The project is licensed under GPLv2.

## Credits and acknowledgements 🙏

Generated using [Cookieplone (2.0.2)](https://github.com/plone/cookieplone) and [cookieplone-templates (19d0792)](https://github.com/plone/cookieplone-templates/commit/19d07923b43f38bc80271aab3d4ea54388fa9d23) on 2026-10-15 16:57:51.018171. A special thanks to all contributors and supporters!
