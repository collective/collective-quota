---
myst:
  html_meta:
    "description": "Set the soft limit, the hard limit and the policy in the Quota control panel."
    "property=og:description": "Set the soft limit, the hard limit and the policy in the Quota control panel."
    "property=og:title": "Configure limits"
    "keywords": "Plone, Collective Quota, control panel, limits"
---

# Configure limits

You need the **Manager** or **Site Administrator** role.

1.  Open **Site Setup**, then **Quota** under **Add-on Configuration**
    (`@@quota-controlpanel`).
2.  Read **Current usage** at the top: it shows how much the site uses now.
3.  Enter a **Soft limit (MB)**, for example 80 % of what you want to allow. Editors
    will see a yellow banner from that point on.
4.  Enter a **Hard limit (MB)**. It must be at least the soft limit.
5.  Choose the **Policy when the hard limit is reached**. See
    {doc}`../concepts/limits-and-policies` for what each one does.
6.  If you chose **Allow uploads up to a maximum file size**, set **Maximum file size
    over the limit (MB)** to a value greater than 0.
7.  Select **Save**.

The table **Where the values come from** shows, for every setting, whether it comes
from this control panel, an environment variable or the default. To go back to the
environment variables or the defaults, select **Reset to defaults**.

## Over the REST API

The same settings are at `@controlpanels/collective-quota`:

```shell
curl -i -X PATCH http://localhost:8080/Plone/++api++/@controlpanels/collective-quota \
  -u admin:admin -H "Content-Type: application/json" \
  -d '{"soft_limit_mb": 4000, "hard_limit_mb": 5000, "over_limit_policy": "block_files"}'
```

A `GET` returns the stored values in `data`, and the values in use, their sources and
the locked fields in `effective`, `sources` and `locked`.
