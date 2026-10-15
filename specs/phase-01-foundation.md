# Phase 1 — Foundation: package cleanup, permissions, layers, test fixtures

Status: Done
Depends on: —
Last updated: 2026-10-15

## Goal

Turn the cookieplone scaffold into a Classic-first add-on skeleton with the permissions,
browser layers, shared helpers, and test fixtures every later phase builds on. No quota
behaviour yet.

## Scope

In: dependency cleanup, permissions + rolemap, second browser layer, `utils.py`,
`browser/` and `restapi/` packages (empty registrations), test fixtures (sample content
factories, a multi-blob test type, environment helper), the 100 % coverage gate, CI
sanity.

Out: index, settings, views (phases 2+). The `set_quota` registry fixture moved to
phase 3, because the records it writes only exist once `IQuotaSettings` is registered.

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
    "plone.exportimport",
    "plone.namedfile",
    "plone.restapi",
]
```

(`plone.app.linkintegrity`, `plone.exportimport` and `plone.namedfile` are part of Plone,
listed explicitly because the code imports from them; `plone.exportimport` is used by
the `initial` profile's handler and otherwise only arrives through `plone.distribution`.)

`dependencies.zcml`: keep `<include package="plone.restapi" />`, drop `plone.volto`.
`profiles/default/metadata.xml`: `<version>1000</version>`, dependencies
`profile-plone.app.registry:default` and `profile-plone.restapi:default`.

Why `plone.restapi:default`: a plain Classic site created with `Products.CMFPlone`
alone (no distribution) does **not** install it, so `plone.restapi: Use REST API` is
granted to nobody but Manager and the restapi browser layer is missing. Our
`IQuotaRestapiLayer` subclasses `IPloneRestapiLayer`, so without the dependency the
add-on would half-activate restapi adapters without restapi's own setup. On sites
that already have it, the dependency is a no-op.

`scripts/create_site.py` no longer passes `distribution_name="volto"` (that distribution
came from `plone.volto`; the `classic` distribution lives in `plone.classicui`, which is
not a dependency). It creates the site with
`extension_ids=(plone.app.contenttypes:default,)` instead.

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
    # images: valid 1x1 PNG padded with trailing bytes; ValueError if size < PNG size

@pytest.fixture
def make_file(portal, make_blob):
    """make_file(container, id, size_bytes, type="File") -> created object (via api.content.create, no validation)"""
    # type "File" -> field `file`, type "Image" -> field `image`; runs as Manager

@pytest.fixture
def make_image(make_file):
    """make_image(container, id, size_bytes) -> created Image"""
```

`set_quota` is added in phase 3 (see that phase).

The test layer also loads `plone.exportimport` ZCML so the `initial` profile can be
tested.

Note: `make_file` uses `plone.api` on purpose (no validation) so tests can push a site
*over* the limit before testing enforcement.

Functional helpers: `browser(role="Manager")` (plone.testing `Browser`, basic auth,
`handleErrors = False`) and `api_session(role="Manager")` (pytest-plone's
`request_factory`, a `RelativeSession` on `++api++`) live in `conftest.py` too. Both are
factories: `Manager` uses the site owner, `Anonymous` sends no credentials, any other
role is granted (with `Member`) to the default test user on the functional portal and
committed.

### Coverage gate

`backend/pyproject.toml`:

```toml
[tool.coverage.run]
source_pkgs = ["collective.quota"]
source = ["tests"]
branch = true
parallel = true
omit = ["src/collective/quota/locales/*.py"]

[tool.coverage.report]
fail_under = 100
show_missing = true
skip_covered = false
```

`make test-coverage` runs `pytest --cov --cov-branch --cov-report term-missing
--cov-fail-under=100`. A bare `--cov` (instead of `--cov=collective.quota`) makes
pytest-cov use the configured sources, so `tests/` is measured too (`tests` is not an
importable package, hence `source` rather than `source_pkgs`). The gate is enforced
from this phase on: every later phase lands with its tests.
`# pragma: no cover` is forbidden: `make lint` runs
`if grep -rn "pragma: no cover" src tests; then …; exit 1; fi` (a bare `! grep` line
would not fail the recipe, since bash's `set -e` ignores `!` pipelines).

### Environment fixture

```python
@pytest.fixture
def quota_env(monkeypatch):
    """quota_env(soft=None, hard=None, policy=None, max_file=None, lock=None) sets/clears COLLECTIVE_QUOTA_* vars"""
```

It always starts by deleting all five variables so tests never leak host settings, and
`conftest.py` also has an autouse fixture that clears them for every test. Unknown
keyword arguments raise `TypeError`. The variable names live in `QUOTA_ENV_VARS` in
`conftest.py` until phase 3 adds `collective.quota.settings.ENV_VARS`.

### CI

`.github/workflows/backend.yml` already has a `coverage` job using
`plone/meta/.github/workflows/backend-pytest-coverage.yml@2.x`, which runs
`make test-coverage`, so the gate applies in CI with no workflow change. The lint job
uses plone/meta's `backend-lint.yml` (ruff, pyroma, zpretty, …), not `make lint`, so
the `pragma: no cover` check only runs locally. The `test` matrix lists Plone
`6.2-latest` and `6.1-latest` only (6.0 dropped; see notes).

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
- `backend/Makefile` (coverage flags, `pragma: no cover` check)
- `backend/scripts/create_site.py` (no `volto` distribution)

Create:
- `backend/src/collective/quota/utils.py`
- `backend/src/collective/quota/browser/{__init__.py,configure.zcml,templates/}`
- `backend/src/collective/quota/restapi/{__init__.py,configure.zcml}`
- `backend/src/collective/quota/catalog/{__init__.py,configure.zcml}`
- `backend/tests/test_permissions.py`, `test_fixtures.py`, `test_utils.py`
- `backend/tests/test_scaffold.py` (covers cookieplone code: summary serializer
  metadata, `HiddenProfiles`, `initial` profile)

## Tasks

- [x] Remove `plone.volto` from `pyproject.toml`, `dependencies.zcml`, `metadata.xml`; add `plone.app.linkintegrity`, `plone.exportimport`, `plone.namedfile` to dependencies; add `profile-plone.restapi:default` to `metadata.xml`
- [x] Regenerate the environment (`make clean install` in `backend/`) and confirm the site still creates (`make create-site`); `create_site.py` no longer uses the `volto` distribution
- [x] Declare the two permissions in `permissions.zcml`
- [x] Map default roles in `profiles/default/rolemap.xml`
- [x] Add `IQuotaRestapiLayer`; register both layers in default and uninstall `browserlayer.xml`
- [x] Create `utils.py` with `MB`, `mb_to_bytes`, `human_readable_size` re-export
- [x] Create `browser/`, `restapi/`, `catalog/` sub-packages and include them from `configure.zcml`
- [x] Add `IMultiBlobSchema` + `quota_multi` FTI and enable `plone.leadimage` on Document in the test layer
- [x] Add `make_blob`, `make_file`, `make_image`, `browser`, `api_session` fixtures to `tests/conftest.py` (`set_quota` moved to phase 3)
- [x] Update install/uninstall tests for the second layer
- [x] Coverage config (`fail_under = 100`, branch) + `make test-coverage` flags + `pragma: no cover` lint check
- [x] `quota_env` fixture + autouse env cleanup
- [x] `make lint` and `make format` clean
- [x] Verify CI workflow runs backend lint + `make test-coverage`

## Tests

- [x] `tests/setup/test_setup_install.py`: add-on installed; both layers present; profile version `1000`; `plone.restapi` installed; `plone.volto` not installed
- [x] `tests/setup/test_setup_uninstall.py`: both layers gone after uninstall
- [x] `tests/test_permissions.py`: both permissions exist on the portal; `Manager`/`Site Administrator` have both; `Editor`, `Contributor`, `Reviewer` have `View Disk Usage` but not `Manage Quota Settings`; `Member` and anonymous have neither
- [x] `tests/test_fixtures.py`: `quota_multi` can be created with three blobs; `make_file(size)` yields `obj.file.getSize() == size`; `make_image` yields a valid 1x1 image of the requested size; `quota_env` sets and clears variables; `browser`/`api_session` authenticate as Manager, another role, and Anonymous
- [x] `tests/test_scaffold.py`: summary serializer metadata, `HiddenProfiles`, `initial` profile imports
- [x] `tests/test_utils.py`: `mb_to_bytes(None) == 0`, `mb_to_bytes(3) == 3 * MB`
- [x] Coverage report at 100 % for the modules that exist after this phase

## Acceptance criteria

- A fresh Classic site (`make create-site`, then install the add-on in Site Setup → Add-ons) installs without errors and without `plone.volto` being installed.
- `make test-coverage` passes at 100 %; `make lint` is clean.
- Role mapping is visible and editable in ZMI → Security.

## Notes / risks

Implementation notes (2026-10-15):

- Verified on a running instance: `make create-site` builds a Classic site with no
  `plone.volto` profile; installing through the Add-ons installer on a bare
  `Products.CMFPlone` site also pulls in `plone.restapi:default`, and uninstall works.
- The Volto-exported example content still imports on Classic, but
  `/images/plone-foundation.png` is dropped (`/images` is a non-folderish Document on
  Classic). Phase 7 regenerates the example content.
- CI's `test` matrix included Plone `6.0-latest`, while the classifiers list only 6.1 and
  6.2, and `plone.exportimport` (already imported by the scaffold) does not exist for 6.0.
  6.0 was dropped from the matrix.
- `make lint`'s `check-python-versions` reports that `requires-python = ">=3.11"` is
  open-ended while the classifiers stop at 3.13. It is only a warning (exit 0) and comes
  from the scaffold; phase 7 can tidy it up.

Original risks:

- Removing `plone.volto` changes the cookieplone `create_site.py` script expectations;
  check `backend/scripts/create_site.py` and the `initial` profile (example content was
  exported from a Volto-flavoured site; keep it but make sure it still imports on a
  Classic site, or trim it to a Folder + File + Image sample in phase 7).
- `plone.leadimage` behavior must be enabled on Document in the test layer only, not in
  the product profile.
