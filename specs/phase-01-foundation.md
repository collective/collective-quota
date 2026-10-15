# Phase 1 — Foundation: package cleanup, permissions, layers, test fixtures

Status: Not started
Depends on: —
Last updated: 2026-10-15

## Goal

Turn the cookieplone scaffold into a Classic-first add-on skeleton with the permissions,
browser layers, shared helpers, and test fixtures every later phase builds on. No quota
behaviour yet.

## Scope

In: dependency cleanup, permissions + rolemap, second browser layer, `utils.py`,
`browser/` and `restapi/` packages (empty registrations), test fixtures (sample content
factories, a multi-blob test type, settings helper, environment helper), the 100 %
coverage gate, CI sanity.

Out: index, settings, views (phases 2+).

## Design

### Dependencies

`plone.volto` is removed from the runtime dependencies, from `dependencies.zcml`, and
from `profiles/default/metadata.xml`. Reason: installing `plone.volto:default` on a
Classic site changes site behaviour (blocks-based types, Volto settings). The add-on
must work on a plain Classic site. `plone.restapi` stays (REST enforcement and control
panel adapter). The Volto phase will add Volto bits in a separate extra/profile.

`backend/pyproject.toml` after this phase:

```toml
dependencies = [
    "Products.CMFPlone",
    "plone.api",
    "plone.app.linkintegrity",
    "plone.namedfile",
    "plone.restapi",
]
```

(`plone.app.linkintegrity` and `plone.namedfile` are part of Plone, listed explicitly
because the code imports from them.)

`dependencies.zcml`: keep `<include package="plone.restapi" />`, drop `plone.volto`.
`profiles/default/metadata.xml`: `<version>1000</version>`, dependencies
`profile-plone.app.registry:default` only (already present in Plone; harmless and explicit).

### Permissions

`permissions.zcml`:

```xml
<permission id="collective.quota.ManageSettings" title="collective.quota: Manage Quota Settings" />
<permission id="collective.quota.ViewDiskUsage" title="collective.quota: View Disk Usage" />
```

`profiles/default/rolemap.xml`:

```xml
<rolemap>
  <permissions>
    <permission name="collective.quota: Manage Quota Settings" acquire="True">
      <role name="Manager" />
      <role name="Site Administrator" />
    </permission>
    <permission name="collective.quota: View Disk Usage" acquire="True">
      <role name="Manager" />
      <role name="Site Administrator" />
      <role name="Editor" />
      <role name="Contributor" />
      <role name="Reviewer" />
    </permission>
  </permissions>
</rolemap>
```

### Browser layers

`interfaces.py`:

```python
from plone.restapi.interfaces import IPloneRestapiLayer
from zope.publisher.interfaces.browser import IDefaultBrowserLayer


class IBrowserLayer(IDefaultBrowserLayer):
    """Classic UI layer."""


class IQuotaRestapiLayer(IPloneRestapiLayer):
    """REST layer: overrides of plone.restapi adapters are registered for it."""
```

`profiles/default/browserlayer.xml` registers both (`collective.quota`,
`collective.quota.restapi`); `profiles/uninstall/browserlayer.xml` removes both.

### Shared helpers (`utils.py`)

```python
from plone.base.utils import human_readable_size  # re-export for templates/tests

MB = 1024 * 1024


def mb_to_bytes(value: int | None) -> int:
    return int(value or 0) * MB
```

### Package stubs

- `browser/__init__.py`, `browser/configure.zcml` (namespaces declared, `-*- extra stuff
  goes here -*-` marker), `browser/templates/` folder.
- `restapi/__init__.py`, `restapi/configure.zcml`.
- `catalog/__init__.py`, `catalog/configure.zcml`.
- `configure.zcml` includes `.browser`, `.restapi`, `.catalog` (in addition to the
  existing includes).

### Test fixtures

`testing.py`:

- Keep `PLONE_APP_CONTENTTYPES_FIXTURE` as base, load `plone.restapi` and
  `collective.quota` ZCML, install `collective.quota:default`.
- In `setUpPloneSite`, also register a test-only Dexterity type `quota_multi` with
  schema `collective.quota.testing.IMultiBlobSchema`:

```python
class IMultiBlobSchema(model.Schema):
    title = schema.TextLine(title="Title")
    attachment = NamedBlobFile(title="Attachment", required=False)
    picture = NamedBlobImage(title="Picture", required=False)
    second = NamedBlobFile(title="Second attachment", required=False)
```

  FTI created with `DexterityFTI("quota_multi")`, `klass = plone.dexterity.content.Item`,
  `schema = "collective.quota.testing.IMultiBlobSchema"`, behaviors
  `plone.namefromtitle`, `plone.basic`, `global_allow = True`, `add_permission =
  cmf.AddPortalContent`. This type exercises the "sum of several fields" rule and the
  "blob field in a behavior vs. main schema" path (lead image behavior is also tested
  through `plone.app.contenttypes` Document + `plone.leadimage` behavior enabled in the
  test layer for `Document`).

`backend/tests/conftest.py` additions (plain pytest fixtures, on top of pytest-plone):

```python
MB = 1024 * 1024

@pytest.fixture
def make_blob():
    """make_blob(size_bytes, filename="f.bin", image=False) -> NamedBlobFile/Image"""

@pytest.fixture
def make_file(portal, make_blob):
    """make_file(container, id, size_bytes, type="File") -> created object (via api.content.create, no validation)"""

@pytest.fixture
def make_image(...):  # 1x1 PNG padded with trailing bytes to reach size

@pytest.fixture
def set_quota(portal):
    """set_quota(soft_mb=0, hard_mb=0, policy="block_all", max_file_mb=10) writes the registry"""
```

Note: `make_file` uses `plone.api` on purpose (no validation) so tests can push a site
*over* the limit before testing enforcement.

Functional helpers: `browser` fixture (plone.testing `Browser` logged in as a given
role) and `api_session` fixture (`plone.restapi.testing.RelativeSession` with basic
auth) live in `conftest.py` too; both exist already in pytest-plone / plone.restapi,
only thin wrappers are needed.

### Coverage gate

`backend/pyproject.toml`:

```toml
[tool.coverage.run]
source_pkgs = ["collective.quota", "tests"]
branch = true
parallel = true
omit = ["src/collective/quota/locales/*.py"]

[tool.coverage.report]
fail_under = 100
show_missing = true
skip_covered = false
```

`make test-coverage` already runs `pytest --cov=collective.quota --cov-report term-missing`;
add `--cov-branch --cov-fail-under=100` to the target so the Makefile and the config
agree. The gate is enforced from this phase on: every later phase lands with its tests.
`# pragma: no cover` is forbidden (add a ruff/grep check in `make lint`:
`! grep -rn "pragma: no cover" src/`).

### Environment fixture

```python
@pytest.fixture
def quota_env(monkeypatch):
    """quota_env(soft=None, hard=None, policy=None, max_file=None, lock=None) sets/clears COLLECTIVE_QUOTA_* vars"""
```

It always starts by deleting all five variables so tests never leak host settings, and
`conftest.py` also has an autouse fixture that clears them for every test.

### CI

Confirm `.github/workflows` runs `make lint` and `make test-coverage` for `backend/` on
push (cookieplone ships lint + test; switch the test job to the coverage target).

## Files

Modify:
- `backend/pyproject.toml` (dependencies)
- `backend/src/collective/quota/dependencies.zcml`
- `backend/src/collective/quota/configure.zcml`
- `backend/src/collective/quota/permissions.zcml`
- `backend/src/collective/quota/interfaces.py`
- `backend/src/collective/quota/testing.py`
- `backend/src/collective/quota/profiles/default/metadata.xml`
- `backend/src/collective/quota/profiles/default/browserlayer.xml`
- `backend/src/collective/quota/profiles/default/rolemap.xml`
- `backend/src/collective/quota/profiles/uninstall/browserlayer.xml`
- `backend/tests/conftest.py`
- `backend/tests/setup/test_setup_install.py`, `test_setup_uninstall.py`

Create:
- `backend/src/collective/quota/utils.py`
- `backend/src/collective/quota/browser/{__init__.py,configure.zcml,templates/}`
- `backend/src/collective/quota/restapi/{__init__.py,configure.zcml}`
- `backend/src/collective/quota/catalog/{__init__.py,configure.zcml}`
- `backend/tests/test_permissions.py`

## Tasks

- [ ] Remove `plone.volto` from `pyproject.toml`, `dependencies.zcml`, `metadata.xml`; add `plone.app.linkintegrity`, `plone.namedfile` to dependencies
- [ ] Regenerate the environment (`make clean install` in `backend/`) and confirm the site still creates (`make create-site`)
- [ ] Declare the two permissions in `permissions.zcml`
- [ ] Map default roles in `profiles/default/rolemap.xml`
- [ ] Add `IQuotaRestapiLayer`; register both layers in default and uninstall `browserlayer.xml`
- [ ] Create `utils.py` with `MB`, `mb_to_bytes`, `human_readable_size` re-export
- [ ] Create `browser/`, `restapi/`, `catalog/` sub-packages and include them from `configure.zcml`
- [ ] Add `IMultiBlobSchema` + `quota_multi` FTI and enable `plone.leadimage` on Document in the test layer
- [ ] Add `make_blob`, `make_file`, `make_image`, `set_quota`, `browser`, `api_session` fixtures to `tests/conftest.py`
- [ ] Update install/uninstall tests for the second layer
- [ ] Coverage config (`fail_under = 100`, branch) + `make test-coverage` flags + `pragma: no cover` lint check
- [ ] `quota_env` fixture + autouse env cleanup
- [ ] `make lint` and `make format` clean
- [ ] Verify CI workflow runs backend lint + `make test-coverage`

## Tests

- [ ] `tests/setup/test_setup_install.py`: add-on installed; both layers present; profile version `1000`
- [ ] `tests/setup/test_setup_uninstall.py`: both layers gone after uninstall
- [ ] `tests/test_permissions.py`: both permissions exist on the portal; `Manager`/`Site Administrator` have both; `Editor`, `Contributor`, `Reviewer` have `View Disk Usage` but not `Manage Quota Settings`; `Member` and anonymous have neither
- [ ] `tests/test_fixtures.py`: `quota_multi` can be created with three blobs; `make_file(size)` yields `obj.file.getSize() == size`; `set_quota` writes all four registry records; `quota_env` sets and clears variables
- [ ] `tests/test_utils.py`: `mb_to_bytes(None) == 0`, `mb_to_bytes(3) == 3 * MB`
- [ ] Coverage report at 100 % for the modules that exist after this phase

## Acceptance criteria

- A fresh Classic site (`make create-site`, then install the add-on in Site Setup → Add-ons) installs without errors and without `plone.volto` being installed.
- `make test-coverage` passes at 100 %; `make lint` is clean.
- Role mapping is visible and editable in ZMI → Security.

## Notes / risks

- Removing `plone.volto` changes the cookieplone `create_site.py` script expectations;
  check `backend/scripts/create_site.py` and the `initial` profile (example content was
  exported from a Volto-flavoured site; keep it but make sure it still imports on a
  Classic site, or trim it to a Folder + File + Image sample in phase 7).
- `plone.leadimage` behavior must be enabled on Document in the test layer only, not in
  the product profile.
