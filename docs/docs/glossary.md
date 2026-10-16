---
myst:
  html_meta:
    "description": "Terms used in the Collective Quota documentation."
    "property=og:description": "Terms used in the Collective Quota documentation."
    "property=og:title": "Glossary"
    "keywords": "Plone, Collective Quota, glossary"
---

(glossary-label)=

# Glossary

```{glossary}
:sorted: true

blob_size
    The catalog index and metadata column holding, for each item, the sum in bytes of
    its file and image fields. See {doc}`reference/catalog-index`.

Soft limit
    The usage at which editors start to see a warning. It never blocks anything.

Hard limit
    The usage above which the {term}`policy` applies to saves.

policy
    What happens to a save that would push usage above the {term}`hard limit`:
    `block_all`, `block_files`, `limit_file_size` or `allow`.

commit guard
    A check at the end of every transaction that adds bytes or items; it cancels
    changes that crossed the {term}`hard limit` without being approved by a form or
    the REST API. See {doc}`reference/commit-guard`.

locked setting
    A setting whose environment variable is set while
    `COLLECTIVE_QUOTA_LOCK_SETTINGS` is on. The control panel and the REST API cannot
    change it.

Plone
    [Plone](https://plone.org/) is an open-source content management system that is used to create, edit, and manage digital content, like websites, intranets and custom solutions.

add-on
    An add-on in Plone extends its functionality.
    It is code that is released as a package to make it easier to install.

Markedly Structured Text
MyST
    [Markedly Structured Text (MyST)](https://myst-parser.readthedocs.io/en/latest/) is a rich and extensible flavor of Markdown, used to write this documentation.

Plone Sphinx Theme
    [Plone Sphinx Theme](https://plone-sphinx-theme.readthedocs.io/) is the Sphinx theme of this documentation.
```
