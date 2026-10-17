---
myst:
  html_meta:
    "description": "REST API of Collective Quota: @quota-usage, @quota-rebuild and the quota expansion element."
    "property=og:description": "REST API of Collective Quota: @quota-usage, @quota-rebuild and the quota expansion element."
    "property=og:title": "REST API"
    "keywords": "Plone, Collective Quota, REST API, plone.restapi, Volto"
---

# REST API

Collective Quota adds two services and one expansion element to `plone.restapi`. They
exist only while the add-on is installed, and they give any REST client (Volto first)
the same data the Classic views render. Anonymous users never get quota data.

| Endpoint | Context | Permission |
|---|---|---|
| `GET @quota-usage?limit=10\|25\|50\|100` | Site root | View Disk Usage |
| `POST @quota-rebuild` | Site root | Manage Quota Settings |
| `?expand=quota` on any content `GET` | Any content and the site root | View Disk Usage, checked on the site root |
| `GET`/`PATCH @controlpanels/collective-quota` | Site root | Manage Quota Settings (see {doc}`settings`) |

Without the permission, `plone.restapi` answers `401 Unauthorized`, for anonymous and
authenticated users alike.

Sizes are always bytes, plus a `*_human` string formatted like Plone does
(`plone.base.utils.human_readable_size`). Names follow `plone.restapi`: `@id`, `UID`,
`@type`, and `modified` in ISO 8601.

## `GET @quota-usage`

```shell
curl -u admin:secret -H "Accept: application/json" \
  "http://localhost:8080/Plone/@quota-usage?limit=10"
```

```json
{
  "@id": "http://localhost:8080/Plone/@quota-usage",
  "total": 3650722201,
  "total_human": "3.4 GB",
  "soft": 4294967296,
  "soft_human": "4.0 GB",
  "hard": 5368709120,
  "hard_human": "5.0 GB",
  "percent": 68,
  "level": "ok",
  "limits_configured": true,
  "message": null,
  "policy": "block_all",
  "policy_title": "Block new items and any upload that adds bytes",
  "policy_hint": "New content and uploads are blocked until files are removed.",
  "can_manage": true,
  "controlpanel": "http://localhost:8080/Plone/@controlpanels/collective-quota",
  "limit": 10,
  "limits": [10, 25, 50, 100],
  "items": [
    {
      "@id": "http://localhost:8080/Plone/reports/annual-report",
      "UID": "afb0a2ccbeb240f9baa9f0e64feed7e5",
      "title": "Annual report",
      "@type": "File",
      "type_title": "File",
      "parent": {"@id": "http://localhost:8080/Plone/reports", "title": "Reports"},
      "blob_size": 2097152,
      "blob_size_human": "2.0 MB",
      "modified": "2026-10-16T14:02:11+00:00",
      "can_delete": true
    }
  ]
}
```

### Summary fields

| Field | Type | Meaning |
|---|---|---|
| `@id` | URL | This service |
| `total`, `total_human` | int, string | Bytes used by all files and images of the site |
| `soft`, `soft_human` | int, string or `null` | Soft limit; `0` and `null` when disabled |
| `hard`, `hard_human` | int, string or `null` | Hard limit; `0` and `null` when disabled |
| `percent` | int or `null` | Percentage of the hard limit; `null` without a hard limit |
| `level` | `ok`, `warning`, `exceeded` | The only value clients should branch on |
| `limits_configured` | `bool` | `false` when neither limit is set: show no limit-related UI |
| `message` | string or `null` | Translated warning text; `null` when `level` is `ok` |
| `policy`, `policy_title` | token, string | Policy in effect (present even when the hard limit is disabled) |
| `policy_hint` | string or `null` | Translated sentence on what is blocked; `null` without a hard limit |
| `can_manage` | `bool` | The user holds Manage Quota Settings |
| `controlpanel` | URL | REST control panel; present only when `can_manage` is true |

### Listing fields

| Field | Meaning |
|---|---|
| `limit` | Number of items asked for: `limit` from the query string if it is one of `limits`, else `25` |
| `limits` | Accepted values of `limit` |
| `items` | The biggest items the user can see, biggest first |
| `items[].@id`, `UID`, `@type`, `title` | As in `plone.restapi` summaries |
| `items[].type_title` | Translated content type title |
| `items[].parent` | `@id` and `title` of the container |
| `items[].blob_size`, `blob_size_human` | Size of the item's files and images |
| `items[].modified` | ISO 8601 |
| `items[].can_delete` | The user holds Delete objects on the item |

The listing is a catalog search with the user's permissions, so it lists only the
items the user may access.

## `POST @quota-rebuild`

Re-catalogs every item for `blob_size` and recomputes the total, like the
"Rebuild usage data" button. No body is needed and none is read.

```shell
curl -X POST -u admin:secret -H "Accept: application/json" \
  http://localhost:8080/Plone/@quota-rebuild
```

```json
{"items": 1234, "total": 3650722201, "total_human": "3.4 GB"}
```

## Expansion element `quota`

Every content response gets `@components.quota` for users holding View Disk Usage on
the site root:

```json
"@components": {
  "quota": {"@id": "http://localhost:8080/Plone/@quota-usage"}
}
```

With `?expand=quota` (alone or with other elements, such as
`?expand=navroot,quota`), it carries the summary fields of `@quota-usage` (everything
except `limit`, `limits` and `items`). Reading it costs one counter read and one
permission check; no content is loaded.

For anonymous users and users without the permission, the `quota` key is absent with
or without `expand`, so their responses are the same as on a site without the add-on.

A user who holds View Disk Usage only through a local role on a folder gets no
`quota` key, because the permission is checked on the site root.

## Deleting items

There is no quota-specific endpoint. Use `plone.restapi`, as Volto's folder contents does:

1. `GET @linkintegrity?uids=<uid>&uids=<uid>` to show the links that would break.
2. `DELETE <item @id>` for each selected item.
3. `GET @quota-usage` again; the space freed is the difference in `total`.
