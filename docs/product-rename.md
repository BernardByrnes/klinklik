# Product Rename: Clinicopus → KlinKlik

Date: 2026-08-20
Status: approved product identity rename; no functional change.

- The product is now named **KlinKlik** (wordmark **KLINKLIK**), descriptor "Clinic Management System".
- Architecture and V1 scope are unchanged; see the canonical blueprint at `K:\new\clinicopus2.md` (filename is historical).
- Internal technical identifiers intentionally still use "clinicopus" until a dedicated infrastructure migration is planned. These include:
  - the filesystem/project path (`K:\clinicopus`) and the blueprint filename;
  - the Django project package `clinicopus` (`clinicopus.settings`, wsgi/asgi) and Django app module names;
  - database name/role (`clinicopus`, `clinicopus_app`), Docker service/volume names, and the PostgreSQL RLS policy name `clinicopus_tenant_isolation` (migration history);
  - demo seed slug `clinicopus-demo`, demo user e-mail addresses (`@clinicopus.local`), and demo passwords (`ClinicopusDemo123!`, `ClinicopusDemo!2026`) — local development credentials, not public branding;
  - frontend package name `clinicopus-web`.
- User-facing branding (UI wordmarks, browser title/metadata, receipt footer, API/OpenAPI titles, CI display name) uses KlinKlik.
