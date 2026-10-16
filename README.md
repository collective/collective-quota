# Collective Quota 🚀

[![Built with Cookieplone](https://img.shields.io/badge/built%20with-Cookieplone-0083be.svg?logo=cookiecutter)](https://github.com/plone/cookieplone-templates/)
[![Black code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![CI](https://github.com/collective/collective-quota/actions/workflows/main.yml/badge.svg)](https://github.com/collective/collective-quota/actions/workflows/main.yml)

Disk quota for Plone sites: measures the space used by uploaded files and images, warns editors near the limit, enforces a hard limit, and helps find and delete the biggest items.

## Features ✨

- Measures the size of every file and image field in a `blob_size` catalog index, with a running site-wide total that costs nothing to read.
- Adds a **Quota** control panel (soft limit, hard limit, over-limit policy, maximum file size), also available over the REST API; every setting can come from a `COLLECTIVE_QUOTA_*` environment variable and can be locked.
- Enforces the hard limit in Classic add and edit forms and in `plone.restapi`, and cancels any other change (copy/paste, scripts, imports) that would cross it.
- Adds a **Disk usage** page to the user menu that lists the biggest items and deletes several at once, with Plone's link-integrity warnings.
- Shows editors a warning banner near the soft limit and a stronger one at the hard limit.
- Works in Volto too: the add-on `volto-collective-quota` brings the same menu entry, banner, disk usage page and control panel, on top of the REST API (`@quota-usage`, `@quota-rebuild`, `?expand=quota`).

The backend add-on, `collective.quota`, works with Plone 6.1 and 6.2 and stands alone in Classic UI. For Volto 19, install both halves. See [backend/README.md](backend/README.md), [frontend/README.md](frontend/README.md) and [docs/](docs/) for the full documentation.

## Quick Start 🏁

### Prerequisites ✅

-   An [operating system](https://6.docs.plone.org/install/create-project-cookieplone.html#prerequisites-for-installation) that runs all the requirements mentioned.
-   [uv](https://6.docs.plone.org/install/create-project-cookieplone.html#uv)
-   [nvm](https://6.docs.plone.org/install/create-project-cookieplone.html#nvm)
-   [Node.js and pnpm](https://6.docs.plone.org/install/create-project.html#node-js) 24
-   [Make](https://6.docs.plone.org/install/create-project-cookieplone.html#make)
-   [Git](https://6.docs.plone.org/install/create-project-cookieplone.html#git)


### Installation 🔧

1.  Clone this repository, then change your working directory.

    ```shell
    git clone git@github.com:collective/collective-quota.git
    cd collective-quota
    ```

2.  Install this code base.

    ```shell
    make install
    ```


### Fire Up the Servers 🔥

1.  Create a new Plone site on your first run.

    ```shell
    make backend-create-site
    ```

2.  Start the backend at http://localhost:8080/.

    ```shell
    make backend-start
    ```

3.  In a new shell session, start the frontend at http://localhost:3000/.

    ```shell
    make frontend-start
    ```

Voila! Your Plone site should be live and kicking! 🎉

## Project structure 🏗️

This monorepo consists of the following distinct sections:

- **backend**: The Python add-on `collective.quota`, with a development Plone installation (pip instead of buildout).
- **frontend**: The Volto add-on `volto-collective-quota`.
- **docs**: Scaffold for writing documentation for your project.

### Why this structure? 🤔

- Both halves of the add-on, and what you need to develop and test them, live in one repository.
- Specific GitHub Workflows are triggered based on changes in each codebase (refer to .github/workflows).

## Code quality assurance 🧐

To check your code against quality standards, run the following shell command.

```shell
make check
```

### Format the codebase

To format and rewrite the code base, ensuring it adheres to quality standards, run the following shell command.

```shell
make format
```

| Section | Tool | Description | Configuration |
| --- | --- | --- | --- |
| backend | Ruff | Python code formatting, imports sorting  | [`backend/pyproject.toml`](./backend/pyproject.toml) |
| backend | `zpretty` | XML and ZCML formatting  | -- |
| frontend | ESLint | Fixes most common frontend issues | [`frontend/.eslintrc.js`](.frontend/.eslintrc.js) |
| frontend | prettier | Format JS and Typescript code  | [`frontend/.prettierrc`](.frontend/.prettierrc) |
| frontend | Stylelint | Format Styles (css, less, sass)  | [`frontend/.stylelintrc`](.frontend/.stylelintrc) |

Formatters can also be run within the `backend` or `frontend` folders.

### Linting the codebase
or `lint`:

 ```shell
make lint
```

| Section | Tool | Description | Configuration |
| --- | --- | --- | --- |
| backend | Ruff | Checks code formatting, imports sorting  | [`backend/pyproject.toml`](./backend/pyproject.toml) |
| backend | Pyroma | Checks Python package metadata  | -- |
| backend | check-python-versions | Checks Python version information  | -- |
| backend | `zpretty` | Checks XML and ZCML formatting  | -- |
| frontend | ESLint | Checks JS / Typescript lint | [`frontend/.eslintrc.js`](.frontend/.eslintrc.js) |
| frontend | prettier | Check JS / Typescript formatting  | [`frontend/.prettierrc`](.frontend/.prettierrc) |
| frontend | Stylelint | Check Styles (css, less, sass) formatting  | [`frontend/.stylelintrc`](.frontend/.stylelintrc) |

Linters can be run individually within the `backend` or `frontend` folders.

## Internationalization 🌐

Generate translation files for Plone and Volto with ease:

```shell
make i18n
```

## Developing with Claude 🤖

This product was built with [Claude](https://claude.ai) as a development assistant, following a spec-first workflow. Use the same workflow for new features.

### Specs first, with Claude Fable 5.1

The [`specs/`](specs/) folder holds the plan for everything this repository builds, and in which order. Draft and revise specs with **Claude Fable 5.1** (`claude-fable-5-1`):

- [`specs/00-architecture.md`](specs/00-architecture.md) fixes every name (permissions, views, registry keys, REST endpoints, Volto components), the quota policy, and the product rules that hold across both halves.
- Each phase gets its own file (`specs/phase-NN-*.md`) with a goal, scope, design, list of files, tasks and tests as checkboxes, acceptance criteria and a `Status` line.
- [`specs/README.md`](specs/README.md) lists the phases with their status and the project conventions (commands, 100 % backend coverage, 90 % frontend coverage, i18n, changelog fragments, no Docker images).

Settle the open design questions in the spec before any code is written.

### Implementation, with Claude Opus 5.5

Implement phases one at a time, in order, with **Claude Opus 5.5** (`claude-opus-5-5`) in [Claude Code](https://claude.com/claude-code), working from the specs:

- Read `specs/00-architecture.md` and the phase file first; they are the contract.
- Check off tasks and tests as they land, and move the phase `Status` from `Not started` to `In progress` to `Done`. A phase is `Done` only when every task and test is checked and the acceptance criteria hold.
- When the code shows that a spec is wrong (a library behaves differently, a name does not exist), fix the spec in the same commit, so the documents never lag behind the code.
- Before every commit, run the gates: `make lint` and `make test-coverage` in `backend/`, `make lint` and `make test` in `frontend/`, and the Cypress suite for user-visible flows.

### A person stays in charge

Claude drafts and implements; a developer reviews every spec and commit, runs the manual QA steps listed in each phase file, and decides what is released. Findings from manual testing go back into the specs and the tests, so they are not lost.

## Credits and acknowledgements 🙏

Generated using [Cookieplone (2.0.2)](https://github.com/plone/cookieplone) and [cookieplone-templates (19d0792)](https://github.com/plone/cookieplone-templates/commit/19d07923b43f38bc80271aab3d4ea54388fa9d23) on 2026-10-15 16:57:51.018171. A special thanks to all contributors and supporters!
