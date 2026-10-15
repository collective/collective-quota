# Phase 4 — Quota policy, enforcement in Classic forms and REST, transaction commit guard

Status: Done
Depends on: Phase 2, Phase 3
Last updated: 2026-10-15

## Goal

When a save would push total usage above the hard limit, the configured policy is
applied consistently in Classic UI forms and through `plone.restapi`, with clear,
translated error messages, and without ever blocking cleanup (saves that do not add
bytes). Independently of the UI, a transaction-level guard makes sure that **no code
path** (scripts, `plone.api`, copy/paste, imports, custom widgets) can cross a
configured hard limit without the policy having approved it.

## Scope

In: `policy.py` (pure logic + exception), hook A (pluggable field validators), hook B
(Classic add-form guard), hook C (REST add guard), hook D (commit guard + ledger +
added-event subscriber + `guard_suspended`), messages, tests.

Out: warning UI (phases 5–6).

## Design

### Policy module — `policy.py`

```python
BLOCK_ALL = "block_all"
BLOCK_FILES = "block_files"
LIMIT_FILE_SIZE = "limit_file_size"
ALLOW = "allow"
POLICIES = (BLOCK_ALL, BLOCK_FILES, LIMIT_FILE_SIZE, ALLOW)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str | None = None          # "upload_blocked" | "file_too_large" | "add_blocked"
    mapping: dict = field(default_factory=dict)   # human-readable sizes for messages

    @property
    def message(self):  # zope.i18nmessageid Message in domain collective.quota, or None


def evaluate_upload(total: int, old_size: int, new_size: int, settings: QuotaSettings) -> Decision:
    delta = new_size - old_size
    if settings.hard_bytes <= 0 or delta <= 0 or total + delta <= settings.hard_bytes:
        return Decision(True)
    if settings.policy == ALLOW:
        return Decision(True)
    if settings.policy == LIMIT_FILE_SIZE:
        if new_size <= settings.max_file_bytes:
            return Decision(True)
        return Decision(False, "file_too_large", {...})
    return Decision(False, "upload_blocked", {...})     # BLOCK_ALL, BLOCK_FILES


def evaluate_add(total: int, settings: QuotaSettings) -> Decision:
    if settings.policy == BLOCK_ALL and settings.hard_bytes > 0 and total >= settings.hard_bytes:
        return Decision(False, "add_blocked", {...})
    return Decision(True)


class QuotaExceeded(zope.schema.ValidationError):
    """Raised by hook A; carries the Decision."""

    def __init__(self, decision):
        super().__init__(decision)
        self.decision = decision

    def doc(self):
        return self.decision.message
```

Messages (domain `collective.quota`, mappings use `human_readable_size`):

| reason | message |
|---|---|
| `upload_blocked` | "This file cannot be saved: the site has reached its disk quota (${used} of ${limit}). Delete or shrink existing files first." |
| `file_too_large` | "The site has reached its disk quota (${used} of ${limit}); only files up to ${max_size} can be added now. This file is ${size}." |
| `add_blocked` | "New content cannot be added: the site has reached its disk quota (${used} of ${limit}). Delete or shrink existing files first." |

The semantics table in `00-architecture.md` §4 is normative; unit tests cover every row.

### Hook A — upload validator (`validators.py`)

```python
@implementer(IPluggableFileFieldValidation, IPluggableImageFieldValidation)
@adapter(INamedField, Interface)
class QuotaUploadValidator:
    def __init__(self, field, value):
        self.field, self.value = field, value

    def __call__(self):
        value = self.value
        if value is None or not hasattr(value, "getSize"):
            return
        context = getattr(self.field, "context", None)
        old_value = None
        if context is not None:
            old_value = get_stored_value(context, self.field.interface, self.field.__name__)  # from indexers.blob_size
            if old_value is value:
                return                        # unchanged / re-sent representation
        settings = get_settings()
        if settings.hard_bytes <= 0:
            return
        site = getSite()
        if site is None or get_index(site) is None:
            return
        old_size = old_value.getSize() if old_value is not None else 0
        new_size = int(value.getSize() or 0)
        decision = evaluate_upload(get_total_usage(site), old_size, new_size, settings)
        if not decision.allowed:
            raise QuotaExceeded(decision)
        if new_size > old_size:
            record_approved_bytes(new_size - old_size)      # ledger entry for hook D
```

ZCML (two registrations, same factory, **named** so they do not replace
`plone.namedfile`'s own content-type validators):

```xml
<adapter factory=".validators.QuotaUploadValidator"
         provides="plone.namedfile.interfaces.IPluggableFileFieldValidation"
         name="collective.quota" />
<adapter factory=".validators.QuotaUploadValidator"
         provides="plone.namedfile.interfaces.IPluggableImageFieldValidation"
         name="collective.quota" />
```

Why this works in both UIs: `NamedField.validate()` runs these adapters; z3c.form's
`SimpleFieldValidator` binds the field to the content (edit forms) or leaves it unbound
(add forms, `ignoreContext=True`) and calls `field.validate(value)`; `plone.restapi`'s
`NamedFieldDeserializer` binds the field to the (new or existing) object, converts the
JSON/multipart/TUS payload into the field value and calls `field.validate(value)`.

Error rendering:
- Classic: z3c.form shows `error.doc()` under the file widget and the generic "There
  were some errors" status.
- REST: `plone.restapi` collects `{"field": name, "message": error.doc()}` and answers
  `400 Bad Request` with the standard error body.

`field.interface` can be `None` for fields created outside a schema; then fall back
to `getattr(context, name, None)`.

### Hook B — Classic add-form guard (`browser/addform_guard.py`)

```python
@adapter(Interface, IBrowserLayer, IAddForm, IInterface, Interface)
class QuotaAddFormValidator(InvariantsValidator):
    def validate(self, data):
        errors = list(super().validate(data))
        marker = IAnnotations(self.request).setdefault("collective.quota.addform_checked", set())
        if id(self.view) in marker:
            return tuple(errors)
        marker.add(id(self.view))
        decision = evaluate_add(get_total_usage(), get_settings())
        if not decision.allowed:
            errors.append(Invalid(decision.message))
        else:
            record_approved_add()                          # ledger entry for hook D
        return tuple(errors)
```

Registered in `browser/configure.zcml` as a plain `<adapter factory=... />`
(`provides` inferred from `InvariantsValidator`). The dedupe guard exists because
z3c.form calls the manager validator once per schema interface present in the form
(main schema plus each behavior). Verify at implementation that
`plone.dexterity.browser.add.DefaultAddForm` provides `z3c.form.interfaces.IAddForm`;
if not, discriminate on the class with `WidgetsValidatorDiscriminators(view=DefaultAddForm)`.

The error is rendered by z3c.form's `InvalidErrorViewSnippet` at the top of the form; the
item is not created.

### Hook C — REST add guard (`restapi/deserializer.py`)

```python
@implementer(IDeserializeFromJson)
@adapter(IDexterityContent, IQuotaRestapiLayer)
class QuotaAwareDeserializer(DeserializeFromJson):
    def __call__(self, validate_all=False, data=None, create=False, mask_validation_errors=True):
        if create:
            decision = evaluate_add(get_total_usage(), get_settings())
            if not decision.allowed:
                raise BadRequest(translate(decision.message, context=self.request))
            record_approved_add()                           # ledger entry for hook D
        return super().__call__(validate_all=validate_all, data=data, create=create,
                                mask_validation_errors=mask_validation_errors)
```

The installed `plone.restapi` registers a **single** `DeserializeFromJson` for
`IDexterityContent` (items and containers alike; there is no separate folder
deserializer), so one override covers both; the `__call__` signature above matches it.
`POST` creates the object first and deserializes onto it with `create=True`, so the
check runs before the object is added; TUS uploads (`@tus-upload`) go through the same
deserializer. Raising `BadRequest` aborts the transaction and yields a 400 JSON error.

### Hook D — commit guard (`guard.py`)

Normative description: `00-architecture.md` §5.1. Implementation:

```python
LEDGER_KEY = _LedgerKey()        # set_data() keys by id(), so use a module-level object


@dataclass
class Ledger:
    start_total: int | None = None
    exempt_bytes: int = 0          # index changes made inside guard_suspended()
    approved_bytes: int = 0
    added_items: int = 0
    approved_items: int = 0
    hook_registered: bool = False


def get_ledger(txn=None) -> Ledger:
    # txn.data()/set_data() when available, else a WeakKeyDictionary keyed by txn


def note_index_change(index, delta):          # called by BlobSizeIndex after a non-zero delta
    ledger = get_ledger()
    if ledger.start_total is None:
        ledger.start_total = index.total() - delta   # total before this first change
    if is_suspended():
        ledger.exempt_bytes += delta                  # trusted change: not checked
        return
    _ensure_hook(ledger, index)


def on_item_added(obj, event):                # IObjectAddedEvent, any IDexterityContent
    if is_suspended(): return
    ledger.added_items += 1; _ensure_hook(ledger, obj)


def _ensure_hook(ledger, context):
    # once per transaction; portal from getSite(), else acquired from context
    transaction.get().addBeforeCommitHook(check_quota, args=(root, portal_path))


def check_quota(root, portal_path):
    portal = root.unrestrictedTraverse(portal_path, None)      # gone -> return
    with site(portal):                                         # registry needs the site
        settings = get_settings()
        if settings.hard_bytes <= 0 or get_index(portal) is None: return
        total = get_total_usage(portal)                        # flushes the indexing queue
    net_delta = total - (ledger.start_total or total) - ledger.exempt_bytes
    if net_delta > 0 and total > hard and policy != ALLOW and net_delta > ledger.approved_bytes:
        raise QuotaCommitAborted("unapproved_bytes", mapping)  # logged as a warning
    if policy == BLOCK_ALL and total >= hard and ledger.added_items > ledger.approved_items:
        raise QuotaCommitAborted("unapproved_items", mapping)


@contextmanager
def guard_suspended():
    # thread-local depth counter (nesting-safe); logs the caller at INFO.
    # Changes made inside the block are exempt; this holds across commits made
    # inside the block, and changes made outside it are still checked.


class QuotaCommitAborted(zExceptions.BadRequest):
    # .reason, .mapping, .message; __str__ translates with getRequest()
```

Registration: `<subscriber handler=".guard.on_item_added" />` in `configure.zcml`
(no layer: scripts have no request layer). `BlobSizeIndex._index_object` /
`unindex_object` already call `note_index_change` (stubbed in phase 2); replace the
stub. `rebuild_usage` wraps its loop in `guard_suspended()`.

Error surfaces:
- HTTP status: ZPublisher derives the status from the exception class *name*, so
  `guard.py` registers `quotacommitaborted → 400` in `ZPublisher.HTTPResponse.status_codes`
  (otherwise both UIs answer 500).
- Classic UI: Plone's generic error page hides exception messages from non-managers, so
  an exception view `index.html` for `(QuotaCommitAborted, IBrowserLayer)`
  (`browser/errors.py`, `templates/quota_error.pt`) renders "Disk quota exceeded" with
  the message for everybody; like Plone's own view it answers JSON
  (`{"error_type", "message"}`) when the request does not accept `text/html`. Normal
  users only reach it for copy/paste over the limit and custom code.
- REST: the same view delegates `IAPIRequest`s to `plone.rest`'s `ErrorHandling`
  (400 JSON body with `type` and `message`).
- Scripts: the exception propagates from `transaction.commit()`.

Messages (domain `collective.quota`):

| reason | message |
|---|---|
| `unapproved_bytes` | "The change was cancelled: it would add ${delta} to the site and exceed the disk quota (${used} of ${limit})." |
| `unapproved_items` | "The change was cancelled: new content cannot be added while the site exceeds its disk quota (${used} of ${limit})." |

Transaction-scoped storage: use `transaction.get().set_data()/data()` (available in
`transaction` ≥ 2.0). Guard against transactions that do not support it (`AttributeError`)
with a module-level `WeakKeyDictionary` fallback keyed by the transaction object; both
paths are tested.

### Paths that now are enforced

`plone.api.content.create`, `invokeFactory` + reindex, copy/paste in folder contents,
`plone.exportimport`, upgrade steps, direct attribute writes followed by
`reindexObject()`. All of them are aborted at commit when they would cross the hard
limit without approval. Trusted code opts out with `guard_suspended()`; the README
documents it as administrator-only and recommends running such scripts with the hard
limit temporarily raised instead when possible.

## Files

Create:
- `backend/src/collective/quota/validators.py`
- `backend/src/collective/quota/browser/addform_guard.py`
- `backend/src/collective/quota/restapi/deserializer.py`
- `backend/src/collective/quota/browser/errors.py`, `browser/templates/quota_error.pt` (guard error page)
- `backend/tests/test_policy.py`, `test_enforcement_classic.py`, `test_enforcement_restapi.py`, `test_guard_unit.py`, `test_guard_integration.py`, `test_validators.py`

Modify:
- `backend/src/collective/quota/policy.py` (full implementation)
- `backend/src/collective/quota/guard.py` (replace phase 2 stubs with the full implementation)
- `backend/src/collective/quota/catalog/blob_size_index.py` (confirm `note_index_change` call sites)
- `backend/src/collective/quota/usage.py` (`rebuild_usage` under `guard_suspended()`)
- `backend/src/collective/quota/configure.zcml` (validator adapters)
- `backend/src/collective/quota/browser/configure.zcml` (add-form guard)
- `backend/src/collective/quota/restapi/configure.zcml` (deserializers)

## Tasks

- [x] Implement `Decision`, `evaluate_upload`, `evaluate_add`, `QuotaExceeded`, messages
- [x] Implement and register `QuotaUploadValidator` (two named registrations)
- [x] Implement and register `QuotaAddFormValidator`; confirm the `IAddForm` discriminator against the installed `plone.dexterity`
- [x] Implement and register the REST deserializer override (one is enough, see Hook C); confirm `__call__` signature against the installed `plone.restapi`
- [x] Implement `guard.py`: `Ledger`, `get_ledger` (+ fallback storage), `note_index_change`, `record_approved_bytes`, `record_approved_add`, `on_item_added`, `check_quota`, `guard_suspended`, `QuotaCommitAborted`; register the subscriber
- [x] Hooks A, B, C record approvals in the ledger
- [x] `rebuild_usage` runs under `guard_suspended()`; `post_install` on a site over the limit succeeds
- [x] Manual check (bypass): with hard 1 MB reached and `block_all`, copy/paste a 2 MB File in folder contents → error page with the guard message, nothing pasted; run a `zconsole` script using `plone.api.content.create` with a 2 MB file → `transaction.commit()` raises; wrap it in `guard_suspended()` → succeeds
- [x] Manual check (Classic): set hard 1 MB, policy `block_all`; add a 2 MB File → form error under the file field; add a Document → form-level error; replace an existing 2 MB file with 500 KB → saved
- [x] Manual check (REST, e.g. `curl`/httpie): same three cases → 400 / 400 / 204
- [x] `make i18n`; `make lint`; coverage 100 %

## Tests

- [x] `test_policy.py` — parametrised over the semantics table (every policy × new item / upload crossing / upload under limit / replace smaller / hard disabled / exactly at limit); `evaluate_add` for each policy at/below/above hard
- [x] `test_policy.py::test_messages_have_human_readable_sizes`
- [x] `test_enforcement_classic.py::test_upload_over_limit_blocked_on_add_form` — browser as Editor, `++add++File`, 2 MB upload with hard 1 MB → error text present, no object created, total unchanged
- [x] `test_enforcement_classic.py::test_upload_within_limit_saved`
- [x] `test_enforcement_classic.py::test_edit_replace_with_smaller_allowed_when_over_limit`
- [x] `test_enforcement_classic.py::test_edit_keep_existing_file_allowed` — edit title only on an over-limit site; "keep existing" radio → saved
- [x] `test_enforcement_classic.py::test_limit_file_size_policy` — 5 MB file with max 10 MB allowed; 15 MB denied
- [x] `test_enforcement_classic.py::test_block_all_blocks_document_add` — `++add++Document` over limit → form error; `block_files` → created
- [x] `test_enforcement_classic.py::test_lead_image_behavior_validated` — Document with lead image upload over limit → error
- [x] `test_enforcement_classic.py::test_multi_field_type_each_field_validated`
- [x] `test_enforcement_restapi.py::test_post_file_over_limit_400` — base64 `data` payload → 400, body contains the message and `"field": "file"`
- [x] `test_enforcement_restapi.py::test_patch_file_over_limit_400`
- [x] `test_enforcement_restapi.py::test_patch_resend_representation_allowed` — `{"download": ...}` without `data` → 204
- [x] `test_enforcement_restapi.py::test_patch_replace_with_smaller_allowed`
- [x] `test_enforcement_restapi.py::test_post_document_blocked_under_block_all` — 400; under `block_files` → 201
- [x] `test_enforcement_restapi.py::test_post_into_folder_uses_container_deserializer` — POST a Folder (container type) under `block_all` → 400 (same single deserializer)
- [x] `test_enforcement_restapi.py::test_tus_upload_over_limit_400` (automated: `TestTus`, over and within the limit)
- [x] `test_enforcement_restapi.py::test_transaction_aborted_on_400` — no partial object left in the folder
- [x] `test_guard_unit.py::test_ledger_created_once_per_transaction_and_cleared_after_commit`
- [x] `test_guard_unit.py::test_fallback_storage_when_transaction_lacks_set_data`
- [x] `test_guard_unit.py::test_note_index_change_sets_start_total_once_and_registers_hook_once`
- [x] `test_guard_unit.py::test_check_quota_matrix` — parametrised: hard disabled; net ≤ 0; under limit; over limit with full approval; over limit with partial approval (abort); `allow` policy; moves (net 0 with per-object churn); `block_all` with unapproved add at/above/below hard; `block_files` with unapproved add (allowed); suspended; portal gone; index missing
- [x] `test_guard_unit.py::test_guard_suspended_restores_previous_state_and_logs_caller`
- [x] `test_guard_unit.py::test_quota_commit_aborted_message_translated`
- [x] `test_guard_integration.py::test_plone_api_create_over_limit_aborted_on_commit` — `api.content.create` 2 MB file at hard 1 MB, `transaction.commit()` raises `QuotaCommitAborted`, object absent after `transaction.begin()`, total unchanged
- [x] `test_guard_integration.py::test_direct_attribute_write_and_reindex_aborted`
- [x] `test_guard_integration.py::test_copy_paste_over_limit_aborted` — `manage_pasteObjects` or `api.content.copy`
- [x] `test_guard_integration.py::test_move_and_rename_over_limit_allowed` — net 0
- [x] `test_guard_integration.py::test_delete_always_allowed_over_limit`
- [x] `test_guard_integration.py::test_validated_upload_commits` — form/REST path approves, commit succeeds
- [x] `test_guard_integration.py::test_multi_field_form_net_delta_within_approvals`
- [x] `test_guard_integration.py::test_block_all_unapproved_document_create_aborted_block_files_allowed`
- [x] `test_guard_integration.py::test_rebuild_usage_on_over_limit_site_succeeds` — fresh install with 3 MB of pre-existing content and hard 1 MB
- [x] `test_guard_integration.py::test_allow_policy_never_aborts`
- [x] `test_guard_integration.py::test_no_hook_registered_for_unrelated_transactions` — editing a Document title registers nothing (inspect `transaction.get()._before_commit`)
- [x] `test_guard_integration.py::test_env_locked_hard_limit_enforced_by_guard` — registry says 0, env says 1 MB with lock → guard aborts

## Acceptance criteria

- With hard limit reached and `block_all`, neither Classic nor REST can add bytes or
  create items; with `block_files` items without files can still be created; with
  `limit_file_size` small files still go in; with `allow` nothing is blocked.
- Replacing a big file with a smaller one always works, in both UIs.
- No code path can commit a transaction that crosses the hard limit without validator
  approval, except code that explicitly uses `guard_suspended()`.
- Transactions that do not touch blobs or add items register no hook (zero overhead).
- Error messages are translated and show sizes like "1.2 GB", never raw bytes.

## Notes / risks

Implementation notes (2026-10-15):

- **Suspension is scoped to changes, not to the commit.** The draft's
  `guard_suspended()` set a ledger flag and restored it on exit, and `check_quota`
  returned early when the flag was set. But the commit happens *after* the block, so
  `rebuild_usage()` followed by `transaction.commit()` (the install path) would have
  been aborted on a site over the limit. Now index changes made inside the block are
  added to `ledger.exempt_bytes` and items added inside it are not counted. Suspension is a
  thread-local depth counter, so it also covers commits made inside the block (a new
  transaction gets a new ledger). GenericSetup's catalog import does not reindex new
  indexes, so `post_install` is the only place the install fills the index.
- **Add forms bind the field to the container.** z3c.form validates add-form fields
  bound to the container, so a container with the same field (e.g. a lead image)
  would have been read as the "old value". Hook A ignores the bound context while the
  published view is an `IAddForm` (`_in_add_form()`, via `PUBLISHED.form_instance`).
- `DefaultAddForm` provides `IAddForm` (z3c.form `AddForm`): the plain discriminator works.
  Under `block_all` over the limit, the File add form shows both the add-blocked
  (form-level) and the upload-blocked (field) errors.
- `plone.namedfile` in Plone 6.2 has pluggable validation; no pin needed. The
  validators are global (no layer): on sites without the index they allow everything.
- Error surfaces: the 400 status registration and the exception view (see Hook D) were
  not in the draft; without them REST answered 500 and editors saw no message.
- Tests: `make_file` creates content under `guard_suspended()` and flushes the
  indexing queue, so tests can still push a site over its limit. The "multi field"
  Classic test documents the accepted overshoot: two 600 KB files each pass alone
  under a 1 MB limit, the next upload is blocked. `test_validators.py` covers hook A
  edge cases directly; error surfaces are covered by `TestErrorSurfaces`.
- Manual check on a running instance (port 8091, temporary site at 2.3 MB with hard
  1 MB and `block_all`, deleted afterwards), as a user with Editor + Contributor:
  - Classic: adding a 2 MB File and adding a Document were refused with the form
    errors.
  - REST: `POST` of a File and of a Document returned 400.
  - Copy/paste through `object_copy`/`object_paste` returned 400 and showed
    "Disk quota exceeded" with the guard message; nothing was pasted.
  - Replacing with a smaller file worked: REST `PATCH` 300 → 100 KB returned 204,
    and the Classic edit 2 MB → 500 KB was saved.
  - zconsole: `plone.api.content.create` of a 2 MB file made `transaction.commit()`
    raise `QuotaCommitAborted` and left no object. The same create inside
    `guard_suspended()` committed.


- Indexing queue (found in phase 2): Plone flushes `Products.CMFCore.indexing`'s queue
  in its *own* before-commit hook, so when `check_quota` runs, queued reindexes may not
  be applied yet. `check_quota` must read the total through `get_total_usage()` (which
  calls `processQueue()`), never `index.total()` directly. The index may also register
  the guard hook *while* the queue hook runs; `transaction` runs hooks appended during
  the hook loop, but cover this ordering with a test.

- `plone.namedfile` pluggable validation minimum version: confirm in
  `backend/requirements-mxdev.txt`/constraints; if the installed version lacks it, pin a
  newer `plone.namedfile` compatible with Plone 6.2 and record it in `pyproject.toml`.
- Widgets that bypass `field.validate` (custom AJAX uploaders) are not covered; the
  Classic default `NamedFile` widgets are.
- `IAnnotations(request)` is available on all Zope requests; in tests with a fake
  request, use `zope.annotation` `attribute` annotations on `TestRequest`.
- Before-commit hooks run in registration order; ours only reads, so ordering relative
  to other hooks does not matter **except** for queued indexing: if an indexing queue
  flushes in its own before-commit hook registered *after* ours, `index.total()` would
  be stale. Detect at implementation whether the `Products.CMFCore` indexing queue is
  active and, if so, call `processQueue()` at the start of `check_quota`. Test with the
  queue enabled.
- `savepoint()` and `savepoint.rollback()` do not roll back the ledger; a rollback in
  the middle of a transaction followed by a commit could make `start_total` wrong. The
  guard re-reads `index.total()` at commit, and `start_total` only moves if a rollback
  undid the *first* change. Accept and document; Plone's publisher does not use
  savepoints around content writes.
