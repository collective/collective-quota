---
myst:
  html_meta:
    "description": "The registry records of Collective Quota."
    "property=og:description": "The registry records of Collective Quota."
    "property=og:title": "Settings"
    "keywords": "Plone, Collective Quota, registry, settings"
---

# Settings

Stored in the registry with the prefix `collective.quota`, schema
`collective.quota.interfaces.IQuotaSettings`. All records allow an empty value
(`None`), meaning: use the environment variable or the default.

| Record | Type | Default | Description |
|---|---|---|---|
| `collective.quota.soft_limit_mb` | integer ≥ 0 | `0` | Soft limit in MB; `0` disables it |
| `collective.quota.hard_limit_mb` | integer ≥ 0 | `0` | Hard limit in MB; `0` disables enforcement |
| `collective.quota.over_limit_policy` | choice | `block_all` | `block_all`, `block_files`, `limit_file_size` or `allow` |
| `collective.quota.max_file_size_mb` | integer ≥ 0 | `10` | Maximum file size in MB under `limit_file_size` |

Rules checked when saving from the control panel or the REST API:

- The soft limit cannot be higher than the hard limit (when both are enabled).
- `limit_file_size` needs a maximum file size greater than 0.

Each effective value is resolved in this order: a locked environment variable, the
registry record, the environment variable, the default. See
{doc}`environment-variables`.

REST: `GET`/`PATCH` `@controlpanels/collective-quota`. Besides `data` and `schema`,
the response has `effective` (values in use), `sources` (`registry`, `env`,
`env-locked` or `default` per setting) and `locked` (list of locked settings).
