# ADR-0001: Modular Django/DRF monolith

- Status: accepted
- Authority: ARCH-006 and ARCH-007 in K:\new\clinicopus2.md
- Date: 2026-08-15

## Decision

KlinKlik uses one Django/DRF deployable backend with fourteen code-level Django app boundaries, PostgreSQL as the deployment database, and a Next.js client. Celery/Redis are introduced only for durable background work.

## Consequences

- The first team can deploy and debug one system.
- Domain ownership and dependency direction are enforced in code.
- Cross-module workflows use explicit service functions.
- Extracting a service later remains possible, but no service boundary is paid for before a real need exists.

## Rejected alternatives

Microservices, Kubernetes, GraphQL, serverless fragmentation, and a general event bus are not V1 requirements.
