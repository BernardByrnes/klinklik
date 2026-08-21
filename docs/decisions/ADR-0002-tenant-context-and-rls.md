# ADR-0002: Tenant Context and Database Isolation

## Status

Accepted for the Phase A–D implementation slice.

## Decision

Every tenant-owned table carries organisation_id. Authenticated requests derive the active organisation from the signed access token, enter an explicit transaction, and set the PostgreSQL local setting app.current_org_id on the connection. The application role is not the database owner and is expected to run with FORCE ROW LEVEL SECURITY.

The migration core.0002_tenant_rls discovers tenant tables by their organisation_id column and applies SELECT, INSERT, UPDATE, and DELETE policies with a fail-closed current_setting lookup. SQLite remains the local developer/test backend and intentionally no-ops the PostgreSQL policy operation.

## Consequences

- Querysets still filter by organisation and facility in application code for readable defence in depth.
- Missing or invalid tenant context cannot be treated as an unscoped request on PostgreSQL.
- PostgreSQL policy enforcement must be verified with the supplied Docker Compose stack before pilot infrastructure is provisioned.
- Login with PostgreSQL requires an explicit organisation_id so membership lookup can enter tenant context safely.
