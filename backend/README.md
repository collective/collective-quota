# collective.quota

This product allows to configure a quota limit for Plone sites. It also provides a convenient view for quickly finding the biggest items in case you need to delete

## Features

TODO: List our awesome features

## Configuration

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

### Environment variables

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

### Enforcement

When a save would push total usage above the hard limit, the policy decides:

| Policy | New items without files | Uploads that add bytes | Replacing with a smaller file |
|---|---|---|---|
| `block_all` | refused | refused | allowed |
| `block_files` | allowed | refused | allowed |
| `limit_file_size` | allowed | allowed up to the maximum file size | allowed |
| `allow` | allowed | allowed (warnings only) | allowed |

Deleting content and replacing a file with a smaller one always work, so editors
can clean up. Classic forms show the error on the file field (or at the top of the
add form); REST clients get `400 Bad Request` with the message.

A commit guard also checks every transaction that changes stored file sizes or
adds items, whatever the code path (copy/paste, `plone.api`, imports, scripts). If
the change crosses the hard limit without a form or REST validation having approved
it, the transaction is aborted with "The change was cancelled: …" (`400` over HTTP,
an exception from `transaction.commit()` in scripts).

Trusted administrator code can exempt its own changes:

```python
from collective.quota.guard import guard_suspended

with guard_suspended():
    ...  # changes made here are not checked by the guard
transaction.commit()
```

Each use is logged. Prefer raising the hard limit temporarily (for example with
`COLLECTIVE_QUOTA_HARD_LIMIT_MB`) when possible. `guard_suspended()` is not reachable
from the web.

### Disk usage view

"Disk usage" in the user menu opens `@@quota-usage` on the site root. Managers, Site
Administrators, Editors, Contributors and Reviewers can open it (permission
`collective.quota: View Disk Usage`); Members and anonymous visitors cannot.

The page shows the current usage, the limits and the policy, then the 10, 25, 50 or
100 biggest items the user can see, with links to view or edit each one. Tick
several items and click "Delete selected" (or use an item's "Delete" link): a
confirmation page lists them with their total size and Plone's usual link-integrity
warnings. Items you may not delete, or that another user has locked, are skipped and
reported. Deleting always works, even over the hard limit.

## Installation

Install collective.quota with uv.

```shell
uv add collective.quota
```

Create the Plone site.

```shell
make create-site
```

## Contribute

- [Issue tracker](https://github.com/collective/collective-quota/issues)
- [Source code](https://github.com/collective/collective-quota/)

### Prerequisites ✅

-   An [operating system](https://6.docs.plone.org/install/create-project-cookieplone.html#prerequisites-for-installation) that runs all the requirements mentioned.
-   [uv](https://6.docs.plone.org/install/create-project-cookieplone.html#uv)
-   [Make](https://6.docs.plone.org/install/create-project-cookieplone.html#make)
-   [Git](https://6.docs.plone.org/install/create-project-cookieplone.html#git)
-   [Docker](https://docs.docker.com/get-started/get-docker/) (optional)

### Installation 🔧

1.  Clone this repository.

    ```shell
    git clone git@github.com:collective/collective-quota.git
    cd collective-quota/backend
    ```

2.  Install this code base.

    ```shell
    make install
    ```


### Add features using `plonecli` or `bobtemplates.plone`

This package provides markers as strings (`<!-- extra stuff goes here -->`) that are compatible with [`plonecli`](https://github.com/plone/plonecli) and [`bobtemplates.plone`](https://github.com/plone/bobtemplates.plone).
These markers act as hooks to add all kinds of features through subtemplates, including behaviors, control panels, upgrade steps, or other subtemplates from `bobtemplates.plone`.
`plonecli` is a command line client for `bobtemplates.plone`, adding autocompletion and other features.

To add a feature as a subtemplate to your package, use the following command pattern.

```shell
make add <template_name>
```

For example, you can add a content type to your package with the following command.

```shell
make add content_type
```

You can add a behavior with the following command.

```shell
make add behavior
```

```{seealso}
You can check the list of available subtemplates in the [`bobtemplates.plone` `README.md` file](https://github.com/plone/bobtemplates.plone/?tab=readme-ov-file#provided-subtemplates).
See also the documentation of [Mockup and Patternslib](https://6.docs.plone.org/classic-ui/mockup.html) for how to build the UI toolkit for Classic UI.
```

## License

The project is licensed under GPLv2.

## Credits and acknowledgements 🙏

Generated using [Cookieplone (2.0.2)](https://github.com/plone/cookieplone) and [cookieplone-templates (19d0792)](https://github.com/plone/cookieplone-templates/commit/19d07923b43f38bc80271aab3d4ea54388fa9d23) on 2026-10-15 16:57:51.018171. A special thanks to all contributors and supporters!
