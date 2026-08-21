# Architecture records

KlinKlik is a modular Django/DRF monolith with a Next.js client. Django app boundaries are code boundaries, not deployable services.

The dependency direction is:

core ← tenancy ← accounts ← patients ← {clinical, maternity, laboratory, pharmacy, inventory, scheduling} ← billing ← reporting

platformadmin depends inward only. Cross-cutting audit, notifications, files, and tenant-context helpers are libraries.

Business workflows live in service modules. Views authorize and orchestrate. Serializers validate shape. Models persist and enforce local invariants.
