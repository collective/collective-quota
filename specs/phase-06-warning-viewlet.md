# Phase 6 — Soft/hard limit warning viewlet for editors

Status: Done
Depends on: Phase 2, Phase 3, Phase 5 (button target)
Last updated: 2026-10-16

## Goal

Editors (anyone with `View Disk Usage`) see a banner at the top of every page when
total usage is at or above the soft limit, and a stronger one when the hard limit is
reached, with a button that opens `@@quota-usage`. Anonymous visitors and members
without the permission never see it. The check is O(1).

## Scope

In: viewlet class, template, ZCML registration, `viewlets.xml` ordering, tests.

Out: Volto banner (phase 9).

## Design

### Placement

Manager: `plone.app.layout.viewlets.interfaces.IGlobalStatusMessage`
(`plone.globalstatusmessage`). This is where Plone renders status messages and the
`plone.app.dexterity.defaultpagewarning` editor-only warning, i.e. "on top of the
content area, below the navigation" in every Classic theme. `profiles/default/viewlets.xml`:

```xml
<object>
  <order manager="plone.globalstatusmessage" skinname="*">
    <viewlet name="plone.globalstatusmessage" insert-before="*" />
    <viewlet name="collective.quota.warning" insert-after="plone.globalstatusmessage" />
  </order>
</object>
```

Plone stores no order for this manager, and `OrderedViewletManager` puts ordered
viewlets *before* unordered ones. Ordering only ours (`insert-after="*"`) would put the
banner above the status messages, so the profile pins `plone.globalstatusmessage`
first and ours right after it. `defaultpagewarning` stays unordered and comes after.

Uninstall `viewlets.xml` removes the entry (`<viewlet name="collective.quota.warning" remove="True" />`
inside the same `order` element).

### Viewlet — `browser/viewlets.py` + `templates/warning_viewlet.pt`

```xml
<browser:viewlet
    name="collective.quota.warning"
    manager="plone.app.layout.viewlets.interfaces.IGlobalStatusMessage"
    class=".viewlets.QuotaWarningViewlet"
    template="templates/warning_viewlet.pt"
    layer="..interfaces.IBrowserLayer"
    permission="collective.quota.ViewDiskUsage"
    />
```

```python
class QuotaWarningViewlet(ViewletBase):
    def update(self):
        super().update()
        self.info = get_usage_info()
        self.settings = get_settings()

    @property
    def available(self) -> bool:
        if self.portal_state.anonymous():
            return False
        if getattr(self.view, "__name__", None) in ("quota-usage", "quota-controlpanel"):
            return False       # those pages already show the summary
        return self.info.level in ("warning", "exceeded")

    @property
    def css_class(self) -> str:   # "alert-warning" | "alert-danger"
    @property
    def message(self):            # translated Message with mapping used/limit/percent
    @property
    def usage_url(self) -> str:   # portal_url + "/@@quota-usage"

    def render(self):
        return self.index() if self.available else ""
```

Messages (domain `collective.quota`). Already implemented in phase 5 as
`collective.quota.browser.summary.level_message(info, settings)` (plus
`ALERT_CLASSES`), which `@@quota-usage` renders in its alert; the viewlet calls it too:

| level | text |
|---|---|
| `warning` | "Disk usage warning: this site uses ${used} of ${limit} (${percent}%). Please review large files before the limit is reached." (`limit` = hard if set, else soft; `percent` of that) |
| `exceeded` | "Disk quota exceeded: this site uses ${used} of ${limit}. ${policy_hint}" |

`policy_hint` per policy: `block_all` → "New content and uploads are blocked until
files are removed."; `block_files` → "Uploads are blocked until files are removed.";
`limit_file_size` → "Only files up to ${max_size} can be uploaded until files are
removed."; `allow` → "Uploads are still allowed.".

Template:

```html
<div class="alert d-flex align-items-center justify-content-between gap-3 mb-3"
     tal:attributes="class string:alert ${view/css_class} ..." role="alert" id="collective-quota-warning">
  <span tal:content="view/message" />
  <a class="btn btn-sm btn-outline-dark text-nowrap" tal:attributes="href view/usage_url"
     i18n:translate="">Review disk usage</a>
</div>
```

### Why both `permission` and the anonymous check

The ZCML permission hides the viewlet from users without `View Disk Usage`. The
explicit `anonymous()` check is defence in depth in case a site maps the permission to
`Anonymous` by mistake; the architecture doc requires that anonymous visitors never see
usage information.

## Files

Create:
- `backend/src/collective/quota/browser/viewlets.py`
- `backend/src/collective/quota/browser/templates/warning_viewlet.pt`
- `backend/src/collective/quota/profiles/default/viewlets.xml`
- `backend/src/collective/quota/profiles/uninstall/viewlets.xml`
- `backend/tests/test_viewlet.py`

Modify:
- `backend/src/collective/quota/browser/configure.zcml`

## Tasks

- [x] Viewlet class with `available`, `css_class`, `message`, `usage_url`
- [x] Template with Bootstrap alert and button
- [x] ZCML registration (manager, layer, permission)
- [x] `viewlets.xml` default + uninstall
- [x] Manual check: soft 1 MB, hard 2 MB; upload 1.5 MB → yellow banner on every page as Editor, none as anonymous; upload past 2 MB → red banner with policy hint; banner absent on `@@quota-usage` itself
- [x] `make i18n`; `make lint`; coverage 100 %

## Tests

- [x] `test_viewlet.py::test_hidden_for_anonymous_even_over_limit`
- [x] `test_viewlet.py::test_hidden_for_member_without_permission`
- [x] `test_viewlet.py::test_hidden_below_soft_limit`
- [x] `test_viewlet.py::test_hidden_when_limits_disabled`
- [x] `test_viewlet.py::test_warning_between_soft_and_hard` — class `alert-warning`, message contains human sizes and percent
- [x] `test_viewlet.py::test_danger_at_hard_limit_with_policy_hint` — one case per policy
- [x] `test_viewlet.py::test_button_links_to_usage_view`
- [x] `test_viewlet.py::test_hidden_on_usage_and_controlpanel_views`
- [x] `test_viewlet.py::test_rendered_in_page_for_editor` — functional browser: Editor loads the site root; `#collective-quota-warning` present; anonymous: absent
- [x] `test_viewlet.py::test_order_after_status_messages` — viewlet appears after `plone.globalstatusmessage` in the manager order (`plone.app.viewletmanager` storage)

## Acceptance criteria

- Banner visibility matches the matrix above for every default role.
- Rendering the banner adds no catalog queries beyond the O(1) total read (verify with
  a query counter or by asserting `get_index().total` is the only index access).

## Notes / risks

- Themes that do not render `plone.globalstatusmessage` (rare, custom `main_template`)
  will not show the banner; document that the viewlet can be re-registered to
  `plone.abovecontent` via `viewlets.xml` in the theme.
- If Plone ever ships an order for this manager, the `insert-before`/`insert-after`
  pair still leaves the banner right below the status messages.

Implementation notes (2026-10-16):

- **Ordering**: see the `viewlets.xml` note above; `TestRegistration` and the browser
  test check that the banner comes after `#global_statusmessage`.
- **Summary pages** are detected by the view's `__name__`, not `request.steps`, which
  also covers `@@` and plain traversal and any URL suffix.
- `update()` passes the portal to `get_usage_info()`. The O(1) test patches the
  catalog search methods and asserts they are never called.
- The viewlet class is a ZCML-made subclass that carries the template, so tests look
  it up as an `IViewlet` adapter instead of instantiating `QuotaWarningViewlet`.
- Manual check on a running instance (port 8091, temporary site deleted afterwards,
  1.5 MB used, soft 1 MB, hard 2 MB, policy `allow`):
  - Editor: the yellow banner "Disk usage warning: this site uses 1.5 MB of 2.0 MB
    (75%). …" showed on the site root, a Document, a Folder, a File view, an edit
    form and `folder_contents`. It came after the status messages and before the
    content, and its button links to `@@quota-usage`.
  - No banner for anonymous, for a Member, or on `@@quota-usage` (Editor) and
    `@@quota-controlpanel` (admin).
  - After a 1 MB REST upload (201), the Editor saw the red banner "Disk quota
    exceeded: this site uses 2.5 MB of 2.0 MB. Uploads are still allowed."
