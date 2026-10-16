# Phase 9 — Volto add-on (`volto-collective-quota`)

Status: Not started
Depends on: Phase 8 (services and expander; the JSON in that file is the contract)
Last updated: 2026-10-16

## Goal

Give Volto sites the same features Classic has: a "Disk usage" entry in the user menu,
a warning banner for editors when a limit is near or reached, a biggest-items page with
multi-delete and link-integrity confirmation, and a control panel that explains where
each value comes from and offers "Rebuild usage data". Target: Volto 19.5 (the version
pinned in `frontend/mrs.developer.json`), React 18, react-router 5, semantic-ui-react.

## Scope

In: the add-on package under `frontend/packages/volto-collective-quota`, its
configuration, components, redux slice, i18n, unit tests, Cypress acceptance tests, CI
wiring, README, changelog, release checklist.

Out: changes to the backend (phase 8 covers them), Volto 18 support, theming beyond the
minimal CSS needed for the page and banner.

## Product rules (see `00-architecture.md` §1.1)

1. **Only relevant people, never anonymous.** Every piece of UI renders only when
   `state.userSession.token` is set **and** the backend said yes: the user-menu entry
   needs the `disk-usage` action in `@actions` (user category), the banner needs the
   `quota` expansion to be present, the page needs a `200` from `@quota-usage`. Nothing
   is decided client-side from roles or guesses.
2. **No limits, no noise.** If `limits_configured` is `false`, the banner never renders
   (level is always `ok` anyway), the page shows the total and the listing with a short
   "No limits are configured" note (plus the control panel link for managers), and no
   progress bar or policy text appears. The usage page is then the whole product.
3. **Either half alone.** The backend never needs this package. This package needs the
   backend add-on installed: when `@quota-usage` returns `404` the page shows
   "collective.quota is not installed on the backend" and the other pieces stay hidden
   on their own (no action, no expansion).

## Design

### Package and configuration (`src/index.ts`)

`package.json`: keep `"addons": []` and no runtime `dependencies`; react, react-intl,
react-redux, react-router-dom, semantic-ui-react and react-toastify all come through
`@plone/volto`. Volto add-ons do not declare `@plone/volto` as a peer dependency; the
README states the minimum version (19.x).

```ts
export default function applyConfig(config: ConfigType) {
  // 1. Banner data on every content request Volto already makes.
  config.settings.apiExpanders = [
    ...config.settings.apiExpanders,
    { match: '', GET_CONTENT: ['quota'] },
  ];

  // 2. Banner above everything, on every route, except the two pages that show the
  //    summary themselves (same rule as the Classic viewlet).
  config.registerSlotComponent({
    slot: 'aboveApp',
    name: 'collective-quota-banner',
    component: QuotaBanner,
    predicates: [notOnRoutes(['/quota-usage', '/controlpanel/collective-quota'])],
  });

  // 3. User menu entry (Plug into Volto's "toolbar-user-menu" pluggable).
  config.settings.appExtras = [
    ...config.settings.appExtras,
    { match: '', component: UserMenuEntry },
  ];

  // 4. Routes: both are CMS-UI, non-content routes. Add-on routes win over Volto's
  //    `/controlpanel/:id`, which is how the custom control panel takes over.
  config.addonRoutes = [
    ...config.addonRoutes,
    { path: '/quota-usage', component: QuotaUsage, exact: true },
    { path: '/controlpanel/collective-quota', component: QuotaControlpanel, exact: true },
  ];
  config.settings.nonContentRoutes = [
    ...config.settings.nonContentRoutes,
    /\/quota-usage$/,
  ];

  // 5. State.
  config.addonReducers = { ...config.addonReducers, quota: quotaReducer };

  // 6. Icon in Site Setup (keyed by control panel id).
  config.settings.controlPanelsIcons = {
    ...config.settings.controlPanelsIcons,
    'collective-quota': serverSVG,   // @plone/volto/icons/server.svg
  };
  return config;
}
```

`notOnRoutes(paths)` is a slot predicate `({ location }) => !paths.some((p) =>
location?.pathname?.startsWith(p))` in `src/helpers/predicates.ts`. (`/controlpanel/.*`
is already a non-content route in Volto.)

### Redux slice (`src/actions/quota.ts`, `src/reducers/quota.ts`)

Actions go through Volto's API middleware, so paths are relative to the API root:

| Action | Request | State |
|---|---|---|
| `getQuotaUsage(limit = 25)` | `GET /@quota-usage?limit=N` | `quota.usage: {loading, loaded, error, data}` |
| `rebuildQuota()` | `POST /@quota-rebuild` | `quota.rebuild: {loading, loaded, error, data}` |
| `deleteQuotaItems(urls)` | Volto's `deleteContent(urls)` (serial `DELETE`), re-exported | `state.content.delete` (Volto) |
| link-integrity preview | Volto's `linkIntegrityCheck(uids)` | `state.linkIntegrity` (Volto) |

Reducer shape mirrors Volto's `{loading, loaded, error}` convention. `error` keeps
`status` so the page can tell `401`, `403` and `404` apart.

### User menu entry (`src/components/UserMenuEntry/UserMenuEntry.jsx`)

```jsx
const action = useSelector((s) => s.actions?.actions?.user?.find((a) => a.id === 'disk-usage'));
if (!token || !action) return null;
return (
  <Plug pluggable="toolbar-user-menu" id="collective-quota-disk-usage">
    <li>
      <Link to="/quota-usage">
        {action.title /* "Disk usage", translated by the backend */}
        <Icon name={rightArrowSVG} size="24px" />
      </Link>
    </li>
  </Plug>
);
```

Rendered from `appExtras` (inside `PluggablesProvider`), so the `<li>` appears in the
personal tools menu right after "Site Setup". The action's `url` (a backend URL to
`@@quota-usage`) is ignored on purpose; the route is the Volto page.

### Banner (`src/components/QuotaBanner/QuotaBanner.jsx`)

Slot `aboveApp` (Volto renders it before the header on every route, inside the
`PluggablesProvider`). Reads `content['@components']?.quota` from the slot's `content`
prop; renders nothing unless `token` is set, the key exists, and `level` is `warning`
or `exceeded`:

```jsx
<Message warning|negative id="collective-quota-banner" data-level={level} className="collective-quota-banner">
  <Container>
    <p>{quota.message}</p>                           {/* backend text, already translated */}
    <Link className="ui button basic small" to="/quota-usage">{intl.formatMessage(messages.review)}</Link>
  </Container>
</Message>
```

- No client-side thresholds: the backend computes `level` and `message`
  (`summary.level_message`), so the two UIs can never disagree.
- Not dismissible (parity with Classic; it disappears when usage drops).
- On non-content routes (`/contents`, `/controlpanel/...`) `content` is the last fetched
  content, so the banner still reflects the latest known level; it hides on the two
  summary pages through the slot predicate.
- Minimal CSS in `src/components/QuotaBanner/QuotaBanner.css` (full width, no margin
  collapse with the header).

### Disk usage page (`/quota-usage`, `src/components/QuotaUsage/QuotaUsage.jsx`)

Structure (semantic-ui, same skeleton as Volto's `Controlpanel.jsx`: `Helmet`,
`Container`, toolbar via portal into `#toolbar` with `hideDefaultViewButtons` and a
back button):

```
h1 "Disk usage"
Segment  usage summary
   "Total: 3.4 GB of 5.0 GB (68 %)"   Progress bar coloured by level (green/yellow/red)
   "Soft limit: 4.0 GB · Hard limit: 5.0 GB · Policy: <policy_title>"   (only when limits_configured)
   "No limits are configured. Only the listing below is available."       (when not)
   [Quota settings] → /controlpanel/collective-quota   (can_manage)
   [Rebuild usage data]                                (can_manage; POST @quota-rebuild; toast with item count; refetch)
Message warning|negative with `message` (level ≠ ok)
Toolbar row: "Show" limit selector (10/25/50/100 as a button group; updates the query string ?limit=)  ·  "Delete selected (n)" (disabled until a selection exists)
Table (celled, striped) — header checkbox "select all deletable"
   Checkbox (disabled + title "You cannot delete this item" when !can_delete)
   Title → Link to flattenToAppURL(@id)    Type    Location → Link to parent    Size (title = exact bytes)    Modified (FormattedDate)    Actions: Edit → `${path}/edit`
p.discreet "Sizes include only uploaded files and images. Showing the N largest items you can see."
```

Behaviour:

- Fetch on mount and when `limit` changes (`?limit=` in the URL so it is shareable and
  survives reload; `parse_limit` on the server makes bad values safe).
- `401` → `<Redirect to={`/login?return_url=${pathname}`} />`; `403` → Volto's
  `Unauthorized`; `404` → the "not installed on the backend" message (rule 3).
- Dates: `FormattedDate` from Volto with the long format used by the Contents view.
- After delete or rebuild: refetch with the same limit, clear the selection.

### Delete modal (`src/components/QuotaUsage/DeleteModal.jsx`)

Modeled on Volto's `ContentsDeleteModal` (same `Confirm`, same message ids so Volto's
translations apply: "Delete selected items?", "link-integrity: Delete item and break
links", the broken-references and contained-items sentences), but written here because
the core modal is coupled to folder contents (it assumes `items[].Title` and shows
"delete all items in this folder" when every listed item is selected).

Flow:

1. Open → dispatch `linkIntegrityCheck(selectedUIDs)`; show the selected titles and,
   from `state.linkIntegrity.result`, the breaches whose source is not itself selected
   and the total of contained items (same filtering as the core modal; at most 10
   breaches listed, then "and N more", with the "Links and references" link).
2. Confirm → `deleteContent(selectedIds)` (serial). Remember `total` before.
3. On success → refetch; toast `Deleted {count} items, freeing {size}` where `size` is
   `human(before.total - after.total)` (so folders' contents count, like Classic).
4. On a per-item failure (locked by someone else, or a race) → toast error listing the
   titles that failed; still refetch so the table is accurate.

`human(bytes)` lives in `src/helpers/format.ts` and mirrors `plone.base.utils.human_readable_size`
(1 KB = 1024 B, one decimal) so the toast matches the backend's numbers; unit-tested
against the same examples.

### Control panel (`/controlpanel/collective-quota`, `src/components/QuotaControlpanel/QuotaControlpanel.jsx`)

Volto would already render the generic form for `@controlpanels/collective-quota`. The
custom route keeps that form (Volto's `Form` with `getControlpanel`/`updateControlpanel`
and the exact error handling of `Controlpanel.jsx`, including invariant errors in a
toast) and adds what the Classic panel has:

- A usage `Segment` at the top (same component as the page summary, without buttons),
  fed by `getQuotaUsage(10)`; "Rebuild usage data" button (`rebuildQuota`, toast, refetch).
- Per-field provenance from the control panel payload's top-level `sources`, `effective`
  and `locked`: for each field the description is suffixed with "Current value: X
  (from control panel | from environment | default)"; locked fields are rendered
  disabled: the schema's `readonly: true` (set by the phase 3 adapter) is mapped to
  `isDisabled: true` on that property before the schema reaches Volto's `Form`, because
  Volto's widgets honour `isDisabled`/`disabled`, not `readonly`. Their description says
  "Locked by environment variable COLLECTIVE_QUOTA_…" and a `Message` at the top lists
  the locked fields.
- "Reset to defaults" button in the toolbar next to Save and Cancel (same behaviour as
  the Classic button `handle_reset`): after a `Confirm` dialog it PATCHes
  `@controlpanels/collective-quota` with `null` for every field that is **not** in
  `locked` (the backend already accepts `null`, phase 3 test
  `test_patch_null_clears_value`, and refuses locked fields), then refetches the panel
  and the usage, and toasts "Settings reset. Environment variables or built-in
  defaults apply now." (the backend does not send this text, so the add-on defines it
  in `defineMessages`, same wording as the Classic status message). Fields then show
  their effective value again with source "from environment" or "default". Locked
  fields are untouched and the confirmation text says so when any exist.

Permission: the backend answers `401/403` to `@controlpanels/collective-quota`; the
component shows `Unauthorized` like Volto does. The Site Setup listing only shows the
panel to users who may see it (plone.restapi filters `@controlpanels`).

### i18n

`make i18n` in `frontend/` extracts to `locales/volto.pot` and syncs `de`, `en`, `es`,
`pt_BR`. Translate `en` and `es` fully (same policy as the backend). Strings that come
from the backend (`message`, `policy_title`, `policy_hint`, action title, control panel
labels) are **not** duplicated in the add-on.

### Styling

One small stylesheet per component (`QuotaBanner.css`, `QuotaUsage.css`) imported from
the component; semantic-ui classes for everything else. No theme, `"theme": ""` stays.

### Tests

Unit (vitest, `make test`, run in CI by `frontend-unit.yml`):

- `src/reducers/quota.test.ts` — pending/success/fail transitions, `error.status` kept.
- `src/helpers/format.test.ts` — `human()` against the backend's examples (0 B, 1023 B,
  1.0 KB, 2.0 MB, 3.4 GB).
- `src/helpers/predicates.test.ts` — `notOnRoutes`.
- `src/components/QuotaBanner/QuotaBanner.test.jsx` — nothing without token; nothing when
  `@components.quota` is absent; nothing for level `ok`; renders warning / negative with
  the backend message and the link.
- `src/components/UserMenuEntry/UserMenuEntry.test.jsx` — hidden without the action,
  shown with it.
- `src/components/QuotaUsage/QuotaUsage.test.jsx` — renders summary + rows from a mocked
  store; "no limits" note when `limits_configured` is false; checkbox disabled when
  `can_delete` is false; 404 message.
- `src/components/QuotaUsage/DeleteModal.test.jsx` — breaches filtered, confirm label
  switches to "break links".
- `src/components/QuotaControlpanel/QuotaControlpanel.test.jsx` — provenance suffixes
  from `sources`; locked field rendered disabled with the lock note; "Reset to
  defaults" dispatches a PATCH with `null` for exactly the non-locked fields.

Coverage: vitest runs with `--coverage` (v8 provider) and a `90 %` lines threshold on
`src/`, excluding `src/index.ts` and `src/config/`, configured in
`vitest.config.mjs`; `make test` fails below it and `frontend-unit.yml` runs it.

Acceptance (Cypress, `frontend/cypress/tests/quota.cy.js`, backend from
`make acceptance-backend-start`, which applies `collective.quota:default`):

- `cy.setRegistry('collective.quota.soft_limit_mb', 1)` and `hard_limit_mb` `2`,
  `over_limit_policy` `allow`; create Files through `cy.createContent` with a generated
  base64 payload (≈ 1.5 MB) so the site crosses the soft limit.
- As admin (`cy.autologin()`): banner visible on `/` and on a folder; user menu has "Disk
  usage"; `/quota-usage` lists the files, biggest first; limit buttons change the rows;
  select two → delete → confirmation lists them → confirm → toast "freeing" → rows gone →
  banner gone.
- Link integrity: a Document linking to a File (slate link in `blocks`), select the File
  → modal shows the breach → confirm → both deleted as expected.
- Anonymous: `cy.visit('/')` without login → no banner, no `#collective-quota-banner`;
  `cy.visit('/quota-usage')` → redirected to login.
- No limits: registry cleared → no banner; `/quota-usage` shows the "No limits" note.
- Control panel: `/controlpanel/collective-quota` shows the usage segment; save soft 1 /
  hard 2; "Rebuild usage data" toasts the item count; "Reset to defaults" → confirm →
  fields show `0` / `block_all` / `10` with source "default" and the banner disappears.

CI: `.github/workflows/frontend.yml` currently runs i18n and unit only. Add an
`acceptance` job (build `backend/Dockerfile.acceptance`, start it, `make
ci-acceptance-test`) following cookieplone's project template; it depends on `unit`.

### Documentation and changelog

- `frontend/README.md`: replace the scaffold "Features" placeholder with the four
  features, the requirement "backend add-on `collective.quota` installed", and the
  rules in "Product rules". Keep the cookieplone installation/development sections.
- `docs/docs/how-to-guides/use-with-volto.md`: install both halves, where things appear
  in Volto (menu, banner, page, control panel), and that the feature set equals Classic.
- `frontend/packages/volto-collective-quota/news/+initial.feature`.
- Root `README.md`: features paragraph mentions Volto.

### Release checklist

- [ ] `frontend/packages/volto-collective-quota/package.json` version `1.0.0-alpha.0` → release-it alpha
- [ ] `make lint`, `make test`, `make i18n` clean in `frontend/`
- [ ] Storybook builds (cookieplone deploys it to GitHub Pages)
- [ ] `make build-images` builds the frontend image with `VOLTO_VERSION` from `repository.toml`
- [ ] Tag + publish to npm — maintainers

## Files

Create (under `frontend/packages/volto-collective-quota/src/` unless noted):
- `actions/quota.ts`, `reducers/quota.ts`, `constants/ActionTypes.ts`
- `helpers/format.ts`, `helpers/predicates.ts`
- `components/QuotaBanner/QuotaBanner.jsx` + `.css`
- `components/UserMenuEntry/UserMenuEntry.jsx`
- `components/QuotaUsage/QuotaUsage.jsx`, `UsageSummary.jsx`, `ItemsTable.jsx`, `DeleteModal.jsx`, `QuotaUsage.css`
- `components/QuotaControlpanel/QuotaControlpanel.jsx`
- the `*.test.*` files listed above
- `frontend/cypress/tests/quota.cy.js`
- `frontend/packages/volto-collective-quota/news/+initial.feature`
- `docs/docs/how-to-guides/use-with-volto.md`

Modify:
- `src/index.ts`, `src/config/settings.ts` (or fold into `index.ts`)
- `locales/**`
- `frontend/README.md`, root `README.md`, `docs/docs/how-to-guides/index.md`
- `.github/workflows/frontend.yml`
- `frontend/cypress/tests/example.cy.js` (delete the scaffold test)

## Tasks

- [ ] `make install` in `frontend/` on a clean checkout (Volto 19.5 via mrs-developer); `make start` against `make acceptance-backend-start`
- [ ] `src/index.ts` configuration (expander, slot, appExtras, routes, reducer, icon)
- [ ] Redux slice + helpers with unit tests
- [ ] User menu entry
- [ ] Banner (slot `aboveApp`, predicate)
- [ ] Disk usage page: summary, limit selector, table, error states
- [ ] Delete modal with link-integrity preview and "freed" toast
- [ ] Control panel with provenance, locked fields, rebuild, "Reset to defaults"
- [ ] vitest coverage threshold (90 % lines) configured and passing
- [ ] i18n extracted; `en` and `es` translated
- [ ] Cypress suite green locally against the acceptance backend
- [ ] CI acceptance job
- [ ] README, docs how-to, news fragment
- [ ] Manual QA (below) on the docker-compose stack (`make stack-start`)

## Manual QA (Volto)

Stack: `make stack-create-site`, `make stack-start`, site at `http://collective-quota.localhost`.

1. Anonymous: home page has no banner; `/quota-usage` redirects to login; the toolbar is absent.
2. Login as editor: user menu shows "Disk usage"; page lists the example content (2 Files, 1 Image) with sizes; limit buttons work.
3. Site Setup as admin: "Quota" appears under "Add-on Configuration"; set soft 2 MB, hard 3 MB, `block_all`; usage segment updates; "Rebuild usage data" toasts the count.
4. Upload a 1.5 MB File as editor: yellow banner on every page except `/quota-usage` and the control panel; not visible after logout.
5. Upload until > 3 MB: red banner; adding a Page fails with the backend's message in Volto's form error toast; a smaller replacement upload on an existing File succeeds.
6. `/quota-usage`: select the File linked from the example Document and one more → modal lists the breach → confirm → toast with freed size → banner turns yellow/green.
7. Environment lock: restart the backend with `COLLECTIVE_QUOTA_HARD_LIMIT_MB=50` and `COLLECTIVE_QUOTA_LOCK_SETTINGS=1` → control panel shows the hard limit disabled with the lock note; saving other fields still works; "Reset to defaults" clears the other three fields and leaves the hard limit at 50 (locked).
8. Clear all limits: no banner anywhere; page shows the "No limits" note; uploads unrestricted.
9. Uninstall the backend add-on (Classic Add-ons): Volto shows no menu entry, no banner; `/quota-usage` shows the "not installed" message; reinstall → everything is back.

## Acceptance criteria

- All three product rules hold and are covered by Cypress tests (anonymous, no limits,
  backend-less).
- The banner text and level always equal what Classic shows for the same site state
  (they come from the same backend function).
- Deleting from the page behaves like deleting from folder contents, including the
  link-integrity confirmation, and reports the bytes freed.
- The Volto control panel offers everything the Classic one does: edit, provenance,
  locked fields, rebuild, reset to defaults.
- Unit (with the 90 % coverage threshold) and Cypress suites green in CI; `make lint`
  clean; `en`/`es` complete.

## Open questions

- Whether to also expose the summary in `@site` so the banner has data on the very
  first render of non-content routes; today the slot waits for the first content
  request. Revisit if editors notice the delay.
