---
myst:
  html_meta:
    "description": "What Collective Quota counts as disk usage, and how it keeps the total up to date."
    "property=og:description": "What Collective Quota counts as disk usage, and how it keeps the total up to date."
    "property=og:title": "How disk usage is measured"
    "keywords": "Plone, Collective Quota, disk usage, blob_size, catalog"
---

# How disk usage is measured

Collective Quota measures the bytes that editors upload: the files and images stored
in the file and image fields of content items.

## Per item

Every content type in Plone is built from a schema plus behaviors. For each item,
Collective Quota looks at every field of those schemas that holds a file or an image
(any `plone.namedfile` field: `NamedFile`, `NamedImage`, `NamedBlobFile`,
`NamedBlobImage`), and adds up the sizes that `plone.namedfile` stores with each
value. The file itself is never opened, so measuring is cheap.

The result is stored in the {term}`blob_size` catalog index and in a metadata
column of the same name. Items whose type has no file or image field are not
indexed at all. Items that have such fields but no file yet count as 0.

## Per site

The site total is the sum of `blob_size` over all cataloged items. The index keeps
it as a running counter: every time the catalog indexes, reindexes or unindexes an
item, the counter changes by the difference. Reading the total therefore costs the
same on a site with ten items as on a site with a million, and every page can show
the warning banner without slowing down.

Because every add, edit, move, copy, paste and delete in Plone goes through the
catalog, the counter cannot miss a change. Rebuilding the index (from the control
panel, or with "Clear and rebuild" in the ZMI) recomputes it from scratch.

## What is not counted

| Counted | Not counted |
|---|---|
| `File.file`, `Image.image`, the lead image, and file or image fields of custom types and behaviors | Older versions kept by the versioning machinery (CMFEditions) |
| Working copies, which are regular items | Image scales generated for thumbnails and previews |
| | Rich text, blocks and other non-file data |
| | ZODB overhead, and anything not in `portal_catalog` |

Folders do not add up their contents: each item counts on its own. So the total is
always lower than the size of `Data.fs` plus the blob storage on disk. The quota is a
policy about what editors upload, not a filesystem limit.
