# Phase 3 — Settings: registry + environment variables + lock flag, control panel, REST control panel adapter

Status: Done
Depends on: Phase 1, Phase 2
Last updated: 2026-10-15

## Goal

Site administrators configure the soft limit, hard limit, over-limit policy, and the
per-file cap in a Classic control panel, or operators set them through environment
variables. `COLLECTIVE_QUOTA_LOCK_SETTINGS` makes environment values fixed; otherwise
the control panel can override them. The same settings are exposed through
`@controlpanels/collective-quota` for the future Volto panel, with the same lock rules.
The control panel also shows current usage, the source of every value, and offers the
"Rebuild usage data" and "Reset to defaults" actions.

## Scope

In: `IQuotaSettings`, registry records, vocabulary, `settings.py` (environment parsing,
lock, resolution), control panel form + template with usage summary, value sources,
locked fields, rebuild and reset buttons, REST configlet adapter honouring the lock,
tests.

Out: enforcement (phase 4), listing (phase 5).

## Design

### Schema — `interfaces.py`

```python
class IQuotaSettings(Interface):
    soft_limit_mb = schema.Int(
        title=_("Soft limit (MB)"),
        description=_("When total usage reaches this value, editors see a warning. 0 disables the warning. Leave empty to use the environment variable or the default."),
        min=0, required=False,                      # registry default None
    )
    hard_limit_mb = schema.Int(
        title=_("Hard limit (MB)"),
        description=_("When a save would push total usage above this value, the policy below applies. 0 disables enforcement."),
        min=0, required=False,
    )
    over_limit_policy = schema.Choice(
        title=_("Policy when the hard limit is reached"),
        vocabulary="collective.quota.OverLimitPolicies",
        required=False,
    )
    max_file_size_mb = schema.Int(
        title=_("Maximum file size over the limit (MB)"),
        description=_('Only used by the policy "Allow uploads up to a maximum file size".'),
        min=0, required=False,
    )
```

All four records default to `None` ("not set here"). Invariants are **not** declared on
the schema (they would run on raw form data and ignore environment values); the form
validates them on the effective values (see "Control panel" below). Built-in defaults
live in `settings.py`: `DEFAULTS = {"soft_limit_mb": 0, "hard_limit_mb": 0,
"over_limit_policy": "block_all", "max_file_size_mb": 10}`.

Registry: `profiles/default/registry/main.xml`

```xml
<registry>
  <records interface="collective.quota.interfaces.IQuotaSettings" prefix="collective.quota" />
</registry>
```

Uninstall: `profiles/uninstall/registry.xml` with the same `records` element and
`remove="True"`.

### Vocabulary — `vocabularies/policies.py`

Named utility `collective.quota.OverLimitPolicies` (`IVocabularyFactory`) with terms:

| token | title |
|---|---|
| `block_all` | Block new items and any upload that adds bytes |
| `block_files` | Allow new items, block uploads that add bytes |
| `limit_file_size` | Allow uploads up to a maximum file size |
| `allow` | Allow everything, only show warnings |

Also export the tokens as constants from `policy.py` (phase 4 owns that module; this
phase creates it with the constants only).

### Environment variables and resolution — `settings.py`

```python
ENV_PREFIX = "COLLECTIVE_QUOTA_"
ENV_VARS = {
    "soft_limit_mb": "COLLECTIVE_QUOTA_SOFT_LIMIT_MB",
    "hard_limit_mb": "COLLECTIVE_QUOTA_HARD_LIMIT_MB",
    "over_limit_policy": "COLLECTIVE_QUOTA_OVER_LIMIT_POLICY",
    "max_file_size_mb": "COLLECTIVE_QUOTA_MAX_FILE_SIZE_MB",
}
LOCK_VAR = "COLLECTIVE_QUOTA_LOCK_SETTINGS"
TRUTHY = {"1", "true", "yes", "on"}
DEFAULTS = {...}
FIELDS = tuple(ENV_VARS)


@dataclass(frozen=True)
class EnvSettings:
    values: dict[str, int | str]     # only variables that are set and valid
    lock: bool


def read_env(environ=None) -> EnvSettings:
    # int fields: int(value) >= 0 else warn + skip; policy: token in POLICIES else warn + skip
    # empty string == unset; warnings logged once per (var, value) via a module-level set


def is_locked(name: str, env: EnvSettings | None = None) -> bool:
    env = env or read_env()
    return env.lock and name in env.values


def resolve(name, registry_value, env: EnvSettings) -> tuple[value, source]:
    if env.lock and name in env.values:   return env.values[name], "env-locked"
    if registry_value is not None:        return registry_value, "registry"
    if name in env.values:                return env.values[name], "env"
    return DEFAULTS[name], "default"


@dataclass(frozen=True)
class QuotaSettings:
    soft_bytes: int
    hard_bytes: int
    policy: str
    max_file_bytes: int
    sources: dict[str, str]          # field -> "env-locked" | "registry" | "env" | "default"
    locked: frozenset[str]
    values: dict[str, int | str]     # field -> effective value in MB / policy token (for UIs)


def resolve_all(registry_values, env) -> dict[str, tuple[value, source]]
def find_violations(resolved) -> list[tuple[message, fields]]
    # soft > hard (only when both > 0; 0 = disabled never conflicts);
    # limit_file_size with max_file_size_mb == 0
def invariant_errors(resolved) -> list[message]
    # only violations involving a field whose source is "registry": conflicts coming
    # purely from the environment/defaults belong to the operator and are not errors
def set_registry_value(name, value)
    # IRegistry[...] = value; plone.api.portal.set_registry_record refuses None


def get_registry_values() -> dict[str, int | str | None]:
    # api.portal.get_registry_record(f"collective.quota.{name}", default=None) for each field;
    # all None when the records do not exist (add-on not installed)


def get_settings() -> QuotaSettings:
    env = read_env()
    reg = get_registry_values()
    resolved = resolve_all(reg, env)
    # each find_violations() entry is logged once as a warning (values still applied)
    return QuotaSettings(
        soft_bytes=mb_to_bytes(resolved["soft_limit_mb"][0]), ...,
        sources={n: src for n, (_, src) in resolved.items()},
        locked=frozenset(n for n in FIELDS if is_locked(n, env)),
    )
```

`usage.py` re-exports `get_settings` and `QuotaSettings` so phase 2 callers keep working.

Operational notes for docs: variables are read from the process environment of the
Zope instance (`docker-compose.yml` `environment:`, systemd unit, or the shell that
runs `make start`). `instance.yaml`/`zope.conf` need no changes.

### Control panel — `controlpanels/quota.py`

```python
class QuotaControlPanelForm(RegistryEditForm):
    schema = IQuotaSettings
    schema_prefix = "collective.quota"
    label = _("Quota settings")
    description = _("Limits apply to the bytes stored in file and image fields across the whole site.")


class QuotaControlPanel(ControlPanelFormWrapper):
    form = QuotaControlPanelForm
    index = ViewPageTemplateFile("../browser/templates/controlpanel.pt")

    def usage(self) -> UsageInfo: ...
    def can_rebuild(self) -> bool: ...   # ManageSettings; always True here, kept for template clarity
```

Form behaviour with environment values and the lock:

```python
class QuotaControlPanelForm(RegistryEditForm):
    buttons = RegistryEditForm.buttons.copy()      # keep Save/Cancel when adding Reset
    handlers = RegistryEditForm.handlers.copy()

    def updateFields(self):
        super().updateFields()
        self.quota_settings = get_settings()
        for name in self.quota_settings.locked:
            self.fields[name].mode = DISPLAY_MODE  # before the widgets are built

    def updateWidgets(self):
        super().updateWidgets()
        for name in FIELDS:
            widget = self.widgets[name]
            if name in settings.locked:
                widget.value = IDataConverter(widget).toWidgetValue(<env value>)
            widget.description = field description + " " + source_note(...)
            # e.g. "Currently: 500 MB (from environment variable COLLECTIVE_QUOTA_HARD_LIMIT_MB; a value saved here takes precedence)."
            # Plone's widget.pt renders descriptions only in input mode: for locked
            # fields the source is shown in the sources table above the form.

    def extractData(self, setErrors=True):
        data, errors = super().extractData(setErrors)
        resolved = resolve_all(get_registry_values() | data, read_env())
        for message in invariant_errors(resolved):
            errors += (IErrorViewSnippet for Invalid(message),)   # form-level error
        self.widgets.errors = errors   # when setErrors
        return data, errors

    def applyChanges(self, data):
        for name in get_settings().locked:
            data.pop(name, None)             # never write locked fields
        return super().applyChanges(data)

    @button.buttonAndHandler(_("Reset to defaults"), name="reset")
    def handle_reset(self, action):
        # set_registry_value(name, None) for every non-locked field (a locked
        # field's stored value is left alone), status message, redirect
```

Invariant messages: "The soft limit cannot be higher than the hard limit." and
"Set a maximum file size greater than 0 for this policy."

`controlpanel.pt` extends the standard control panel wrapper layout (`prefs_main_template`
macro in Plone 6 Classic) and adds, above the form:

- Usage card: total (human readable), hard/soft limits, percent progress bar
  (`progress-bar bg-success|bg-warning|bg-danger` by level), active policy title.
- Sources table: one row per setting with effective value and source badge
  (`Control panel`, `Environment`, `Environment (locked)`, `Default`) and the variable
  name. When `COLLECTIVE_QUOTA_LOCK_SETTINGS` is on, an info alert explains that locked
  values can only be changed by the operator.
- Link "Review biggest items" → `@@quota-usage` (phase 5; render the link only if the
  view is traversable: `context.restrictedTraverse("@@quota-usage", None)`).
- Form (POST to `@@quota-rebuild`, with `authenticator`) and button "Rebuild usage data"
  with help text explaining it walks the whole catalog.

Registration:

- `controlpanels/configure.zcml`: `<browser:page name="quota-controlpanel"
  for="plone.base.interfaces.IPloneSiteRoot" class=".quota.QuotaControlPanel"
  permission="collective.quota.ManageSettings" layer="..IBrowserLayer" />`
- `profiles/default/controlpanel.xml`:

```xml
<object name="portal_controlpanel">
  <configlet title="Quota" action_id="collective-quota" appId="collective.quota"
             category="Products" condition_expr="" icon_expr="string:device-hdd"
             url_expr="string:${portal_url}/@@quota-controlpanel" visible="True">
    <permission>collective.quota: Manage Quota Settings</permission>
  </configlet>
</object>
```

  Implemented with `icon_expr="string:device-hdd"` (Bootstrap icon shipped by
  `plone.staticresources`; verified rendering in Site Setup). The configlet title is
  translatable (`i18n:attributes="title"`).

- `profiles/uninstall/controlpanel.xml`: `<configlet action_id="collective-quota" remove="True" />`.

### REST control panel — `controlpanels/restapi.py`

```python
@adapter(Interface, IQuotaRestapiLayer)
class QuotaConfigletPanel(RegistryConfigletPanel):
    schema = IQuotaSettings
    schema_prefix = "collective.quota"
    configlet_id = "collective-quota"
    configlet_category_id = "Products"
    title = _("Quota")
    group = "Products"
```

Registered as `<adapter factory=".restapi.QuotaConfigletPanel" name="collective-quota"
provides="plone.restapi.controlpanels.interfaces.IControlpanel" />`. Permission is
inherited from the configlet (`ManageSettings`).

The adapter class also implements the marker `IQuotaControlpanel(IControlpanel)`
(`interfaces.py`), so the serializer and deserializer below are registered for it and
win over plone.restapi's generic `IControlpanel` ones.

- `GET` (`QuotaControlpanelSerializeToJson`, subclass of plone.restapi's
  `ControlpanelSerializeToJson`): standard `schema` + `data`, where `data` is what the
  control panel **stores** (`null` = unset), like the Classic form. Locked fields show
  their environment value in `data` (rendered with the DX field serializers, so the
  policy is `{"token", "title"}` like any Choice) and get `"readonly": true` in their
  schema property. Extra top-level keys: `effective` (values in use, MB / token),
  `sources` (`{"hard_limit_mb": "env-locked", ...}`) and `locked` (sorted list).
- `PATCH` (`QuotaControlpanelDeserializeFromJson`): a locked field sent with a value
  **different** from its locked value → `400` "Setting X is locked by environment
  variable Y"; sending the locked value itself is ignored (clients often send the whole
  form) and never written. Other fields are deserialized and validated, then the
  invariants are checked on the effective values; only when everything passes are the
  values written. Errors use plone.restapi's usual `BadRequest([...])` shape.

## Files

Create:
- `backend/src/collective/quota/settings.py`
- `backend/src/collective/quota/vocabularies/policies.py`
- `backend/src/collective/quota/policy.py` (constants only in this phase)
- `backend/src/collective/quota/controlpanels/quota.py`
- `backend/src/collective/quota/controlpanels/restapi.py`
- `backend/src/collective/quota/browser/templates/controlpanel.pt`
- `backend/src/collective/quota/profiles/uninstall/registry.xml`
- `backend/src/collective/quota/profiles/uninstall/controlpanel.xml`
- `backend/tests/test_settings.py`, `test_env_settings.py`, `test_controlpanel.py`, `test_controlpanel_restapi.py`

Modify:
- `backend/src/collective/quota/interfaces.py`
- `backend/src/collective/quota/usage.py` (re-export `get_settings`, `QuotaSettings`)
- `backend/src/collective/quota/vocabularies/configure.zcml`
- `backend/src/collective/quota/controlpanels/configure.zcml`
- `backend/src/collective/quota/profiles/default/registry/main.xml`
- `backend/src/collective/quota/profiles/default/controlpanel.xml`
- `backend/src/collective/quota/browser/rebuild.py` (redirect target → control panel,
  unconditionally: both views live on the same layer)

## Tasks

- [x] `IQuotaSettings` with optional fields (registry default `None`), i18n strings
- [x] Registry records in default profile; removal in uninstall profile
- [x] Vocabulary utility + ZCML
- [x] `policy.py` constants `BLOCK_ALL`, `BLOCK_FILES`, `LIMIT_FILE_SIZE`, `ALLOW`, `POLICIES`
- [x] `settings.py`: `ENV_VARS`, `LOCK_VAR`, `read_env` (validation + once-per-value warnings), `resolve`, `is_locked`, `get_registry_values`, `get_settings`, `DEFAULTS`
- [x] Control panel form: locked fields in display mode, source notes, effective-value invariants, `applyChanges` skipping locked fields, "Reset to defaults" button
- [x] Control panel template: usage card, sources table, lock alert, rebuild form
- [x] `controlpanel.xml` default + uninstall
- [x] REST `IControlpanel` adapter with `sources`/`locked` in GET and locked-field rejection in PATCH
- [x] Document the variables in `backend/README.md` and add commented examples to `docker-compose.yml` (the compose stack was later removed; the README examples stay)
- [x] Manual check in a running site: Site Setup → Add-on Configuration → Quota; save values; rebuild and reset buttons; invariants shown as errors; start the instance with `COLLECTIVE_QUOTA_HARD_LIMIT_MB=100 COLLECTIVE_QUOTA_LOCK_SETTINGS=1` and confirm the field is read-only and REST PATCH is refused
- [x] `set_quota(soft_mb=0, hard_mb=0, policy="block_all", max_file_mb=10)` fixture in `tests/conftest.py` writing the four registry records (moved here from phase 1); switch `quota_env` to `collective.quota.settings.ENV_VARS` / `LOCK_VAR` instead of the `QUOTA_ENV_VARS` copy in `conftest.py`
- [x] `make i18n`; `make lint`; coverage 100 %

## Tests

- [x] `test_fixtures.py::test_set_quota_writes_all_records` (moved from phase 1)
- [x] `test_settings.py::test_records_default_to_none_after_install`
- [x] `test_settings.py::test_builtin_defaults_when_nothing_set` — `0`, `0`, `block_all`, `10 MB`; all sources `default`
- [x] `test_settings.py::test_get_settings_converts_mb_to_bytes`
- [x] `test_settings.py::test_get_settings_without_records_is_safe` — uninstall → defaults, no exception
- [x] `test_settings.py::test_registry_none_treated_as_unset`
- [x] `test_settings.py::test_vocabulary_terms`
- [x] `test_env_settings.py::test_env_values_used_when_registry_unset` — each of the four variables; sources `env`
- [x] `test_env_settings.py::test_registry_overrides_env_when_not_locked` — sources `registry`
- [x] `test_env_settings.py::test_lock_makes_env_win_over_registry` — sources `env-locked`, `locked` contains the field
- [x] `test_env_settings.py::test_lock_without_env_value_leaves_field_editable`
- [x] `test_env_settings.py::test_lock_truthy_values` — parametrised over `1/true/TRUE/yes/on/0/false/""/garbage`
- [x] `test_env_settings.py::test_invalid_int_and_policy_logged_and_ignored` — `caplog` shows one warning per value, repeated calls do not re-log
- [x] `test_env_settings.py::test_empty_string_is_unset`
- [x] `test_env_settings.py::test_negative_int_ignored`
- [x] `test_controlpanel.py::test_requires_manage_permission` — Editor → `Unauthorized`; Site Administrator OK
- [x] `test_controlpanel.py::test_save_values` — functional browser: fill soft 100, hard 200, policy `block_files`, save → registry updated
- [x] `test_controlpanel.py::test_invariant_soft_above_hard` — error message rendered, registry unchanged
- [x] `test_controlpanel.py::test_invariant_max_file_required`
- [x] `test_controlpanel.py::test_invariants_use_effective_values` — env hard 100 locked, form soft 200 → error
- [x] `test_controlpanel.py::test_locked_field_rendered_display_mode_with_source_note`
- [x] `test_controlpanel.py::test_locked_field_not_written_even_if_posted` — craft a POST including the locked field → registry unchanged
- [x] `test_controlpanel.py::test_unlocked_fields_still_saved_when_lock_flag_on`
- [x] `test_controlpanel.py::test_sources_table_and_lock_alert`
- [x] `test_controlpanel.py::test_reset_to_defaults_clears_non_locked_records`
- [x] `test_controlpanel.py::test_usage_card_shows_total_and_level` — with 2 files and limits set, the card shows human-readable total and `warning` styling
- [x] `test_controlpanel.py::test_rebuild_button_posts_to_rebuild_view`
- [x] `test_controlpanel.py::test_configlet_listed_in_site_setup` — `portal_controlpanel` has `collective-quota`
- [x] `test_controlpanel_restapi.py::test_get` — `GET @controlpanels/collective-quota` → schema + data
- [x] `test_controlpanel_restapi.py::test_patch` — `PATCH` hard limit → registry updated; Editor → 401/403
- [x] `test_controlpanel_restapi.py::test_listed` — `GET @controlpanels` includes `collective-quota`
- [x] `test_controlpanel_restapi.py::test_get_exposes_effective_values_sources_and_locked`
- [x] `test_controlpanel_restapi.py::test_patch_locked_field_rejected_400_nothing_written`
- [x] `test_controlpanel_restapi.py::test_patch_invariants_on_effective_values`

## Acceptance criteria

- A Site Administrator can set and save limits in Classic UI, sees the current usage
  and where each value comes from, and can trigger a rebuild or a reset from the same page.
- Setting `COLLECTIVE_QUOTA_*` variables configures the add-on without touching the
  control panel; with `COLLECTIVE_QUOTA_LOCK_SETTINGS=1` neither the Classic form nor
  REST can change those values.
- Invalid combinations are rejected with clear messages.
- Uninstall removes the configlet and the registry records.

## Notes / risks

Implementation notes (2026-10-15):

- **REST `data` holds stored values, not effective ones.** The draft said `data` would
  be the effective values. A client that loads `data` and sends it back on save (the
  Volto control panel does) would then copy environment values and built-in defaults
  into the registry, freezing them: later changes to the environment would no longer
  apply. `data` therefore mirrors the Classic form (stored values, locked fields show
  the environment value) and the effective values are in a separate `effective` key.
  For the same reason PATCH ignores a locked field sent with its locked value and only
  refuses a different value.
- **Invariants only block what the admin is saving.** An environment-only conflict
  (e.g. `SOFT=200 HARD=100`, nothing in the registry) is logged once by
  `get_settings()` and applied, per §3.3; without the "involves a registry value" rule
  it would also block every save of unrelated fields. A limit of `0` is disabled and
  never conflicts (`soft=500, hard=0` is valid).
- `QuotaSettings.values` (effective MB / token per field) was added for the control
  panel and REST; `resolve_all`, `find_violations`, `invariant_errors`,
  `set_registry_value`, `REGISTRY_PREFIX`, `INT_FIELDS` and the `SOURCE_*` constants
  live in `settings.py` so the form and the REST adapter share one implementation.
- `plone.api.portal.set_registry_record` refuses `None`; resetting and the `set_quota`
  fixture write through `IRegistry` (`set_registry_value`).
- Plone's `widget.pt` renders descriptions only in input mode, so locked (display mode)
  fields show their source in the sources table, not under the field.
- Tests: `make_file` no longer depends on the integration `portal` fixture, so it works
  on the functional layer. `stored_settings()` reads committed registry values on a
  fresh ZODB connection: the test's own connection does not see commits made by the
  HTTP server thread used by `api_session`.
- Manual check on a running instance (port 8091, temporary site, deleted afterwards):
  configlet with icon in Site Setup for a Site Administrator, Editor redirected; both
  invariants shown as form errors; save, usage card (3.0 MB of 10 MB, warning, 30 %),
  rebuild (POST → back to the panel with the message; GET → 405) and reset work.
  Restarted with `COLLECTIVE_QUOTA_HARD_LIMIT_MB=100 COLLECTIVE_QUOTA_LOCK_SETTINGS=1
  COLLECTIVE_QUOTA_OVER_LIMIT_POLICY=bogus`: hard limit read-only with lock alert, a
  crafted POST did not change it while other fields saved, REST PATCH of the locked
  field → 400, soft 200 over the locked hard 100 → 400, reset kept the lock, and the
  invalid policy was logged once.


- `RegistryEditForm` renders `Int` fields with `required=False` as optional; empty
  input is stored as `None`, which now means "unset" and falls through to env/default.
- Display-mode widgets are not extracted by z3c.form, so `applyChanges` would never
  see locked fields anyway; the explicit `pop` guards against crafted POSTs that switch
  the widget mode. Test it.
- The usage card must not break when the index is missing (fresh install before
  `post_install`, or after a partial uninstall): `get_usage_info()` returns zeros.
