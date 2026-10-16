---
myst:
  html_meta:
    "description": "Views, viewlet and actions of Collective Quota."
    "property=og:description": "Views, viewlet and actions of Collective Quota."
    "property=og:title": "Views and viewlet"
    "keywords": "Plone, Collective Quota, views, viewlet"
---

# Views and viewlet

All views are registered on the site root for the `collective.quota` browser layer,
so they exist only while the add-on is installed. Their REST counterparts are
described in {doc}`rest-api`.

| Name | Permission | Description |
|---|---|---|
| `@@quota-controlpanel` | Manage Quota Settings | Control panel: usage summary, settings, sources, "Rebuild usage data" |
| `@@quota-rebuild` | Manage Quota Settings | `POST` only, with a CSRF token: recomputes the usage data, then redirects to the control panel |
| `@@quota-usage` | View Disk Usage | The biggest items. Parameter `limit`: `10`, `25` (default), `50` or `100` |
| `@@quota-delete` | View Disk Usage | Confirmation page for `uids:list`. With `form.button.confirm` and a valid `_authenticator`, deletes the items; `form.button.cancel` goes back |

## Viewlet

`collective.quota.warning`, in the viewlet manager `plone.globalstatusmessage`, right
after the status messages. Rendered for users with View Disk Usage when the level is
`warning` (yellow, `alert-warning`) or `exceeded` (red, `alert-danger`), except on
`@@quota-usage` and `@@quota-controlpanel`. The element has the id
`collective-quota-warning` and a `data-level` attribute.

## User action

`disk-usage` in the `user` category (the user menu), after **Preferences**, pointing to
`@@quota-usage` on the site root. Requires View Disk Usage.

## Control panel entry

Configlet `collective-quota` in the "Products" group of Site Setup.

## Error page

A transaction cancelled by the {term}`commit guard` answers `400`. Browsers get a
"Disk quota exceeded" page with the message. Clients that do not accept HTML get JSON
with `error_type` (`QuotaCommitAborted`) and `message`; the REST API answers with its
usual error JSON, `type` and `message`.
