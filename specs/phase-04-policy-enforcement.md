# Phase 4 — Quota policy, enforcement in Classic forms and REST, transaction commit guard

Status: Not started
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
class _AddGuardMixin:
    def __call__(self, validate_all=False, data=None, create=False, mask_validation_errors=True):
        if create:
            decision = evaluate_add(get_total_usage(), get_settings())
            if not decision.allowed:
                raise BadRequest(translate(decision.message, context=self.request))
            record_approved_add()                           # ledger entry for hook D
        return super().__call__(validate_all=validate_all, data=data, create=create,
                                mask_validation_errors=mask_validation_errors)


@implementer(IDeserializeFromJson)
@adapter(IDexterityContent, IQuotaRestapiLayer)
class QuotaAwareDeserializer(_AddGuardMixin, DeserializeFromJson): ...


@implementer(IDeserializeFromJson)
@adapter(IDexterityContainer, IQuotaRestapiLayer)
class QuotaAwareFolderDeserializer(_AddGuardMixin, DeserializeFolderFromJson): ...
```

Both registrations are needed because `plone.restapi` registers separate deserializers
for items and containers. Check the exact `__call__` signature of the installed
`plone.restapi` and mirror it. Raising `BadRequest` inside the deserializer aborts the
transaction (the half-created object is discarded) and yields a 400 JSON error.

### Hook D — commit guard (`guard.py`)

Normative description: `00-architecture.md` §5.1. Implementation:

```python
LEDGER_KEY = "collective.quota.ledger"


@dataclass
class Ledger:
    start_total: int | None = None
    approved_bytes: int = 0
    added_items: int = 0
    approved_items: int = 0
    suspended: bool = False
    hook_registered: bool = False


def get_ledger(txn=None) -> Ledger:
    txn = txn or transaction.get()
    ledger = txn.data(LEDGER_KEY) if _has_txn_data(txn) else _fallback.get(txn)
    if ledger is None:
        ledger = Ledger()
        txn.set_data(LEDGER_KEY, ledger)      # or WeakKeyDictionary fallback keyed by txn
    return ledger


def note_index_change(index, delta):          # called by BlobSizeIndex after a non-zero delta
    ledger = get_ledger()
    if ledger.start_total is None:
        ledger.start_total = index.total() - delta   # total before this first change
    _ensure_hook(ledger)


def record_approved_bytes(n: int):
    get_ledger().approved_bytes += n


def record_approved_add():
    get_ledger().approved_items += 1


@adapter(IDexterityContent, IObjectAddedEvent)
def on_item_added(obj, event):
    ledger = get_ledger()
    ledger.added_items += 1
    _ensure_hook(ledger)


def _ensure_hook(ledger):
    if not ledger.hook_registered:
        transaction.get().addBeforeCommitHook(check_quota, args=(_portal_path(),))
        ledger.hook_registered = True


def check_quota(portal_path):
    ledger = get_ledger()
    if ledger.suspended:
        return
    settings = get_settings()
    if settings.hard_bytes <= 0:
        return
    portal = _resolve_portal(portal_path)      # unrestrictedTraverse; return if gone
    index = get_index(portal)
    if index is None:
        return
    total = index.total()
    start = ledger.start_total if ledger.start_total is not None else total
    net_delta = total - start
    if (net_delta > 0 and total > settings.hard_bytes and settings.policy != ALLOW
            and net_delta > ledger.approved_bytes):
        logger.warning("quota guard aborted transaction: unapproved bytes ...")
        raise QuotaCommitAborted("unapproved_bytes", mapping=...)
    if (settings.policy == BLOCK_ALL and total >= settings.hard_bytes
            and ledger.added_items > ledger.approved_items):
        raise QuotaCommitAborted("unapproved_items", mapping=...)


@contextmanager
def guard_suspended():
    ledger = get_ledger()
    previous = ledger.suspended
    ledger.suspended = True
    logger.info("quota guard suspended by %s", <caller from inspect.stack()>)
    try:
        yield
    finally:
        ledger.suspended = previous


class QuotaCommitAborted(zExceptions.BadRequest):
    # Raised from the before-commit hook; __str__ returns the translated message.
    ...
```

Registration: `<subscriber handler=".guard.on_item_added" />` in `configure.zcml`
(no layer: scripts have no request layer). `BlobSizeIndex._index_object` /
`unindex_object` already call `note_index_change` (stubbed in phase 2); replace the
stub. `rebuild_usage` wraps its loop in `guard_suspended()`.

Error surfaces:
- Classic UI: the publisher aborts the transaction and renders the standard error page
  with the `QuotaCommitAborted` message (translated in `__str__` using the request from
  `getRequest()` when available). Normal users never reach it because hooks A–C deny
  earlier; it appears for copy/paste over the limit and for custom code.
- REST: `plone.restapi` error handling turns `BadRequest` into a 400 JSON body.
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
- `backend/tests/test_policy.py`, `test_enforcement_classic.py`, `test_enforcement_restapi.py`, `test_guard_unit.py`, `test_guard_integration.py`

Modify:
- `backend/src/collective/quota/policy.py` (full implementation)
- `backend/src/collective/quota/guard.py` (replace phase 2 stubs with the full implementation)
- `backend/src/collective/quota/catalog/blob_size_index.py` (confirm `note_index_change` call sites)
- `backend/src/collective/quota/usage.py` (`rebuild_usage` under `guard_suspended()`)
- `backend/src/collective/quota/configure.zcml` (validator adapters)
- `backend/src/collective/quota/browser/configure.zcml` (add-form guard)
- `backend/src/collective/quota/restapi/configure.zcml` (deserializers)

## Tasks

- [ ] Implement `Decision`, `evaluate_upload`, `evaluate_add`, `QuotaExceeded`, messages
- [ ] Implement and register `QuotaUploadValidator` (two named registrations)
- [ ] Implement and register `QuotaAddFormValidator`; confirm the `IAddForm` discriminator against the installed `plone.dexterity`
- [ ] Implement and register both REST deserializer overrides; confirm `__call__` signature against the installed `plone.restapi`
- [ ] Implement `guard.py`: `Ledger`, `get_ledger` (+ fallback storage), `note_index_change`, `record_approved_bytes`, `record_approved_add`, `on_item_added`, `check_quota`, `guard_suspended`, `QuotaCommitAborted`; register the subscriber
- [ ] Hooks A, B, C record approvals in the ledger
- [ ] `rebuild_usage` runs under `guard_suspended()`; `post_install` on a site over the limit succeeds
- [ ] Manual check (bypass): with hard 1 MB reached and `block_all`, copy/paste a 2 MB File in folder contents → error page with the guard message, nothing pasted; run a `zconsole` script using `plone.api.content.create` with a 2 MB file → `transaction.commit()` raises; wrap it in `guard_suspended()` → succeeds
- [ ] Manual check (Classic): set hard 1 MB, policy `block_all`; add a 2 MB File → form error under the file field; add a Document → form-level error; replace an existing 2 MB file with 500 KB → saved
- [ ] Manual check (REST, e.g. `curl`/httpie): same three cases → 400 / 400 / 204
- [ ] `make i18n`; `make lint`; coverage 100 %

## Tests

- [ ] `test_policy.py` — parametrised over the semantics table (every policy × new item / upload crossing / upload under limit / replace smaller / hard disabled / exactly at limit); `evaluate_add` for each policy at/below/above hard
- [ ] `test_policy.py::test_messages_have_human_readable_sizes`
- [ ] `test_enforcement_classic.py::test_upload_over_limit_blocked_on_add_form` — browser as Editor, `++add++File`, 2 MB upload with hard 1 MB → error text present, no object created, total unchanged
- [ ] `test_enforcement_classic.py::test_upload_within_limit_saved`
- [ ] `test_enforcement_classic.py::test_edit_replace_with_smaller_allowed_when_over_limit`
- [ ] `test_enforcement_classic.py::test_edit_keep_existing_file_allowed` — edit title only on an over-limit site; "keep existing" radio → saved
- [ ] `test_enforcement_classic.py::test_limit_file_size_policy` — 5 MB file with max 10 MB allowed; 15 MB denied
- [ ] `test_enforcement_classic.py::test_block_all_blocks_document_add` — `++add++Document` over limit → form error; `block_files` → created
- [ ] `test_enforcement_classic.py::test_lead_image_behavior_validated` — Document with lead image upload over limit → error
- [ ] `test_enforcement_classic.py::test_multi_field_type_each_field_validated`
- [ ] `test_enforcement_restapi.py::test_post_file_over_limit_400` — base64 `data` payload → 400, body contains the message and `"field": "file"`
- [ ] `test_enforcement_restapi.py::test_patch_file_over_limit_400`
- [ ] `test_enforcement_restapi.py::test_patch_resend_representation_allowed` — `{"download": ...}` without `data` → 204
- [ ] `test_enforcement_restapi.py::test_patch_replace_with_smaller_allowed`
- [ ] `test_enforcement_restapi.py::test_post_document_blocked_under_block_all` — 400; under `block_files` → 201
- [ ] `test_enforcement_restapi.py::test_post_into_folder_uses_container_deserializer` — POST a Folder (container type) under `block_all` → 400
- [ ] `test_enforcement_restapi.py::test_tus_upload_over_limit_400` (if TUS is easy to drive in tests; otherwise mark as manual)
- [ ] `test_enforcement_restapi.py::test_transaction_aborted_on_400` — no partial object left in the folder
- [ ] `test_guard_unit.py::test_ledger_created_once_per_transaction_and_cleared_after_commit`
- [ ] `test_guard_unit.py::test_fallback_storage_when_transaction_lacks_set_data`
- [ ] `test_guard_unit.py::test_note_index_change_sets_start_total_once_and_registers_hook_once`
- [ ] `test_guard_unit.py::test_check_quota_matrix` — parametrised: hard disabled; net ≤ 0; under limit; over limit with full approval; over limit with partial approval (abort); `allow` policy; moves (net 0 with per-object churn); `block_all` with unapproved add at/above/below hard; `block_files` with unapproved add (allowed); suspended; portal gone; index missing
- [ ] `test_guard_unit.py::test_guard_suspended_restores_previous_state_and_logs_caller`
- [ ] `test_guard_unit.py::test_quota_commit_aborted_message_translated`
- [ ] `test_guard_integration.py::test_plone_api_create_over_limit_aborted_on_commit` — `api.content.create` 2 MB file at hard 1 MB, `transaction.commit()` raises `QuotaCommitAborted`, object absent after `transaction.begin()`, total unchanged
- [ ] `test_guard_integration.py::test_direct_attribute_write_and_reindex_aborted`
- [ ] `test_guard_integration.py::test_copy_paste_over_limit_aborted` — `manage_pasteObjects` or `api.content.copy`
- [ ] `test_guard_integration.py::test_move_and_rename_over_limit_allowed` — net 0
- [ ] `test_guard_integration.py::test_delete_always_allowed_over_limit`
- [ ] `test_guard_integration.py::test_validated_upload_commits` — form/REST path approves, commit succeeds
- [ ] `test_guard_integration.py::test_multi_field_form_net_delta_within_approvals`
- [ ] `test_guard_integration.py::test_block_all_unapproved_document_create_aborted_block_files_allowed`
- [ ] `test_guard_integration.py::test_rebuild_usage_on_over_limit_site_succeeds` — fresh install with 3 MB of pre-existing content and hard 1 MB
- [ ] `test_guard_integration.py::test_allow_policy_never_aborts`
- [ ] `test_guard_integration.py::test_no_hook_registered_for_unrelated_transactions` — editing a Document title registers nothing (inspect `transaction.get()._before_commit`)
- [ ] `test_guard_integration.py::test_env_locked_hard_limit_enforced_by_guard` — registry says 0, env says 1 MB with lock → guard aborts

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
