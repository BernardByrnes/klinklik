# Phase A–D implementation note

The current stopping point implements:

Patient to Check-in to Queue to Triage to Consultation to Service charge to Invoice to Payment to Receipt.

The backend is a modular Django/DRF monolith with tenant-aware services, role capabilities, audit events, patient links without merge, signed/amendable clinical notes, and allocation-authoritative clinic billing. The Next.js client keeps access tokens in memory and uses an httpOnly rotating refresh cookie.

The following blueprint areas are deliberately not implemented here: pharmacy, inventory, laboratory, ANC/maternity, offline operations, external payment rails, and Phase 2/3 workflows.
