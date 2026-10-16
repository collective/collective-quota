---
myst:
  html_meta:
    "description": "Configure Collective Quota through environment variables and lock the settings."
    "property=og:description": "Configure Collective Quota through environment variables and lock the settings."
    "property=og:title": "Configure with environment variables"
    "keywords": "Plone, Collective Quota, environment variables, docker, lock"
---

# Configure with environment variables (and lock them)

Hosting providers and operators can set the quota outside the database, so that it is
the same on every deployment and, if needed, cannot be changed by site
administrators.

1.  Set the variables in the environment of the Zope process: the `environment:`
    section of `docker-compose.yml`, the systemd unit, or the shell that runs
    `make start`. See {doc}`../reference/environment-variables` for the list.

    ```yaml
    services:
      backend:
        environment:
          COLLECTIVE_QUOTA_SOFT_LIMIT_MB: "4500"
          COLLECTIVE_QUOTA_HARD_LIMIT_MB: "5000"
          COLLECTIVE_QUOTA_OVER_LIMIT_POLICY: block_files
    ```

2.  Restart Plone. The control panel now says "from environment variable …" next to
    those settings. Site administrators can still override them by saving a value.

3.  To make the values fixed, also set `COLLECTIVE_QUOTA_LOCK_SETTINGS=1` and
    restart. The settings that have a variable become read-only in the control panel,
    a REST `PATCH` that changes them is refused with `400`, and enforcement uses the
    environment values whatever the database says. Settings without a variable stay
    editable.

To unlock, remove `COLLECTIVE_QUOTA_LOCK_SETTINGS` (or set it to `0`) and restart.

Empty variables are ignored, and invalid values (not a whole number, a negative
number, an unknown policy) are logged once as a warning and ignored.
