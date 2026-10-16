---
myst:
  html_meta:
    "description": "Install Collective Quota on a Volto site and find its menu entry, banner, disk usage page and control panel."
    "property=og:description": "Install Collective Quota on a Volto site and find its menu entry, banner, disk usage page and control panel."
    "property=og:title": "Use Collective Quota with Volto"
    "keywords": "Plone, Collective Quota, Volto, frontend"
---

# Use Collective Quota with Volto

Collective Quota comes in two halves. The backend add-on, `collective.quota`, does all
the measuring and enforcing, and has the Classic UI pages and the REST API. The Volto
add-on, `volto-collective-quota`, shows the same things in Volto. A Volto site needs
both; a Classic UI site needs only the backend add-on.

## Install both halves

1. Install `collective.quota` in the Plone backend and activate it in
   **Site Setup › Add-ons**, as described in {doc}`configure-limits`.
2. In your Volto 19 project, add the frontend add-on to `package.json`:

   ```json
   "dependencies": {
       "volto-collective-quota": "*"
   }
   ```

3. Add it to `volto.config.js`:

   ```javascript
   const addons = ['volto-collective-quota'];
   ```

4. Install the dependencies and restart Volto.

The Volto add-on has no backend profile of its own, and it changes nothing in Classic UI.

## Where to find things in Volto

| Feature | Where | Who sees it |
|---|---|---|
| **Disk usage** menu entry | Personal tools menu (your avatar in the toolbar), after "Site Setup" | Users with "View Disk Usage" (Editor, Contributor, Reviewer, Site Administrator, Manager) |
| Warning banner | Above the page header, on every page except the disk usage page and the Quota control panel | Same users, only when the site reaches the soft or the hard limit |
| Disk usage page | `/quota-usage` | Same users |
| Quota control panel | **Site Setup › Add-on Configuration › Quota** (`/controlpanel/collective-quota`) | Users with "Manage Quota Settings" (Site Administrator, Manager) |

Anonymous users never see any of it.

## What you can do

The features are the same as in Classic UI:

- **Disk usage page**: the total, the limits and the policy in effect, and the biggest
  items. Choose how many items to show (10, 25, 50 or 100). Select items and click
  **Delete selected**: the confirmation lists the links that would break, like
  Volto's folder contents. A message then tells you how much space was freed.
- **Warning banner**: yellow at the soft limit, red at the hard limit. It goes away by
  itself when usage drops. The text comes from the backend, so it is the same as the
  Classic banner.
- **Quota control panel**: the soft limit, hard limit, policy and maximum file size.
  Each field says its current value and where it comes from (control panel,
  environment or default). Fields locked by environment variables are disabled.
  **Rebuild usage data** recomputes the numbers; **Reset to defaults** (the undo
  button in the toolbar) clears every value saved in the control panel, so the
  environment variables or the built-in defaults apply again. Locked fields are not
  touched.

With no limit configured, Volto shows no banner, and the disk usage page shows the
total and the biggest items with a "No limits are configured" note.

## If something is missing

- **No menu entry and no banner:** check that `collective.quota` is activated on the
  backend and that your user has the "View Disk Usage" permission (see
  {doc}`grant-disk-usage-access`).
- **The page says "collective.quota is not installed on the backend":** the frontend
  add-on is installed, but the backend add-on is not activated on this site.
- **The banner appears only after you open a page:** it reads the usage summary from
  the content Volto loads, so it shows up with the first page you visit after login.

The REST endpoints that the Volto add-on uses are documented in {doc}`../reference/rest-api`.
