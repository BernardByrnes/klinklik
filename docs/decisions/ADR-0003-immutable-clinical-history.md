# ADR-0003: Immutable Clinical and Audit History

## Status

Accepted for the Phase A–D implementation slice.

## Decision

Signed clinical notes are represented by a durable ClinicalNoteVersion record. The API rejects ordinary edits after signature and exposes an explicit amend action requiring a reason. Audit events are append-only in the model and receive a PostgreSQL trigger during the RLS migration.

## Consequences

- Historical signed versions remain queryable and are not overwritten by amendments.
- Clinical content is stored as structured JSON for this slice; clinical interpretation, dosing, interaction checking, and risk scoring remain out of scope.
- The complete clinical history trigger hardening should be expanded before broader clinical modules are activated.
