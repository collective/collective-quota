---
myst:
  html_meta:
    "description": "Change which roles can see the Disk usage page and the warning banner."
    "property=og:description": "Change which roles can see the Disk usage page and the warning banner."
    "property=og:title": "Grant editors access to disk usage"
    "keywords": "Plone, Collective Quota, permissions, roles"
---

# Grant editors access to disk usage

The **collective.quota: View Disk Usage** permission controls the Disk usage page,
the user-menu entry and the warning banner. By default, Manager, Site Administrator,
Editor, Contributor and Reviewer have it.

## In the Zope Management Interface

1.  Open the site in the ZMI and go to its **Security** tab.
2.  Find **collective.quota: View Disk Usage**.
3.  Tick the roles that should have it, keep **Acquire** ticked, and save.

To grant it in one folder only, do the same on that folder's **Security** tab; the
page itself lives on the site root, so the user still needs it there to open it.

## In a policy package

Add the permission to the `rolemap.xml` of your policy package:

```xml
<rolemap>
  <permissions>
    <permission name="collective.quota: View Disk Usage" acquire="True">
      <role name="Manager" />
      <role name="Site Administrator" />
      <role name="Editor" />
      <role name="Contributor" />
      <role name="Reviewer" />
      <role name="Member" />
    </permission>
  </permissions>
</rolemap>
```

Anonymous visitors never see usage information, even if the permission is given to
`Anonymous` by mistake. Changing who may edit the settings works the same way with
**collective.quota: Manage Quota Settings**.
