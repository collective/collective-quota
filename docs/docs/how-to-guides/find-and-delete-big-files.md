---
myst:
  html_meta:
    "description": "Use the Disk usage page to find the biggest items and delete several at once."
    "property=og:description": "Use the Disk usage page to find the biggest items and delete several at once."
    "property=og:title": "Find and delete the biggest files"
    "keywords": "Plone, Collective Quota, disk usage, delete, link integrity"
---

# Find and delete the biggest files

You need a role with the **collective.quota: View Disk Usage** permission: Editor,
Contributor, Reviewer, Site Administrator or Manager by default.

1.  Open the user menu (your name) and click **Disk usage**. When the site is near or
    over its quota, the **Review disk usage** button of the warning banner leads to
    the same page.
2.  The table lists the biggest items you can see, biggest first. Use **Number of
    items** and **Show** to see 10, 25, 50 or 100 of them.
3.  To replace a file with a smaller one, click **Edit** and upload the new file.
    That always works, even over the hard limit.
4.  To delete, tick the items (or the box in the header to select all) and click
    **Delete selected**, or click **Delete** on a single row.
5.  The confirmation page lists the items and their total size. If other content
    links to them, Plone's link-integrity warning lists the pages that would have
    broken links, with links to edit them first.
6.  Click **Delete**. You are back on the disk usage page, with a message saying how
    much space was freed.

Items you are not allowed to delete have no checkbox. Items locked by someone else
who is editing them are skipped, and a message says so.
