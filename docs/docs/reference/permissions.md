---
myst:
  html_meta:
    "description": "Permissions defined by Collective Quota."
    "property=og:description": "Permissions defined by Collective Quota."
    "property=og:title": "Permissions"
    "keywords": "Plone, Collective Quota, permissions"
---

# Permissions

| Permission (title) | Id | Default roles | Protects |
|---|---|---|---|
| `collective.quota: Manage Quota Settings` | `collective.quota.ManageSettings` | Manager, Site Administrator | `@@quota-controlpanel`, `@controlpanels/collective-quota`, `@@quota-rebuild` |
| `collective.quota: View Disk Usage` | `collective.quota.ViewDiskUsage` | Manager, Site Administrator, Editor, Contributor, Reviewer | `@@quota-usage`, `@@quota-delete`, the warning banner, the "Disk usage" user action |

`@@quota-delete` also checks Plone's `Delete objects` permission on every item and
requires a valid CSRF token to delete. Anonymous users never see the banner, whatever
the permission settings.
