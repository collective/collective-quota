---
myst:
  html_meta:
    "description": "From installing Collective Quota to cleaning up the biggest files on an existing site."
    "property=og:description": "From installing Collective Quota to cleaning up the biggest files on an existing site."
    "property=og:title": "Set up a quota on an existing site"
    "keywords": "Plone, Collective Quota, tutorial"
---

# Set up a quota on an existing site

In this tutorial you add Collective Quota to a site that already has content, choose
limits that fit it, see what editors see, and free some space.

You need a Plone 6.1 or 6.2 Classic UI project and the Manager role.

## Install the add-on

1.  Add `collective.quota` to the dependencies of your backend package and run:

    ```shell
    make install
    make start
    ```

2.  In **Site Setup → Add-ons**, activate **Collective Quota**. Installing measures
    every existing file and image, which takes a moment on big sites.

## Look at the current usage

1.  Open **Site Setup → Quota**. **Current usage** shows the total. Write it down.
2.  Open your user menu and select **Disk usage**. The biggest items of the site are
    listed, biggest first.

## Choose the limits

Say the site uses 3.4 GB and you want to allow 5 GB.

1.  In the Quota control panel, set **Soft limit (MB)** to `4096` and **Hard limit
    (MB)** to `5120`.
2.  Keep the policy **Block new items and any upload that adds bytes**, or choose
    **Allow new items, block uploads that add bytes** if editors should still be able
    to add pages.
3.  Select **Save**. Nothing changes for editors yet: the site is under both limits.

## See the warning

To see what editors will see, lower the soft limit below the current usage, for
example to `3000`, and save. Every page now shows a yellow banner that starts with
**Disk usage warning: this site uses 3.4 GB of 5.0 GB (68%)**. Log in as an editor in another
browser: they see it too. Anonymous visitors do not.

Set the hard limit below the current usage as well, for example to `3200`, and save.
The banner turns red, and as an editor:

- uploading a new file is refused, with the reason under the file field;
- with the policy **Block new items and any upload that adds bytes**, adding a page
  is refused too;
- replacing a file with a smaller one still works.

## Free some space

1.  Select **Review disk usage** in the banner.
2.  Tick two big files you do not need and select **Delete selected**.
3.  If a page links to one of them, the confirmation page says so. Edit that page
    first, or delete anyway.
4.  Select **Delete**. The message says how much space was freed, and the summary at
    the top shows the new total.

## Put the real limits back

Set the soft and hard limits back to `4096` and `5120` and save. The banner goes away.

If the quota should not be changed from the site, ask your hosting operator to set
`COLLECTIVE_QUOTA_HARD_LIMIT_MB` and `COLLECTIVE_QUOTA_LOCK_SETTINGS`; see
{doc}`../how-to-guides/configure-with-environment-variables`.
