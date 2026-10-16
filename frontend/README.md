# Collective Quota (volto-collective-quota)

Volto add-on for [`collective.quota`](https://github.com/collective/collective-quota): disk quota for Plone sites. It shows editors how much space uploaded files and images use, warns them near the limit, and helps them find and delete the biggest items.

[![npm](https://img.shields.io/npm/v/volto-collective-quota)](https://www.npmjs.com/package/volto-collective-quota)
[![](https://img.shields.io/badge/-Storybook-ff4785?logo=Storybook&logoColor=white&style=flat-square)](https://collective.github.io/volto-collective-quota/)
[![CI](https://github.com/collective/collective-quota/actions/workflows/main.yml/badge.svg)](https://github.com/collective/collective-quota/actions/workflows/main.yml)


## Features

- **Disk usage** in the personal tools menu, right after "Site Setup".
- A warning banner above every page when the site reaches the soft limit, and a stronger one at the hard limit. The text comes from the backend, so it always matches what Classic UI shows.
- The **Disk usage** page (`/quota-usage`): total, limits and policy, then the biggest items (10, 25, 50 or 100). Select several and delete them with Volto's link-integrity confirmation; a toast reports the space freed.
- A **Quota** control panel (`/controlpanel/collective-quota`): the usual form, plus the current usage, where each value comes from (control panel, environment or default), fields locked by environment variables, "Rebuild usage data" and "Reset to defaults".

## Requirements

- Volto 19.
- The backend add-on `collective.quota` installed on the Plone site. Without it, the menu entry and the banner stay hidden and the page says the backend add-on is missing.

## Who sees what

- **Never anonymous users.** Everything renders only for logged-in users that the backend allows (permission "collective.quota: View Disk Usage"; the control panel also needs "Manage Quota Settings"). The add-on makes no decision from roles: it waits for the `disk-usage` action, the `quota` expansion or a successful `@quota-usage` response.
- **No limits, no noise.** With neither a soft nor a hard limit set, no banner appears and the page shows the total and the biggest items with a "No limits are configured" note.
- **Either half alone.** Classic UI sites need only the backend add-on.

## Installation

To install your project, you must choose the method appropriate to your version of Volto.


### Volto 19

Add `volto-collective-quota` to your `package.json`.

```json
"dependencies": {
    "volto-collective-quota": "*"
}
```

Add `volto-collective-quota` to your `volto.config.js`.

```javascript
const addons = ['volto-collective-quota'];
```

If this package provides a Volto theme, and you want to activate it, then add the following to your `volto.config.js`.

```javascript
const theme = 'volto-collective-quota';
```


## Test installation

Visit http://localhost:3000/ in a browser, login, and check the awesome new features.


## Development

The development of this add-on is done in isolation using pnpm workspaces, the latest `mrs-developer`, and other Volto core improvements.
For these reasons, it only works with pnpm and Volto 18.


### Prerequisites ✅

-   An [operating system](https://6.docs.plone.org/install/create-project-cookieplone.html#prerequisites-for-installation) that runs all the requirements mentioned.
-   [nvm](https://6.docs.plone.org/install/create-project-cookieplone.html#nvm)
-   [Node.js and pnpm](https://6.docs.plone.org/install/create-project.html#node-js) 24
-   [Make](https://6.docs.plone.org/install/create-project-cookieplone.html#make)
-   [Git](https://6.docs.plone.org/install/create-project-cookieplone.html#git)

### Installation 🔧

1.  Clone this repository, then change your working directory.

    ```shell
    git clone git@github.com:collective/collective-quota.git
    cd collective-quota/frontend
    ```

2.  Install this code base.

    ```shell
    make install
    ```


### Make convenience commands

Run `make help` to list the available Make commands.


### Set up development environment

Install package requirements.

```shell
make install
```

### Start developing

Start the backend from `../backend` (Plone with `collective.quota`; on the first run, `make install` and `make create-site` there).

```shell
make backend-start
```

In a separate terminal session, start the frontend.

```shell
make start
```

### Lint code

Run ESlint, Prettier, and Stylelint in analyze mode.

```shell
make lint
```

### Format code

Run ESlint, Prettier, and Stylelint in fix mode.

```shell
make format
```

### i18n

Extract the i18n messages to locales.

```shell
make i18n
```

### Unit tests

Run unit tests.

```shell
make test
```

### Run Cypress tests

Run each of these steps in separate terminal sessions.

In the first session, start the frontend in development mode.

```shell
make acceptance-frontend-dev-start
```

In the second session, start the backend acceptance server.

```shell
make acceptance-backend-start
```

In the third session, start the Cypress interactive test runner.

```shell
make acceptance-test
```

## License

The project is licensed under the MIT license.
