# Phase 8 — REST endpoints and Volto UI (deferred)

Status: Deferred
Depends on: Phases 1–7
Last updated: 2026-10-15

## Goal

Give Volto sites the same features as Classic: a control panel, a "Disk usage" entry
in the toolbar/user menu, a warning banner for editors, a biggest-items view with
multi-delete honouring link integrity, and proper rendering of quota errors in forms.
Everything in this file is design intent captured now so the backend of phases 1–7
needs no rework later.

## What phases 1–7 already provide for Volto

- `@controlpanels/collective-quota` (GET/PATCH) — the Volto control panel can be
  generated from the schema with Volto's generic control panel component.
- `GET @actions` already includes the `disk-usage` user action (category `user`) with
  its permission check, so the toolbar can show it.
- Upload enforcement returns standard `400` validation errors (`field`, `message`)
  that Volto's form already displays; `block_all` add denial returns a `400` with a
  message.
- `IQuotaRestapiLayer` is the layer for every REST override.

## Backend work (REST, in `backend/`)

- [ ] `GET @quota-usage` service on the site root, permission `collective.quota.ViewDiskUsage`:
      `{ "total": int, "total_human": str, "soft": int, "hard": int, "percent": int|null, "level": "ok|warning|exceeded", "policy": str, "policy_title": str, "items": [...], "limit": int }`
      with `?limit=10|25|50|100`; items carry `@id`, `UID`, `title`, `@type`, `type_title`, `parent {@id,title}`, `blob_size`, `blob_size_human`, `modified`, `can_delete`.
- [ ] `POST @quota-rebuild` service (`ManageSettings`) → `{ "items": n, "total": int }`.
- [ ] Deletion: reuse `plone.restapi`'s `DELETE` per item plus the existing `@linkintegrity` endpoint for breach preview (no new backend needed); document the client flow.
- [ ] `@quota-usage` summary also exposed in `@site` or `@navroot` expansion? Decide when the banner is built (likely a small `quota` expansion component on the site root to avoid an extra request per page).
- [ ] Tests for each service.

## Frontend work (`frontend/packages/volto-collective-quota`)

- [ ] Control panel registered from `@controlpanels/collective-quota`.
- [ ] Toolbar / user menu entry "Disk usage" (from `@actions` user category).
- [ ] Editor banner component reading the `quota` expansion; hidden for anonymous.
- [ ] "Disk usage" view: table, limit selector, checkboxes, delete with link-integrity
      modal (same UX as Volto's Contents delete).
- [ ] i18n (`volto-collective-quota` locales).
- [ ] Cypress acceptance tests using `make acceptance-backend-start`.

## Open questions for that iteration

- Whether the banner should live in Volto's `AppExtras` or as a toolbar badge.
- Whether per-navigation-root totals (multilingual / subsites) are needed; the index
  design supports a `path` query but the O(1) total is site-wide only.
