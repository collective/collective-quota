---
myst:
  html_meta:
    "description": "Environment variables read by Collective Quota."
    "property=og:description": "Environment variables read by Collective Quota."
    "property=og:title": "Environment variables"
    "keywords": "Plone, Collective Quota, environment variables"
---

# Environment variables

Read from the environment of the Zope process on every request, so a restart is
enough to apply a change.

| Variable | Setting | Accepted values |
|---|---|---|
| `COLLECTIVE_QUOTA_SOFT_LIMIT_MB` | Soft limit | integer ≥ 0 |
| `COLLECTIVE_QUOTA_HARD_LIMIT_MB` | Hard limit | integer ≥ 0 |
| `COLLECTIVE_QUOTA_OVER_LIMIT_POLICY` | Policy | `block_all`, `block_files`, `limit_file_size`, `allow` |
| `COLLECTIVE_QUOTA_MAX_FILE_SIZE_MB` | Maximum file size | integer ≥ 0 |
| `COLLECTIVE_QUOTA_LOCK_SETTINGS` | Lock flag | `1`, `true`, `yes`, `on` (any case) lock; anything else does not |

Resolution order for each setting:

1. If `COLLECTIVE_QUOTA_LOCK_SETTINGS` is on and the variable is set: the variable.
   The setting is read-only in the control panel and over REST.
2. The value saved in the control panel.
3. The variable.
4. The default ({doc}`settings`).

Empty values are ignored. Invalid values are logged once as a warning and ignored.
