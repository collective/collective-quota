# Changelog

<!--
   You should *NOT* be adding new change log entries to this file.
   You should create a file in the news directory instead.
   For helpful instructions, please see:
   https://github.com/plone/plone.releaser/blob/master/ADD-A-NEWS-ITEM.rst
-->

<!-- towncrier release notes start -->

## 1.0.0 (2026-11-27)


### Breaking

- Drop the `plone.volto` dependency and Plone 6.0 support: the add-on targets Classic UI on Plone 6.1 and 6.2, and installs `plone.restapi`. 


### Feature

- Add Spanish translations, upgrade-step helpers and Classic example content. 
- Add the Quota control panel (`@@quota-controlpanel`, also `@controlpanels/collective-quota` over REST) with soft limit, hard limit, policy and maximum file size; every setting can come from a `COLLECTIVE_QUOTA_*` environment variable, optionally locked with `COLLECTIVE_QUOTA_LOCK_SETTINGS`. 
- Add the REST API for Volto: `GET @quota-usage` (usage summary and biggest items), `POST @quota-rebuild`, and the `quota` expansion element (`?expand=quota`). `plone.volto` is only an `acceptance` extra for the Volto acceptance server. 
- Add the `@@quota-usage` view, linked from the user menu as "Disk usage": the biggest items, and deleting several at once with Plone's link-integrity warnings. 
- Add the `blob_size` catalog index and metadata column: the size in bytes of every item's files and images, with a running site total that is read in constant time. Installing populates it for existing content. 
- Enforce the hard limit with four policies (`block_all`, `block_files`, `limit_file_size`, `allow`) in Classic forms and plone.restapi, plus a commit guard that cancels any other transaction crossing the limit; trusted scripts can use `guard_suspended()`. 
- Show editors a warning banner when the site reaches the soft limit, and a stronger one at the hard limit.
