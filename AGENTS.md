# KlinKlik Engineering Rules

## Source of truth

The authoritative product and architecture specification is:

- K:\new\clinicopus2.md

It is the Clinicopus Canonical Product Blueprint v1.0 (the product has since been renamed to KlinKlik; the blueprint filename is historical). The earlier review file in this workspace is historical context only. Do not casually reinterpret frozen decisions.

Open decisions in the blueprint are not permission to guess. Items marked VALIDATION REQUIRED, CLINICIAN VALIDATION REQUIRED, PHARMACIST VALIDATION REQUIRED, or LEGAL / REGULATORY VALIDATION REQUIRED must remain explicit and must not be enabled by assumption.

## Scope

- Work only on the approved story or implementation slice.
- Do not implement Phase 2 or Phase 3 features early.
- Preserve cheap architectural seams only when they are explicitly described by the blueprint.
- Do not redesign the product direction: KlinKlik is one platform for CLINIC, PHARMACY, and CLINIC + PHARMACY.
- Organisation is the tenant root. Facility is a branch, not a tenant.

## Architecture

- Use the modular Django/DRF monolith and Next.js client defined in the blueprint.
- Do not introduce microservices, Kubernetes, GraphQL, serverless fragmentation, or a general event bus.
- Keep the fourteen Django app boundaries and their one-way dependency direction.
- Business logic belongs in explicit service modules.
- Views authorize, orchestrate, and serialize responses.
- Serializers validate shape and input data; they do not own workflows.
- Models persist data and enforce local invariants; do not hide domain workflows in save hooks.
- Server-side authorization is authoritative. Frontend permission gates are UX only.
- API types are generated from OpenAPI; do not hand-maintain duplicate API types.

## Safety and data integrity

- Tenant isolation is mandatory. Every tenant-owned model carries organisation context.
- PostgreSQL RLS must fail closed, use FORCE RLS, and run under a non-BYPASSRLS application role.
- Never edit stock quantities directly. Stock changes only through append-only movements.
- Never sell or dispense expired medicine. There is no expiry override.
- Controlled/Class A medicines are blocked in baseline V1.
- Never delete final clinical, financial, stock, payment, or audit records. Correct with versioning, reversal, amendment, or a new state-bearing record.
- Do not put PHI into logs, error telemetry, or audit payloads.
- Do not SSR patient charts or persist PHI in localStorage or a persistent query cache.
- No offline completion of stock, money, dispensing, or final clinical sign-off.
- Do not invent clinical interpretation, dosing, interaction checks, risk scoring, or regulatory rules.

## Required implementation quality

Every implementation must include:

- service-level tests;
- API and permission tests;
- tenant-isolation tests for new tenant-scoped endpoints;
- audit assertions for audited actions;
- state-transition tests for legal and illegal transitions;
- loading, empty, and error UI states;
- accessibility coverage for core workflow screens;
- generated OpenAPI/client-type validation where applicable;
- a clear migration path and rollback/correction behavior.

A task is not complete merely because the UI works.

## Completion report

Every task report must state:

- files changed;
- decisions made;
- architecture rules applied;
- validations and tests run, with exact results;
- remaining risks and open blueprint decisions;
- whether canonical architecture was touched;
- current git status;
- whether anything was pushed, merged, deployed, or submitted for review.

Do not push, merge, deploy, or open a PR unless explicitly requested.
