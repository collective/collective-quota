# Phase 5 — `@@quota-usage` biggest-items view, multi-delete with link integrity, user-menu entry

Status: Done
Depends on: Phase 2, Phase 3
Last updated: 2026-10-16

## Goal

Editors open "Disk usage" from the user menu, see the current usage and the N biggest
items (N ∈ 10/25/50/100), jump to any item to edit or replace its file, or select
several and delete them in one go with the same link-integrity confirmation Plone shows
elsewhere.

## Scope

In: `@@quota-usage` view + template, `@@quota-delete` two-step view + template, user
action in `actions.xml`, tests.

Out: viewlet (phase 6), REST listing endpoint (phase 8).

## Design

### `@@quota-usage` — `browser/usage.py` + `templates/usage.pt`

Registration: `for="plone.base.interfaces.IPloneSiteRoot"`, `layer=IBrowserLayer`,
`permission="collective.quota.ViewDiskUsage"`.

```python
LIMITS = (10, 25, 50, 100)
DEFAULT_LIMIT = 25


class DiskUsageView(BrowserView):
    def limit(self) -> int:               # from request.form["limit"], validated against LIMITS
    def usage(self) -> UsageInfo:         # get_usage_info()
    def settings(self) -> QuotaSettings
    def policy_title(self) -> str         # vocabulary term title
    def items(self) -> list[dict]:
        brains = catalog(
            blob_size={"query": 1, "range": "min"},
            sort_on="blob_size", sort_order="descending", sort_limit=limit,
        )[:limit]
        # per brain: uid, title (pretty_title_or_id), url, edit_url (url + "/edit"),
        #   portal_type, type_title (fti.Title()), parent_url, parent_title,
        #   size (metadata; fallback index.getEntryForObject(rid, 0) when Missing),
        #   size_human, modified (toLocalizedTime),
        #   can_delete (api.user.has_permission("Delete objects", obj=brain._unrestrictedGetObject()))
    def can_manage(self) -> bool          # ManageSettings → show control panel link
```

`summary()` and `alert()` come from `browser/summary.py` (`usage_summary`,
`level_message`, `ALERT_CLASSES`), which the control panel's usage card also uses and
the phase 6 viewlet reuses for its text.

Catalog search is **restricted** (`catalog(...)`, not `unrestrictedSearchResults`) so
users only see what they may view. Plone indexes `allowedRolesAndUsers` from
"Access contents information", not "View", so a listed item can still refuse
`brain.getObject()`; the view loads objects with `brain._unrestrictedGetObject()` and
checks permissions on them.

Template structure (Plone 6 Classic / Bootstrap 5):

```
h1 "Disk usage"
.card summary
   Total: 3.4 GB of 5 GB (68%)   [progress bar colored by level]
   Soft limit: 4 GB · Hard limit: 5 GB · Policy: <title>
   [Quota settings] (if can_manage)  [Rebuild usage data] (if can_manage; POST form)
.alert (warning/danger) when level != ok, same text as the viewlet
form#quota-usage-form method="post" action="@@quota-delete"
   <authenticator/>
   select name="limit" (10/25/50/100) + button "Show"  (GET to @@quota-usage; separate small form)
   table.table.table-striped
     th: [select all checkbox] | Title | Type | Location | Size | Modified | Actions
     tr per item: checkbox name="uids:list" value=uid (disabled + tooltip when not can_delete)
                  Title link → url | type_title | parent link | size_human (title="N bytes") | modified |
                  "Edit" (url/edit) · "Delete" (link to @@quota-delete?uids:list=uid)
   button.btn.btn-danger "Delete selected" (inline JS disables it until a checkbox is ticked; it stays usable without JS)
p.text-muted "Sizes include only uploaded files and images. Showing the N largest items you can see."
```

"Select all" uses a minimal inline script (or Patternslib `pat-checklist`; choose
whichever is available in the target Plone and keep it dependency-free).

### `@@quota-delete` — `browser/delete.py` + `templates/delete_confirmation.pt`

Registration: same context/layer, `permission="collective.quota.ViewDiskUsage"`.

```python
class QuotaDeleteView(BrowserView):
    def __call__(self):
        form = self.request.form
        if "form.button.cancel" in form:
            return self._redirect()
        uids = form.get("uids", [])
        if isinstance(uids, str): uids = [uids]
        if not uids:
            IStatusMessage(self.request).add(_("No items selected."), "warning")
            return self._redirect()
        self.items, self.skipped = self._resolve(uids)   # restricted catalog(UID=uids); split on Delete objects
        if "form.button.confirm" in form:
            CheckAuthenticator(self.request)              # plone.protect; raises Forbidden on bad token
            return self._delete()
        return self.index()                               # confirmation page

    def breaches_html(self) -> str:
        info = getMultiAdapter((self.context, self.request), name="delete_confirmation_info")
        if not info.linkintegrity_enabled:
            return ""
        info.breaches = info.get_breaches([item["obj"] for item in self.items])
        if not info.breaches and not info.breach_count:
            return ""
        return info.template()

    def _delete(self):
        deletable = []
        for item in self.items:
            obj = item["obj"]
            lock_info = obj.restrictedTraverse("@@plone_lock_info", None)
            if lock_info is not None and lock_info.is_locked():
                if lock_info.is_locked_for_current_user():      # locked by someone else
                    self.skipped.append({**item, "reason": _("locked by another user")})
                    continue
                ILockable(obj).unlock()
            deletable.append(obj)
        before = get_total_usage()
        api.content.delete(objects=deletable, check_linkintegrity=False)
        freed = before - get_total_usage()          # includes the contents of folders
        IStatusMessage(self.request).add(_("Deleted ${count} items, freeing ${size}.", mapping=...), "info")
        for s in self.skipped: IStatusMessage(...).add(_("Skipped ${title}: ${reason}"), "warning")
        return self._redirect()
```

Link integrity: `@@delete_confirmation_info` is the stock `plone.app.linkintegrity`
view. Its template renders the same HTML snippet folder contents and the single-item
`delete_confirmation` show (list of items that link to the selection, plus folder
content counts). Calling the view returns `None` when link integrity is disabled, but
otherwise always renders wrapper markup, even without breaches, so `breaches_html`
calls `get_breaches()` itself and only renders the template when there are breaches
or non-empty folders. The confirmation page always renders (standard Plone
behaviour: deletion always confirms), with the snippet inside a `.alert.alert-warning`
when non-empty. Because the user has seen the warning, the actual delete uses
`check_linkintegrity=False`; `plone.app.linkintegrity`'s own event handlers still run
and update relations.

Confirmation template:

```
h1 "Delete selected items"
p "Do you really want to delete the following N items (X in total)?"
table: Title (link) | Type | Size
[breaches_html block when not empty]
[skipped list when not empty: "The following items will not be deleted: ... (no permission)"]
["None of the selected items exist any more." when nothing resolved]
form method="post" action="@@quota-delete"
   hidden uids:list × N, <authenticator/>
   button name="form.button.confirm" class="btn btn-danger" "Delete"   (only when N > 0)
   button name="form.button.cancel" class="btn btn-secondary" "Cancel"
```

Single-item delete links from the listing reuse this view with one UID.

### User menu action — `profiles/default/actions.xml`

```xml
<object name="portal_actions" meta_type="Plone Actions Tool">
  <object name="user" meta_type="CMF Action Category">
    <object name="disk-usage" meta_type="CMF Action" i18n:domain="collective.quota" insert-after="preferences">
      <property name="title" i18n:translate="">Disk usage</property>
      <property name="description" i18n:translate="" />
      <property name="url_expr">python:f"{plone_portal_state.portal_url()}/@@quota-usage"</property>
      <property name="icon_expr">string:hdd</property>
      <property name="available_expr">python:member is not None</property>
      <property name="permissions">
        <element value="collective.quota: View Disk Usage" />
      </property>
      <property name="visible">True</property>
    </object>
  </object>
</object>
```

`hdd` is a Bootstrap icon shipped by `plone.staticresources` (there is no
`plone-upload` icon). `portal_url()` (not navigation root) because the view is registered on the site root
and the quota is site-wide. `profiles/uninstall/actions.xml` removes the action.
Plone's user menu honours `permissions`, so Members without `ViewDiskUsage` do not see
the entry; anonymous users never do.

## Files

Create:
- `backend/src/collective/quota/browser/usage.py`
- `backend/src/collective/quota/browser/delete.py`
- `backend/src/collective/quota/browser/templates/usage.pt`
- `backend/src/collective/quota/browser/templates/delete_confirmation.pt`
- `backend/src/collective/quota/profiles/default/actions.xml`
- `backend/src/collective/quota/profiles/uninstall/actions.xml`
- `backend/src/collective/quota/browser/summary.py`
- `backend/tests/test_usage_view.py`, `test_delete_view.py`, `test_user_action.py`,
  `test_summary.py`

Modify:
- `backend/src/collective/quota/browser/configure.zcml`
- `backend/src/collective/quota/controlpanels/quota.py` (usage card from `summary.py`;
  the "Review biggest items" link is now always shown)

## Tasks

- [x] `DiskUsageView` with `limit`, `items`, `usage`, metadata fallback, `can_delete`
- [x] `usage.pt` (summary card, alert, limit selector, table, select-all, delete button)
- [x] `QuotaDeleteView` two-step flow with `CheckAuthenticator`, lock handling, skipped items, status messages
- [x] `delete_confirmation.pt` embedding `@@delete_confirmation_info` output
- [x] `actions.xml` (default + uninstall)
- [x] Manual check: as Editor open the user menu → "Disk usage"; change N; tick 2 items → Delete → confirmation shows link-integrity warning when a Document links to one of them → confirm → items gone, status message shows bytes freed; anonymous `GET @@quota-usage` → login redirect
- [x] `make i18n`; `make lint`; coverage 100 %

## Tests

- [x] `test_usage_view.py::test_permission` — anonymous → `Unauthorized`; Member → `Unauthorized`; Editor/Contributor/Reviewer/Site Administrator → 200
- [x] `test_usage_view.py::test_items_sorted_desc_and_limited` — create 30 files of distinct sizes; default shows 25 biggest in order; `?limit=10` → 10; `?limit=999` → default 25
- [x] `test_usage_view.py::test_items_respect_view_permission` — private file not visible to a Contributor is absent from their list
- [x] `test_usage_view.py::test_metadata_fallback` — brain with `Missing.Value` metadata (populated via `reindexIndex` only) still shows the right size
- [x] `test_usage_view.py::test_summary_shows_limits_policy_and_level`
- [x] `test_usage_view.py::test_can_delete_flag` — item without `Delete objects` → checkbox disabled
- [x] `test_delete_view.py::test_no_selection_redirects_with_message`
- [x] `test_delete_view.py::test_confirmation_page_lists_items_and_total`
- [x] `test_delete_view.py::test_linkintegrity_breach_warning_rendered` — Document with a link to the File (relation via `plone.app.linkintegrity` test helpers) → snippet contains the Document title
- [x] `test_delete_view.py::test_no_warning_when_linkintegrity_disabled`
- [x] `test_delete_view.py::test_confirm_deletes_and_updates_total`
- [x] `test_delete_view.py::test_confirm_requires_authenticator` — missing/invalid token → `Forbidden`
- [x] `test_delete_view.py::test_items_without_delete_permission_skipped_with_message`
- [x] `test_delete_view.py::test_locked_by_other_user_skipped`
- [x] `test_delete_view.py::test_cancel_redirects`
- [x] `test_user_action.py::test_action_registered_with_permission` — `portal_actions.user["disk-usage"]`
- [x] `test_user_action.py::test_visible_in_user_menu_for_editor_not_member` — functional browser, check the rendered personal tools menu

## Acceptance criteria

- The listing is correct on a site with pre-existing content right after install.
- Deleting from the listing behaves exactly like deleting from folder contents with
  respect to link integrity warnings, locks and permissions.
- "Disk usage" is in the user menu for every role listed in the architecture doc and
  for nobody else by default.

## Notes / risks

Implementation notes (2026-10-16):

- **Catalog visibility is "Access contents information".** Plone's
  `allowedRolesAndUsers` indexer uses that permission, so an item whose "View" is
  restricted is still listed and `brain.getObject()` raises `Unauthorized`. Both views
  use `brain._unrestrictedGetObject()`; `Delete objects` is still checked on each object,
  and `manage_delObjects` checks it again.
- **Locks.** `@@plone_lock_info` is registered only for lockable content. File and
  Image have no `plone.locking` behavior by default, so the lookup returns `None` and
  they are deleted without lock checks; lock tests use a Document.
- **Bytes freed** are measured as the total before minus the total after the delete,
  so deleting a folder reports the files inside it too.
- **The link-integrity view always renders wrapper markup**; see `breaches_html` above.
- **Shared texts.** `browser/summary.py` holds the usage card values and the
  warning/exceeded texts with the policy hints from phase 6, so the viewlet can reuse them.
- Tests: `test_delete_view.py::TestBrowserFlow` covers the whole flow in a browser,
  including a delete over the hard limit with `block_all` that commits.
- Manual check on a running instance (port 8091, temporary site deleted afterwards:
  4.5 MB in `a` 3 MB, `b` 1 MB, `c` 512 KB, a Document linking to `b`, soft 1 MB,
  hard 2 MB, `block_all`):
  - Anonymous `GET @@quota-usage` → 302 to `require_login`.
  - Member: the page redirects to login, and there is no "Disk usage" entry in the user menu.
  - Editor: the user menu shows "Disk usage" with the `hdd` icon. The listing shows
    a, b, c in that order, with the red alert "Disk quota exceeded: this site uses
    4.5 MB of 2.0 MB. New content and uploads are blocked until files are removed."
    and no settings or rebuild links. `?limit=10` preselects 10.
  - Selecting a and b showed "the following 2 items (4.0 MB in total)" and the
    link-integrity warning naming "Linking page". Confirming with a bad token returned
    403. Confirming with the page's token redirected to `@@quota-usage` with "Deleted 2
    items, freeing 4.0 MB." Only c was left, and the total showed 512.0 KB.

- `@@delete_confirmation_info` renders HTML only when `plone.app.layout`'s layer is
  active (always true in Classic). The layer-less fallback returns `""`, so the view
  must not assume HTML.
- Up to 100 object loads per render for the `can_delete` flag; acceptable. If
  profiling shows an issue, drop the flag and rely on the skipped-items message.
- Deleting never adds bytes, so the commit guard (phase 4) never interferes with
  `@@quota-delete`; the test suite asserts that a delete over the limit commits.
- `sort_limit` with a restricted search can return fewer than N items when the user
  cannot see some of the biggest ones; that is expected (the footer text says so).
