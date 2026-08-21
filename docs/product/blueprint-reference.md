# Canonical blueprint reference

The authoritative product and architecture source is:

K:\new\clinicopus2.md

This repository does not silently fork or rewrite that document. The implementation follows its frozen decisions, especially:

- ARCH-001..007: one platform, organisation-root tenancy, modular monolith, app boundaries;
- SEC-001..003: server permissions, no weakened controls, fast user switching;
- CLN-001..003: immutable clinical history and no V1 clinical interpretation;
- ANC-001..005: longitudinal ANC, versioned templates, privacy-gated data, explicit copy-forward;
- PHA-001..005: no expired/controlled/unknown-class sales and hard receiving fields;
- INV-001..006: append-only ledger, lot/location separation, direct receiving, count approval;
- FIN-001..005: unified clinic billing, allocation-authoritative balances, manual Mobile Money, blind shifts;
- REG-001..002: regulatory floors and no unverified compliance claims;
- OPS-001..002: no final offline operations and no paid external API dependency.

Open decisions are listed in the blueprint §55. They must not be guessed in code.
