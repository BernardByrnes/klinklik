…the appointment specifies a clinician THEN the resulting queue entry is routed to that clinician's list. GIVEN a "no-show" appointment WHEN the patient arrives later the same day THEN check-in is still possible and the appointment moves from `NO_SHOW` back to `CHECKED_IN` with an audit entry.
**Perms** `visit.create` + `appointment.read`. **Data** `Visit.appointment_id`, `Appointment.status`, audit. **Audit** Link recorded. **Errors** Two receptionists checking in the same appointment (unique constraint + 412). **UI** Today's appointments panel on the reception home with an inline Check-in button. **Deps** APT-001..003, REC-001. **OOS** Reminders, self-check-in. **Test** Double-check-in guard.

---

> **FORMAT NOTE FOR THE REMAINDER OF THE BACKLOG.** From here the same 18 fields are used but written compactly (`Pre`=preconditions, `Trig`=trigger, `Flow`=main flow, `Alt`=alternate flows, `AC`=acceptance criteria, `Perm`=permissions, `Data`, `Audit`, `Err`=errors/edges, `UI`, `Dep`=dependencies, `OOS`=out of scope, `Test`). The **Global Story Contract (§6.0)** supplies tenancy, permission-denial, audit, idempotency, ETag, validation, UI and test defaults for every story below and is part of each story's acceptance criteria.

---

**REC-010 · Record patient arrival without check-in (walk-in enquiry) · P2**
**Role** `RECEPTIONIST`. **Story** As a receptionist I want to log an enquiry/turn-away so we know demand we did not serve. **Value** Explains lost revenue and capacity gaps. **Pre** Facility open. **Trigger** Person asks for a service we can't provide now. **Flow** Log reason (`NO_CLINICIAN`, `SERVICE_UNAVAILABLE`, `PRICE`, `REFERRED_OUT`, `OTHER`) + optional name/phone → no patient record required. **Alt** Enquiry converts to check-in → link records. **AC** GIVEN a turn-away logged THEN it appears on REP-004 turn-away counts and creates no `Visit`, no `Patient`, no charge. GIVEN conversion to check-in THEN the enquiry is marked `CONVERTED` and linked to the visit. **Perm** `visit.create`. **Data** `Enquiry`. **Audit** Create/convert. **Err** Enquiry logging abused as shadow registration → no clinical fields available. **UI** One-click reason buttons. **Dep** REP-004. **OOS** Waitlists. **Test** No-visit invariant.

---

**REC-011 · Close a visit**
**Epic** 4 · **P0** · **Role** `RECEPTIONIST`, `CASHIER`; **Secondary** `SYSTEM`, `FACILITY_ADMIN`
**Story** As reception/cashier I want to close a completed visit so the patient stops appearing as present and the day's attendance can be reconciled. **Value** Defines "finished"; prevents endlessly-open visits polluting queues and reports.
**Pre** Visit `OPEN`. **Trig** Patient leaves / all steps complete.
**Flow** Pre-flight check → all queue entries terminal, all encounters `SIGNED`/`VOIDED`, all lab orders terminal (`RELEASED`/`CANCELLED`/`REJECTED`), all prescriptions terminal (`DISPENSED`/`PARTIALLY_DISPENSED_CLOSED`/`CANCELLED`), invoice fully paid **or** waived/credited with reason → `Visit CLOSED` with `closed_by`, `closed_at`.
**Alt** (a) Any blocker → list blockers with deep links; no force-close for `RECEPTIONIST`. (b) `FACILITY_ADMIN` may force-close with mandatory reason; blockers are recorded on the visit and surfaced on REP-007. (c) Nightly job flags visits open >24h as `STALE_OPEN` (never auto-closes) for morning review (OPS-004).
**AC** GIVEN a visit with an unsigned encounter WHEN closure is attempted THEN it is rejected listing the encounter and its clinician. GIVEN a visit with an outstanding balance and no waiver WHEN closure is attempted THEN it is rejected with the amount. GIVEN all conditions met WHEN closed THEN the visit disappears from "currently present" counts, remains fully readable, and no further clinical or billing records can be attached without reopening. GIVEN an admin force-close THEN the reason and each bypassed blocker are recorded in the audit event. GIVEN a closed visit WHEN a late lab result is released THEN the result attaches to the original encounter and the visit is auto-flagged `POST_CLOSURE_ACTIVITY` for review (never silently reopened).
**Perm** `visit.close`; force `visit.force_close`. **Data** `Visit.status/closed_*`, audit. **Audit** Closure + every force-close blocker. **Err** Concurrent closure (412); closing while cashier is mid-payment. **UI** Blocker checklist with green ticks/red crosses. **Dep** ENC-017, LAB-015, DSP-009, BIL-014. **OOS** Auto-close. **Test** Blocker matrix; post-closure result handling.

---

## EPIC 5 — QUEUE MANAGEMENT (`QUE`)

**QUE-001 · Queue entry created on check-in · P0 · `SYSTEM`/`RECEPTIONIST`**
**Story** As the platform I want a queue entry per service-point episode so the patient's location is always known. **Value** The location spine; every handoff is a queue transition. **Pre** Visit `OPEN`. **Trig** Check-in or forward-routing. **Flow** Create `QueueEntry(visit, department, priority, queued_at, state=WAITING)`. **Alt** Retail pharmacy sale creates none. **AC** GIVEN check-in to Triage THEN exactly one `WAITING` entry exists for that visit+department; GIVEN a second check-in attempt THEN no duplicate active entry is created (unique partial index on `visit+department+state IN (WAITING,CALLED,IN_SERVICE,ON_HOLD*)`). GIVEN creation THEN `queued_at` is server time. **Perm** `queue.manage` or via `visit.create`. **Data** `QueueEntry`. **Audit** Creation with source. **Err** Department deactivated after entry created → entry remains, admin must move it. **UI** None (implicit). **Dep** REC-001, TEN-005. **OOS** Physical ticket dispensers. **Test** Duplicate-entry constraint.

**QUE-002 · Department work queue view · P0 · `NURSE`,`CLINICIAN`,`LAB_TECH`,`PHARMACIST`,`CASHIER`**
**Story** As a service-point user I want a list of patients waiting for me, ordered fairly, so I know who to call next. **Value** The primary daily screen for four roles. **Pre** Entries exist. **Trig** User opens their queue. **Flow** List filtered to the user's department(s): patient name, number, age/sex, wait time, priority, source (from Triage/Reception), state; sorted priority desc then `queued_at` asc. **Alt** Clinician-assigned entries show first on that clinician's list (QUE-004). **AC** GIVEN 3 routine and 1 emergency entry THEN the emergency sorts first regardless of arrival time. GIVEN two routine entries THEN the earlier `queued_at` sorts first. GIVEN a patient triaged 40 minutes ago THEN wait time displays as "40 min" and the row is highlighted past the configured SLA (QUE-011). GIVEN a user without the department's capability THEN 403. GIVEN a new arrival THEN it appears within 15s without manual reload. **Perm** `queue.read` scoped to department type. **Data** Read; aggregate access audit. **Err** Clock skew; long lists (paginate 25). **UI** Dense rows, wait-time chips, single primary action per row ("Call"/"Start"). **Dep** QUE-001. **OOS** Predicted wait times. **Test** Sort determinism; SLA highlighting.

**QUE-003 · Call and start serving a patient · P0 · all service-point roles**
**Story** As a nurse/clinician I want to call the next patient and mark that I've started so colleagues don't call the same person. **Value** Prevents double-calling and gives real service-time data. **Pre** Entry `WAITING`. **Trig** Staff clicks Call. **Flow** `WAITING → CALLED` (`called_by`, `called_at`) → on opening the patient's form `CALLED → IN_SERVICE` (`served_by`, `service_started_at`). **Alt** Patient absent → QUE-009 (`NO_RESPONSE` → back to `WAITING` with attempt count, or `LEFT_WITHOUT_BEING_SEEN` after N attempts). **AC** GIVEN two staff calling the same entry concurrently THEN exactly one succeeds and the other receives 409 `ALREADY_CALLED` naming the caller. GIVEN `IN_SERVICE` THEN the entry disappears from other users' waiting lists but remains visible with the server's name. GIVEN state changes THEN each is audited with actor and timestamp. **Perm** `queue.serve`. **Data** `QueueEntry` state/actor/times. **Audit** Each transition. **Err** Staff forgets to mark served → `IN_SERVICE` ageing report (QUE-011). **UI** Big Call button; "Being seen by X" label. **Dep** QUE-002. **OOS** Audio announcements. **Test** Concurrency 409.

**QUE-004 · Assign patient to a specific clinician · P1 · `RECEPTIONIST`,`NURSE`,`SUPERVISOR`**
**Story** As reception I want to send a patient to a named clinician (their usual doctor, or the ANC midwife) so continuity is preserved. **Value** Continuity of care and fair workload. **Pre** Clinician active today. **Trig** Routing decision. **Flow** Optional `assigned_user` on the queue entry → appears on that clinician's personal list first, and in the department pool marked "assigned to X". **Alt** Assigned clinician unavailable → any clinician with `encounter.create` may take over with a reason (audited). **AC** GIVEN an entry assigned to Dr A THEN it appears at the top of Dr A's list and is visible-but-marked in the pool. GIVEN Dr B takes it over THEN a reason is required and the audit records the takeover. GIVEN no assignment THEN the entry is a pool entry. **Perm** `queue.assign`. **Data** `QueueEntry.assigned_user_id`, audit. **Err** Assigned clinician logged out all day. **UI** "My patients" vs "Department" tabs. **Dep** QUE-002. **OOS** Load-balancing algorithms. **Test** Takeover audit.

**QUE-005 · Move / forward a patient to another department · P0 · all service-point roles**
**Story** As a clinician/nurse I want to send the patient onward so the next department sees them immediately. **Value** The handoff mechanic itself. **Pre** Entry `IN_SERVICE` or completed. **Trig** Service finished or redirection needed. **Flow** Complete current entry (`COMPLETED`) → create next entry at target department (`WAITING`), carrying visit, priority and a short handoff note. **Alt** Redirect without completing (wrong queue) → `TRANSFERRED` with reason. **AC** GIVEN a nurse completes triage and forwards to Consultation THEN the triage entry is `COMPLETED`, a new Consultation entry is `WAITING`, and the patient appears in the clinician queue within 15s. GIVEN a forward THEN the visit has exactly one active queue entry at any time (invariant test). GIVEN a handoff note THEN it is visible to the receiving user on their queue row. **Perm** `queue.move`. **Data** Two `QueueEntry` rows, audit. **Err** Forwarding to a department with a disabled module → rejected. **UI** "Send to…" with department cards and waiting counts. **Dep** QUE-001..003. **OOS** Multi-destination parallel routing (handled by hold states, QUE-006). **Test** Single-active-entry invariant.

**QUE-006 · Hold a patient awaiting results / payment / procedure · P0 · `CLINICIAN`,`LAB_TECH`,`PHARMACIST`**
**Story** As a clinician I want to park a patient who has gone for tests so my room is free but the patient is not lost. **Value** **This story is what makes Journey B possible.** Without it, patients vanish or encounters get wrongly signed. **Pre** Entry `IN_SERVICE`; a blocking dependency exists (open lab order, unpaid gated charge, pending procedure). **Trig** Clinician orders investigations and releases the patient from the room. **Flow** Entry `IN_SERVICE → ON_HOLD` with `hold_reason` (`AWAITING_RESULTS`|`AWAITING_PAYMENT`|`AWAITING_PROCEDURE`) and `hold_ref` (lab order / invoice / procedure ID) → patient moves to the "On hold" section of the clinician's list with an elapsed timer → when the dependency resolves the entry auto-flags `READY_TO_RESUME`. **Alt** Clinician resumes manually before resolution; patient goes home and returns tomorrow → entry stays on hold across the day boundary and appears on the stale-hold report (QUE-011). **AC** GIVEN a lab order is placed and the clinician clicks "Send to lab" THEN the queue entry becomes `ON_HOLD(AWAITING_RESULTS)` referencing the order and the encounter becomes `AWAITING_RESULTS`. GIVEN all items of the referenced order reach `RELEASED` THEN the entry becomes `READY_TO_RESUME` and is highlighted on the clinician's list within 30s. GIVEN a held entry THEN it never disappears from any list and is counted in "patients in facility". GIVEN the clinician logs out and back in THEN the held patient is still listed. GIVEN resume THEN the entry returns to `IN_SERVICE` and the **same** encounter opens. **Perm** `queue.hold`. **Data** `QueueEntry.state/hold_reason/hold_ref/held_at`, audit. **Audit** Hold, auto-ready, resume. **Err** Hold reference cancelled (order cancelled) → entry flagged `READY_TO_RESUME` with reason `ORDER_CANCELLED`; multiple orders → ready only when all are terminal. **UI** Three sections: Waiting / On hold / Ready to resume, with counts and ageing. **Dep** LAB-004, LAB-018, ENC-016. **OOS** Cross-day auto-cleanup. **Test** Full Journey-B hold/resume with logout in between.

**QUE-007 · Remove patient from queue (left / cancelled) · P0 · `RECEPTIONIST`,`NURSE`,`SUPERVISOR`**
**Story** As staff I want to remove a patient who left so the queue reflects reality. **Value** Queue trust; accurate waiting metrics. **Pre** Entry active. **Trig** Patient left / entry created in error. **Flow** Select entry → reason (`LEFT_WITHOUT_BEING_SEEN`, `WRONG_QUEUE`, `DUPLICATE`, `SENT_HOME`) → state `CANCELLED` or `LWBS`. **Alt** Visit has no other active entry → prompt to close or cancel the visit (REC-006/011). **AC** GIVEN removal with reason `LWBS` THEN the entry is terminal, excluded from served counts, included in the LWBS report, and the visit remains open until explicitly closed. GIVEN removal without a reason THEN 400. **Perm** `queue.remove`. **Data** `QueueEntry`, audit. **Err** Removing an `IN_SERVICE` entry with an open encounter → warn and require supervisor. **UI** Reason picker. **Dep** QUE-002. **OOS** Auto-purge. **Test** Report exclusion.

**QUE-008 · Priority and emergency flags · P0 · `NURSE`,`RECEPTIONIST`**
**Story** As a triage nurse I want to raise a patient's priority so the sickest are seen first. **Value** Basic safety in a first-come-first-served culture. **Pre** Entry exists. **Trig** Emergency arrival or triage acuity. **Flow** Priority `EMERGENCY|URGENT|ROUTINE` set at check-in or from triage acuity (TRI-006) → affects sort order and colour. **Alt** Downgrade requires a reason. **AC** GIVEN triage acuity `EMERGENCY` THEN the onward consultation entry inherits priority `EMERGENCY` automatically. GIVEN a priority change THEN the audit records old/new and actor. GIVEN an `EMERGENCY` entry waiting >10 min THEN it is visually escalated on all department screens. **Perm** `queue.priority.set`. **Data** `QueueEntry.priority`, audit. **Err** Everyone marked urgent → REP-004 tracks priority distribution. **UI** Colour + icon; never colour alone (accessibility). **Dep** TRI-006. **OOS** Formal triage scales (MTS/ESI). **Test** Inheritance from triage.

**QUE-009 · No-response / recall handling · P1 · service-point roles**
**Story** As a nurse I want to record that a called patient didn't answer and re-queue them so I can move on. **Value** Keeps throughput while being fair. **Pre** Entry `CALLED`. **Trig** No response. **Flow** "No response" → attempt count +1 → back to `WAITING` retaining original `queued_at` (fairness) but flagged; after N (config, default 3) attempts offer `LWBS`. **AC** GIVEN a no-response THEN the entry returns to `WAITING` with its original queue time preserved and `call_attempts=1`. GIVEN the 3rd no-response THEN the UI offers LWBS and the row is flagged. **Perm** `queue.serve`. **Data** `QueueEntry.call_attempts`, audit. **Err** Patient in the toilet/at the cashier — never auto-LWBS. **UI** Attempt badge. **Dep** QUE-003. **OOS** Paging/announcement systems. **Test** Fairness of retained queue time.

**QUE-010 · Patient location strip on every screen · P1 · all**
**Story** As any staff member I want to see where a patient currently is so I can answer questions without hunting. **Value** Cuts the commonest interruption in a clinic. **AC** GIVEN a patient with an active queue entry THEN the patient header shows "Currently: Laboratory — waiting (12 min)". GIVEN a patient with no active entry but an open visit THEN it shows "In facility — no active queue". GIVEN a closed visit THEN it shows "Not present". **Perm** `queue.read`. **Data** Read. **Dep** QUE-001, PAT-009. **OOS** Physical location tracking. **Test** State-string mapping for all queue states.

**QUE-011 · Waiting-time SLA and stale-state alerts · P1 · `SUPERVISOR`,`FACILITY_ADMIN`**
**Story** As a supervisor I want alerts when patients wait too long or sit in a state too long so nobody is forgotten. **Value** The main safety net against dead-ends. **Pre** SLA config per department (default: waiting 30 min, `IN_SERVICE` 60 min, `ON_HOLD` 120 min). **Trig** Periodic evaluation (client-side on refresh + a Celery beat sweep every 10 min). **Flow** Breaches surface on the supervisor dashboard and as a badge on the department queue; a daily digest lists all breaches. **AC** GIVEN an entry waiting 35 min with a 30-min SLA THEN it is flagged on the department queue and counted on the supervisor dashboard. GIVEN an `ON_HOLD(AWAITING_RESULTS)` entry older than 120 min THEN it appears on the "stuck patients" list naming the blocking lab order and the ordering clinician. GIVEN no breaches THEN the dashboard explicitly shows zero rather than an empty panel. **Perm** `queue.read` + `supervisor.dashboard`. **Data** Computed; `Alert` rows optional. **Audit** None (read). **Err** Alert fatigue → per-department tuning. **UI** Counts with drill-down. **Dep** QUE-006. **OOS** SMS/email escalation. **Test** Clock-controlled SLA tests.

**QUE-012 · Waiting-room display board · P2 · `RECEPTIONIST`**
**Story** As a facility I want a screen showing who is being called, without exposing PHI. **Value** Reduces crowding at the desk. **AC** GIVEN the board is displayed THEN it shows patient number or first name + initial only (facility-configurable), never full name, diagnosis, age or phone. GIVEN the board URL THEN it requires a device token and shows only currently-called entries. **Perm** Device token, read-only. **Dep** QUE-003, AUTH-013. **OOS** TTS announcements. **Test** PHI-exposure review of the rendered board.

---

## EPIC 6 — TRIAGE (`TRI`)

**TRI-001 · Open triage for a queued patient · P0 · `NURSE`; secondary `MIDWIFE`**
**Story** As a triage nurse I want to open the triage form for the next patient so I can record their baseline. **Value** Objective data before the clinician; the clinician's first context. **Pre** Entry `WAITING` at a `TRIAGE` department; `triage.create`. **Trig** Nurse calls the patient. **Flow** Call (QUE-003) → triage form opens with patient header, visit type, last visit's key vitals for comparison. **Alt** Patient already triaged this visit → open the existing record for update (never create a second) unless a re-triage is explicitly requested (TRI-010). **AC** GIVEN a patient with an existing triage record for this visit WHEN triage is opened THEN the existing record is loaded for editing, not a new one. GIVEN opening triage THEN the queue entry becomes `IN_SERVICE`. GIVEN the previous visit had vitals THEN the last recorded weight and BP are shown as reference with their dates. **Perm** `triage.create`. **Data** `TriageRecord(visit, patient, created_by)`. **Audit** Open (access) + save. **Err** Two nurses opening simultaneously → 409/412. **UI** Single screen, numeric keypads on mobile, tab order following the physical measurement sequence. **Dep** QUE-003. **OOS** Device integration (BP machine feeds). **Test** No-duplicate-record test.

**TRI-002 · Record vital signs · P0 · `NURSE`,`MIDWIFE`**
**Story** As a nurse I want to record vitals with sane limits so errors are caught at entry. **Value** Wrong vitals cause wrong clinical decisions; typos are frequent. **Pre** Triage open. **Trig** Measurement taken. **Flow** Capture temperature (°C), pulse (bpm), respiratory rate, BP systolic/diastolic (mmHg), SpO₂ (%), weight (kg), height (cm), and MUAC (cm) where relevant. Each field optional individually but at least one required to save. **Alt** Equipment unavailable → leave blank; blanks are never recorded as zeros. **AC** GIVEN temperature 39.8 THEN it saves; GIVEN temperature 3.98 or 65 THEN it is rejected with a range error (30.0–45.0). GIVEN systolic 120 and diastolic 130 THEN the save is rejected because diastolic must be less than systolic. GIVEN pulse 0 THEN rejected (use blank for not measured). GIVEN weight and height THEN BMI is computed and displayed to 1 decimal, stored as derived, and **no interpretation text is shown**. GIVEN a saved vital outside a configured reference band THEN it is displayed with a neutral "outside reference range" marker and no advice. GIVEN save THEN the values, units, recorder and timestamp are stored. **Perm** `triage.create`. **Data** `TriageRecord` vitals, derived BMI. **Audit** Save with field diff. **Err** Unit confusion (°F entry) → unit label adjacent to every field, no unit switching in V1; extremely low SpO₂ typo. **UI** Wide numeric inputs, units always visible, out-of-range shown after blur not per keystroke. **Dep** TRI-001. **OOS** Growth charts, early-warning scores, device integration. **Test** Boundary tests per field; BMI arithmetic.

**TRI-003 · Record presenting complaint at triage · P0 · `NURSE`**
**Story** As a nurse I want to capture why the patient came, in their words, so the clinician starts informed. **Value** Speeds clerking; supports routing. **AC** GIVEN a complaint of up to 500 characters THEN it saves verbatim and appears in the clinician's triage panel (ENC-004). GIVEN a blank complaint on an OPD visit THEN saving is blocked with `COMPLAINT_REQUIRED`. GIVEN common complaints THEN a quick-pick list (facility-configurable) inserts text that remains editable. **Perm** `triage.create`. **Data** `TriageRecord.presenting_complaint`. **Err** Nurse writing a diagnosis here → helper text "record the patient's words, not a diagnosis". **Dep** TRI-001. **OOS** Structured symptom coding. **Test** Verbatim round-trip incl. non-ASCII.

**TRI-004 · Record allergies at triage · P0 · `NURSE`; secondary `CLINICIAN`,`PHARMACIST`**
**Story** As a nurse I want to record known allergies so they follow the patient permanently. **Value** The single highest-value safety datum V1 carries. **Pre** Patient exists. **Trig** Triage question. **Flow** Choose `NO_KNOWN_ALLERGIES` | `UNKNOWN` | list of allergies (substance free text or catalogue term, reaction free text, severity `MILD|MODERATE|SEVERE`) → stored **at patient level**, not visit level, with the recording visit referenced. **Alt** Patient reports a new allergy later → added by clinician/pharmacist; existing entries are never silently deleted (mark `ENTERED_IN_ERROR` with reason). **AC** GIVEN an allergy is recorded THEN it appears in the persistent patient header on every clinical screen and on the prescription print. GIVEN `NO_KNOWN_ALLERGIES` THEN the header shows "NKA" and this is distinguishable from "not asked". GIVEN allergy status never captured THEN the header shows "Allergies: not recorded" in a warning style. GIVEN an allergy marked entered-in-error THEN it is hidden from the header, retained in history with the reason, and the change is audited. **Perm** `allergy.manage` (`NURSE`,`CLINICIAN`,`MIDWIFE`,`PHARMACIST`). **Data** `PatientAllergy` (patient-scoped, versioned). **Audit** Add/mark-in-error with reason. **Err** "Allergy" to a food vs drug — free text accepted; **no automatic interaction checking is performed and the UI must not imply any** (AS-11). **UI** Red header chip; add dialog with three fields. **Dep** PAT-009, RX-003. **OOS** Automated allergy–drug alerts, coded allergen terminology. **Test** Header presence on all clinical routes; not-recorded vs NKA distinction.

**TRI-005 · Record current medications and brief history at triage · P1 · `NURSE`**
**Story** As a nurse I want to note what the patient is already taking so the clinician doesn't duplicate therapy. **AC** GIVEN up to 10 current medications entered as free text (name, dose/frequency if known) THEN they display in the clinician's triage panel and prefill the clerking "current medications" field as editable text (ENC-010). GIVEN chronic conditions ticked from a short configurable list (e.g. hypertension, diabetes, HIV, asthma, epilepsy, sickle cell) THEN they appear in the clinician's context panel. **Perm** `triage.create`. **Data** `TriageRecord.current_meds_text`, `chronic_flags`. **Err** Duplication with ENC-010 → clerking clearly labels the source ("from triage"). **Dep** ENC-010. **OOS** Medication reconciliation workflow. **Test** Prefill and editability.

**TRI-006 · Set triage acuity · P0 · `NURSE`**
**Story** As a nurse I want to assign an acuity so the queue orders by clinical need. **Value** Simple prioritisation without pretending to run a validated triage scale. **Flow** Choose `EMERGENCY` | `URGENT` | `ROUTINE` with an optional reason; V1 provides **no automatic acuity computation from vitals** (AS-11). **AC** GIVEN acuity `EMERGENCY` THEN the onward consultation queue entry has priority `EMERGENCY` and the clinician's list shows it first with a distinct marker. GIVEN acuity is changed THEN the queue priority updates and the change is audited with actor and reason. GIVEN no acuity selected THEN `ROUTINE` is stored explicitly (not null). **Perm** `triage.create`. **Data** `TriageRecord.acuity`, `QueueEntry.priority`. **Audit** Changes. **Err** Over-use of `EMERGENCY` → distribution reported (REP-004). **UI** Three large buttons with colour + icon + text. **Dep** QUE-008. **OOS** MTS/ESI/CTAS scoring. **Test** Priority propagation.

**TRI-007 · Save triage and forward to clinician · P0 · `NURSE`**
**Story** As a nurse I want to finish triage and send the patient to the clinician so the handoff is explicit. **Value** The Reception→Nurse→Doctor baton. **Pre** Triage has at least one vital + complaint. **Trig** Nurse clicks Save & Send. **Flow** Validate → persist triage → triage queue entry `COMPLETED` → create consultation (or ANC) queue entry `WAITING` with inherited priority and optional assigned clinician → confirmation showing destination and position. **Alt** Patient sent to Laboratory or Cashier first (facility flow) → destination selectable. Patient sent home from triage (e.g. wrong facility) → QUE-007 + REC-011. **AC** GIVEN a completed triage WHEN saved and forwarded THEN the clinician's queue shows the patient with a triage summary (time, temp, BP, pulse, acuity, complaint) visible on the row or one click away. GIVEN validation failure THEN nothing is forwarded and the nurse stays on the form with errors. GIVEN forwarding THEN the audit records the triage save and the queue transition as separate correlated events. **Perm** `triage.create` + `queue.move`. **Data** `TriageRecord`, two `QueueEntry` rows. **Err** Network failure after save before forward → idempotent retry; the triage record must not be duplicated. **UI** Single "Save & send to…" with destination preselected. **Dep** QUE-005, ENC-004. **OOS** Nurse-initiated protocol treatment. **Test** Partial-failure retry.

**TRI-008 · Amend a triage record · P1 · `NURSE`; secondary `SUPERVISOR`**
**Story** As a nurse I want to correct a mistyped vital so the clinician isn't misled. **Flow** Edit before the clinician signs the encounter → versioned update with reason; after the encounter is signed → correction creates a new version and notifies the signing clinician (AUD-008). **AC** GIVEN an unsigned encounter WHEN the nurse corrects the temperature THEN the new value is shown to the clinician, the previous value is retained in history, and a reason is stored. GIVEN a signed encounter WHEN triage is corrected THEN the amendment is recorded with reason and appears as an addendum in the visit timeline; the signed note content itself is unchanged. **Perm** `triage.update` (own record within the same visit) / `SUPERVISOR` otherwise. **Data** `TriageRecord` version rows. **Audit** Field diff + reason. **Err** Amendment after visit closure → allowed with supervisor + reason, flags the visit `POST_CLOSURE_ACTIVITY`. **Dep** AUD-008. **OOS** Deleting triage. **Test** Version history rendering.

**TRI-009 · Clinician view of triage data · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want the triage data visible while I clerk so I don't re-ask or re-measure. **AC** GIVEN an encounter is opened for a triaged visit THEN a triage panel shows all vitals with units, BMI, acuity, complaint, current meds, chronic flags, allergies, recorder name and time, and it remains visible (sticky or one-click) throughout clerking. GIVEN vitals were amended after the clinician opened the encounter THEN a "triage updated" indicator appears with the new values on refresh. GIVEN no triage exists THEN the panel states "No triage recorded for this visit" and clerking proceeds. **Perm** `triage.read`. **Dep** TRI-007, ENC-004. **Test** Amendment-visibility test.

**TRI-010 · Re-triage / repeat vitals in the same visit · P1 · `NURSE`**
**Story** As a nurse I want to record a second set of vitals (e.g. after antipyretics or before discharge) without overwriting the first. **AC** GIVEN a visit with an existing triage record WHEN a repeat set is recorded THEN a new `VitalsObservation` is created linked to the same visit, both sets are visible in time order, and the clinician panel shows the latest with access to earlier sets. GIVEN a repeat set THEN the queue is not re-routed automatically. **Perm** `triage.create`. **Data** `VitalsObservation` (1..n per visit; the triage record references the first). **Dep** TRI-002. **OOS** Observation charts/graphs (P2). **Test** Ordering and latest-selection.

**TRI-011 · Mandatory paediatric weight · P0 · `NURSE`**
**Story** As a facility I want weight to be compulsory for under-5s because dosing depends on it. **AC** GIVEN a patient aged under 5 years WHEN triage is saved without weight THEN the save is rejected with `WEIGHT_REQUIRED_UNDER_5`. GIVEN a patient aged under 5 THEN weight is displayed prominently in the clinician header and printed on the prescription (RX-007). GIVEN an age-estimated infant THEN the same rule applies. **Perm** `triage.create`. **Dep** PAT-010, RX-007. **OOS** Weight-based dose calculation (explicitly excluded — AS-11). **Test** Boundary at the 5th birthday.

---

## EPIC 7 — CLINICAL ENCOUNTER / DOCTOR CLERKING (`ENC`)

> This epic is deliberately granular. The encounter is a **long-lived, resumable, versioned clinical record**, not a form submission.

**ENC-001 · Start an encounter from the clinician queue · P0 · `CLINICIAN`; secondary `MIDWIFE`**
**Story** As a clinician I want to start seeing the next patient so an encounter record exists and my colleagues know the patient is with me. **Value** Creates the clinical container and claims the patient. **Pre** Queue entry `WAITING`/`CALLED` at a `CONSULTATION` department; `encounter.create`; visit `OPEN`. **Trig** Clinician clicks "Start consultation". **Flow** Call → queue entry `IN_SERVICE` → **check for an existing non-terminal encounter for this visit**: if one exists, open it (ENC-002); otherwise create `Encounter(visit, patient, provider, type=OPD, state=OPEN, started_at)` → clerking workspace opens. **Alt** (a) Patient has an open encounter from _another_ clinician → do not create a second; show "Open encounter held by Dr X" with a takeover path (ENC-022). (b) Consultation not paid under `PAY_BEFORE` → warn with the outstanding amount; clinician may proceed with `billing.gate.override` (audited) or send the patient to the cashier. **AC** GIVEN a visit with no encounter WHEN the clinician starts THEN exactly one encounter is created in state `OPEN` linked to that visit. GIVEN a visit with an existing `OPEN`/`AWAITING_RESULTS`/`RESULTS_READY` encounter WHEN the clinician starts THEN **no new encounter is created** and the existing one opens with all previously entered content. GIVEN concurrent starts by two clinicians THEN exactly one encounter exists (unique partial index on `visit + state NOT IN (SIGNED,VOIDED)`). GIVEN an unpaid gated consultation THEN the clinician sees the outstanding amount before the workspace opens. GIVEN encounter creation THEN the audit records provider, visit, patient and time. **Perm** `encounter.create`. **Data** `Encounter`, `QueueEntry.state`. **Audit** Create + open. **Err** Visit closed between queueing and starting → 409 with a reopen path. **UI** Workspace: left = context (patient, triage, history), centre = clerking sections, right = orders/prescriptions tray. **Dep** QUE-003, TRI-009. **OOS** Templates per specialty (P2). **Test** **Single-encounter-per-visit invariant under concurrency.**

**ENC-002 · Resume an existing open encounter · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want to reopen the same encounter after the patient returns from the lab, cashier or another room so my notes continue where I left them. **Value** **The core correction of the previous design mistake.** **Pre** Encounter in `OPEN`/`AWAITING_RESULTS`/`RESULTS_READY`; user is the author or has takeover rights. **Trig** Clinician clicks the patient in "On hold"/"Ready to resume", or opens the visit. **Flow** Load the same encounter ID with all sections, draft text, orders, results and prescriptions → state moves to `OPEN` if it was `RESULTS_READY` → queue entry returns to `IN_SERVICE`. **Alt** Encounter authored by another clinician → read-only unless takeover (ENC-022). **AC** GIVEN an encounter that was left in `AWAITING_RESULTS` two hours ago WHEN the clinician resumes it THEN the encounter ID is unchanged, every previously entered field is present verbatim, and the previously placed orders are listed with their current statuses. GIVEN resume from `RESULTS_READY` THEN released results are displayed inline in the encounter and the state becomes `OPEN`. GIVEN a resume across a logout/login boundary THEN behaviour is identical. GIVEN a resume THEN an audit event `ENCOUNTER_RESUMED` records actor and previous state. GIVEN the visit was closed in error THEN resume is blocked with a reopen path (`visit.reopen`). **Perm** `encounter.update` (author) or `encounter.takeover`. **Data** `Encounter` state, audit. **Err** Two devices resuming the same encounter → ETag conflict on save with a field-level diff. **UI** "Ready to resume" list item shows what changed ("3 results released"). **Dep** QUE-006, LAB-018. **OOS** Real-time collaborative editing. **Test** Journey-B resume with identical encounter ID asserted.

**ENC-003 · Patient context panel in the encounter · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want the patient's key background beside my note so I don't switch screens. **AC** GIVEN an open encounter THEN the context panel shows: name, sex, age (with "est." if estimated), patient number, allergies (or NKA / not recorded), chronic flags, last 3 visits with dates and primary diagnoses, active prescriptions from the last 30 days, and the last 3 lab results with dates. GIVEN a minor THEN guardian and weight are shown. GIVEN no history THEN each section shows an explicit empty state. GIVEN the panel is opened THEN a single access-audit event is written for the encounter view, not one per sub-section. **Perm** `encounter.read` + `patient.read`. **Dep** PAT-009. **OOS** Cross-facility history unless BRN-005 grants it. **Test** Payload authorisation; empty states.

**ENC-004 · Triage context inside the encounter · P0 · `CLINICIAN`** — see TRI-009 for the reciprocal view. **AC** GIVEN triage exists THEN vitals with units, BMI, acuity, complaint, recorder and time appear without extra navigation and are read-only to the clinician. GIVEN the clinician needs new vitals THEN they can request a repeat (creates a nursing task in the triage queue, QUE-005) rather than editing the nurse's record. **Perm** `triage.read`. **Dep** TRI-009. **Test** Read-only enforcement (API rejects clinician edits to triage).

**ENC-005 · Presenting complaint · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want to record the presenting complaint(s) and duration so the note starts correctly. **AC** GIVEN one or more complaints entered (text up to 500 chars each, optional duration value + unit `HOURS|DAYS|WEEKS|MONTHS`) THEN they are stored as an ordered list and printed as such. GIVEN the triage complaint exists THEN it is offered as a one-click copy into this field and remains separately visible. GIVEN an encounter saved without a presenting complaint THEN signing is blocked (ENC-017) although drafting is allowed. **Data** `Encounter.complaints[]`. **Dep** ENC-015. **Test** Sign-blocking rule.

**ENC-006 · History of presenting complaint · P0 · `CLINICIAN`** **AC** GIVEN free text up to 4000 characters THEN it saves, autosaves (ENC-015), preserves line breaks, and renders identically on print. GIVEN the field exceeds the limit THEN a clear character counter and a 400 error prevent silent truncation. **Data** `Encounter.hpc`. **Test** Round-trip of long text with newlines.

**ENC-007 · Review of systems (optional, structured-lite) · P2 · `CLINICIAN`** **AC** GIVEN a configurable system checklist (CVS, RS, GIT, CNS, GUS, MSS) THEN the clinician can mark each `NOT_ASSESSED|NORMAL|ABNORMAL` with a free-text note, and only assessed systems print. GIVEN nothing is marked THEN the section is omitted from print entirely. **Data** `Encounter.ros[]`. **OOS** Symptom coding.

**ENC-008 · Past medical history · P0 · `CLINICIAN`** **AC** GIVEN chronic conditions selected from the configurable list plus free text THEN they save against the **encounter** and optionally promote to a patient-level problem list entry (ENC-009) when the clinician ticks "add to problem list". GIVEN triage chronic flags THEN they are prefilled and editable, labelled "from triage". **Data** `Encounter.pmh`, `PatientProblem` (if promoted). **Test** Promotion behaviour.

**ENC-009 · Patient problem list · P1 · `CLINICIAN`** **Story** As a clinician I want a persistent list of the patient's ongoing problems so every future visit starts informed. **AC** GIVEN a problem added with onset date and status `ACTIVE|RESOLVED` THEN it appears on the patient header/context in all future encounters until resolved. GIVEN a problem is resolved THEN it is retained with a resolution date and is excluded from the active display. GIVEN problem changes THEN they are audited with actor and encounter reference. **Data** `PatientProblem`. **OOS** Automatic derivation from diagnoses (OD-08). **Test** Persistence across visits.

**ENC-010 · Current medications in clerking · P0 · `CLINICIAN`** **AC** GIVEN medications prefilled from triage and from prescriptions dispensed in the last 30 days THEN the clinician can confirm, edit or add entries as free text; the stored value is the clinician's confirmed list, with the source of each line indicated. GIVEN "none" is selected THEN it is stored explicitly and distinguishable from an unanswered field. **Data** `Encounter.current_meds[]`. **Dep** TRI-005, DSP-012. **OOS** Interaction checking (AS-11).

**ENC-011 · Allergies review in clerking · P0 · `CLINICIAN`** **AC** GIVEN patient allergies exist THEN the clinician must acknowledge or update them before signing (a single "reviewed" tick with timestamp). GIVEN allergy status is "not recorded" THEN signing is blocked until the clinician records `NKA`, `UNKNOWN`, or one or more allergies. GIVEN an allergy is added here THEN it is stored at patient level (TRI-004) and immediately reflected in the header. **Data** `PatientAllergy`, `Encounter.allergies_reviewed_at`. **Dep** TRI-004, ENC-017. **Test** Sign-blocking on unrecorded allergy status.

**ENC-012 · Family and social history · P2 · `CLINICIAN`** **AC** GIVEN free-text family history and structured-lite social fields (smoking `NEVER|FORMER|CURRENT`, alcohol `NEVER|OCCASIONAL|REGULAR`, occupation) THEN they save and print when populated and are omitted when empty. **Data** `Encounter.fh`, `Encounter.sh`. **OOS** Risk scoring.

**ENC-013 · Surgical / obstetric / drug history · P1 · `CLINICIAN`,`MIDWIFE`** **AC** GIVEN past surgeries (procedure, year, facility) as repeatable rows THEN they save and display in the context panel of future encounters. GIVEN a female patient of reproductive age THEN obstetric summary fields (gravida, para, living children) are available and, when the ANC module is enabled, are shared with the ANC record (ANC-003) as a single source of truth. **Data** `Encounter.surgical_history[]`, `PatientObstetricSummary`. **Dep** ANC-003. **Test** Single-source consistency between ENC and ANC.

**ENC-014 · Examination findings · P0 · `CLINICIAN`** **AC** GIVEN general examination free text plus per-system examination fields (each optional, up to 2000 chars) THEN only populated sections are stored and printed. GIVEN a "normal examination" quick action THEN it inserts editable template text and never auto-signs or auto-fills clinical findings the clinician has not reviewed. GIVEN examination text THEN it is included in the signed note verbatim. **Data** `Encounter.examination`. **OOS** Body diagrams, images (P2).

**ENC-015 · Autosave and explicit draft save · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want my typing preserved even if the power or network drops, because power cuts are routine. **Value** Prevents the single most rage-inducing failure in Ugandan clinic software. **Pre** Encounter `OPEN`. **Trig** Typing pauses (debounced 3s) or explicit Save. **Flow** Draft content PATCHed to the server with an ETag; success shows "Saved HH:MM:SS"; failure shows an unmistakable "Not saved — retrying" state with a manual retry. **Alt** Offline/failed → content retained **in memory only** with a persistent warning banner; the clinician is warned not to navigate away; no PHI is written to browser storage (AUTH-013). **AC** GIVEN a clinician types HPC text and pauses 3 seconds THEN the draft is persisted server-side and the UI shows a saved indicator with the server timestamp. GIVEN the browser is closed and reopened after an autosave THEN resuming the encounter shows the saved content. GIVEN the network fails during autosave THEN the UI shows "Not saved" persistently (not a transient toast) and retries with backoff; on reconnection the content is saved without duplication. GIVEN a stale ETag (another device edited) THEN the save returns 412 and the clinician is shown both versions to reconcile — content is never silently overwritten. GIVEN the idle lock fires (AUTH-012) THEN the draft is already persisted and no content is lost. **Perm** `encounter.update`. **Data** `Encounter` draft fields, `version`. **Audit** Autosaves are **not** individually audited (volume); a single `ENCOUNTER_DRAFT_UPDATED` summary per session-minute is retained. **Err** Two tabs; power loss mid-request. **UI** Persistent save-state chip near the title; never a disappearing toast as the only indicator. **Dep** AUD-012. **OOS** Offline queueing. **Test** Kill-the-tab test; 412 reconciliation UI.

**ENC-016 · Park encounter as awaiting results · P0 · `CLINICIAN`**
**Story** As a clinician I want to send the patient for tests and free my room without signing the note. **Value** Makes Journeys B and D real. **Pre** Encounter `OPEN` with ≥1 non-terminal lab order (or an explicit "awaiting other" reason). **Trig** Clinician clicks "Send for investigations / park".
**Flow** Encounter `OPEN → AWAITING_RESULTS`; queue entry `IN_SERVICE → ON_HOLD(AWAITING_RESULTS)`; patient added to the clinician's "Awaiting results" list; a patient-facing slip can be printed showing where to go (cashier/lab).
**Alt** (a) No open orders → the clinician must choose a reason (`AWAITING_PROCEDURE`, `AWAITING_PAYMENT`, `PATIENT_STEPPED_OUT`) and the state still holds. (b) Clinician parks and goes off shift → the patient remains on a **department-level** awaiting-results list so any clinician can pick up (with takeover, ENC-022).
**AC** GIVEN an encounter with 3 ordered tests WHEN the clinician parks it THEN the encounter is `AWAITING_RESULTS`, unsigned, fully editable on resume, and appears in the clinician's "Awaiting results" list with an elapsed timer. GIVEN parking THEN no diagnosis, prescription or invoice finalisation is required. GIVEN parking THEN the patient remains counted as present in the facility (REP-002). GIVEN the clinician logs out THEN the parked encounter persists and reappears at next login. GIVEN a parked encounter THEN attempting to sign it while orders are non-terminal produces a confirmation prompt (ENC-018), not a silent block.
**Perm** `encounter.update`. **Data** `Encounter.state`, `QueueEntry`, audit. **Audit** Park with reason and referenced orders. **Err** Parking with zero orders and no reason → 400. **UI** Prominent "Send for investigations" primary action next to Save; confirmation shows what the patient must do next. **Dep** LAB-002, QUE-006. **OOS** Auto-park on order placement (deliberate: the clinician decides). **Test** Journey B end-to-end.

**ENC-017 · Sign / finalise the encounter · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want to sign my note so it becomes the legal, immutable record of the consultation. **Value** Record integrity, medico-legal defensibility, and the trigger for downstream handoffs.
**Pre** Encounter `OPEN` (or `RESULTS_READY`), user is the author (or has taken over), required minimum content present.
**Trig** Clinician clicks Sign.
**Flow** 1) Server validates minimum content: ≥1 presenting complaint, allergy status recorded/reviewed, ≥1 diagnosis (working or final) **or** an explicit "no diagnosis — reason" entry, and a disposition (DX-006). 2) Confirmation dialog summarising what will become immutable and listing any non-terminal orders. 3) On confirm: `Encounter SIGNED` with `signed_by`, `signed_at`, provider name/cadre/licence snapshot, content hash (AUD-003), `version=1`. 4) Downstream events fire: prescriptions `DRAFT → ACTIVE` (RX-005), procedure orders released to the treatment room, unbilled clinical charges finalised (BIL-013), queue entry `COMPLETED` with onward routing chosen by the clinician (pharmacy/cashier/exit).
**Alt** (a) Non-terminal lab orders exist → warning listing them; the clinician may sign anyway (results attach later as addenda, LAB-023) or cancel and park. (b) Minimum content missing → 400 with a checklist of what is missing. (c) The consultation charge is unpaid under `PAY_AFTER` → signing proceeds; the invoice remains outstanding.
**AC** GIVEN an encounter missing a diagnosis WHEN sign is attempted THEN it is rejected with `DIAGNOSIS_REQUIRED` and the note remains editable. GIVEN a valid encounter WHEN signed THEN all clinical fields become read-only via the API (any PATCH returns 409 `RECORD_SIGNED`), a content hash is stored, and the signed note is printable with the provider's name, cadre and licence number. GIVEN signing THEN any `DRAFT` prescription for that encounter becomes `ACTIVE` and appears in the pharmacy queue within 15 seconds. GIVEN signing with an outstanding lab order THEN the clinician is warned and, if they proceed, the encounter is marked `signed_with_pending_orders=true`. GIVEN signing THEN an audit event records actor, timestamp, content hash and the downstream events triggered. GIVEN two sign requests with the same idempotency key THEN the encounter is signed once and no duplicate prescriptions are activated.
**Perm** `encounter.sign` (`CLINICIAN`,`MIDWIFE` only — never nurses, never admins). **Data** `Encounter` (state, signature snapshot, hash), `Prescription`, `Invoice`, `QueueEntry`. **Audit** High-value; hash retained. **Err** Signing an already-signed encounter (409); signing after visit closure (allowed with flag); clinician's licence expired (warn, do not block — OD-04). **UI** Sign is visually distinct and requires explicit confirmation; the dialog is a checklist, not a wall of text. **Dep** DX-001, RX-005, BIL-013, AUD-003. **OOS** Cryptographic e-signature with personal keys, co-signing (P2). **Test** Immutability enforcement at API level; downstream event fan-out; idempotent sign.

**ENC-018 · Sign with pending investigations (explicit choice) · P0 · `CLINICIAN`** **Story** As a clinician I want a clear choice between parking and signing when results are still pending, because sometimes I treat empirically and the result is for follow-up. **AC** GIVEN non-terminal orders WHEN Sign is clicked THEN a dialog lists each pending test and offers exactly two actions: "Park and wait for results" (ENC-016) or "Sign now — results will be added as an addendum". GIVEN "Sign now" THEN the encounter signs, the lab order remains active, and on release the result attaches to the encounter as an addendum with a notification to the signer (LAB-023). GIVEN the dialog THEN neither option is preselected. **Dep** ENC-016/017, LAB-023. **Test** Both branches produce correct downstream states.

**ENC-019 · Void an encounter created in error · P1 · `SUPERVISOR`; secondary `CLINICIAN`**
**Story** As a supervisor I want to void an encounter opened on the wrong patient so the wrong chart isn't polluted. **Pre** Encounter exists. **Flow** Void with mandatory reason (min 20 chars) → state `VOIDED` → content hidden from the clinical timeline but retained in full for audit → related draft prescriptions cancelled, unbilled charges voided, released lab results **not** deleted but detached and flagged for review. **Alt** Signed encounter → voiding requires `SUPERVISOR` + reason and produces a visible "VOIDED" watermark on any reprint; the record is never physically deleted. **AC** GIVEN a voided encounter THEN it does not appear in the patient's clinical history by default, is retrievable via an "include voided" filter by authorised roles, and is excluded from diagnosis and visit statistics. GIVEN voiding THEN the audit stores the full prior content hash, the reason and the actor. GIVEN a voided encounter with a paid invoice THEN the payment is untouched and a reversal must be handled separately (PAY-008). **Perm** `encounter.void`. **Err** Wrong-patient encounters that already drove dispensing → dispense reversal is a separate manual process (DSP-016). **Test** Statistics exclusion; audit completeness.

**ENC-020 · View a signed encounter · P0 · `CLINICIAN`,`MIDWIFE`,`SUPERVISOR`; limited others** **AC** GIVEN a signed encounter THEN it renders read-only with the full note, orders and their results, diagnoses, prescriptions, provider identity snapshot, signed timestamp and version number, plus any addenda in chronological order. GIVEN a nurse or pharmacist opens it THEN they see only the sections their capabilities allow (pharmacist: diagnoses + prescriptions + allergies; nurse: vitals + instructions), enforced in the API payload. GIVEN any view THEN a `PATIENT_RECORD_VIEWED` audit event is written. **Perm** `encounter.read` variants. **Dep** AUD-001. **Test** Per-role payload assertions.

**ENC-021 · Clinician's personal worklists · P0 · `CLINICIAN`,`MIDWIFE`**
**Story** As a clinician I want my own dashboard of who is waiting, who is with me, who is awaiting results and what is unsigned, so nothing falls through. **Value** The clinician's home screen and the primary anti-dead-end mechanism. **AC** GIVEN a clinician signs in THEN their home shows four counted lists: **Waiting for me** (queue), **In progress** (open encounters), **Awaiting results** (encounters in `AWAITING_RESULTS`), and **Ready to review** (encounters in `RESULTS_READY`), plus **Unsigned** (encounters `OPEN`/`RESULTS_READY` older than 24 hours). GIVEN a result is released THEN the patient moves from "Awaiting results" to "Ready to review" within 30 seconds with a visible badge change. GIVEN an encounter has been unsigned for more than 24 hours THEN it appears in the "Unsigned" list and on the supervisor dashboard (REP-015). GIVEN a clinician with no patients THEN each list shows an explicit zero state. **Perm** `encounter.read` (own) + `queue.read`. **Dep** QUE-006, LAB-018. **Test** Badge transition timing; 24-hour unsigned rule.

**ENC-022 · Transfer or take over an encounter · P1 · `SUPERVISOR`,`CLINICIAN`**
**Story** As a clinician taking over from a colleague who has gone off shift, I want to continue their unsigned encounter so the patient isn't restarted. **Pre** Encounter non-terminal; original author unavailable or consenting. **Flow** Request takeover with reason → encounter's `current_provider` changes while `created_by` is preserved → both providers are recorded on the note and on the print ("Started by Dr A, completed by Dr B") → the new provider signs. **AC** GIVEN a takeover THEN the encounter ID is unchanged, all content is preserved, and the printed note names both providers with their roles and times. GIVEN a takeover without a reason THEN it is rejected. GIVEN a takeover THEN the original author retains read access and is notified in their worklist. GIVEN a signed encounter THEN takeover is not possible (use addendum, ENC-023). **Perm** `encounter.takeover` (`SUPERVISOR`, or `CLINICIAN` when the author's session has been inactive for a configured period). **Audit** High-value. **Dep** USR-004. **Test** Dual-provider print.

**ENC-023 · Amend a signed encounter (addendum) · P0 · `CLINICIAN`(author); secondary `SUPERVISOR`**
**Story** As a clinician I want to add a correction or new information to a signed note without altering the original, so the record stays truthful. **Value** Real clinical need + legal integrity. **Pre** Encounter `SIGNED`. **Trig** New information, error found, late result. **Flow** Create an addendum: type (`CORRECTION`|`ADDITIONAL_INFORMATION`|`LATE_RESULT`|`CLARIFICATION`), text, mandatory reason → addendum signed separately with its own timestamp and hash → encounter `version` increments; the original text remains visible and unaltered. **Alt** Addendum by a non-author → permitted for `SUPERVISOR` with reason; the addendum is attributed to them, not to the original author. **AC** GIVEN a signed encounter WHEN an addendum is added THEN the original content is byte-identical and its hash still validates, the addendum appears below the original with its own author, timestamp and reason, and the encounter version becomes 2. GIVEN a printed note after amendment THEN it shows the original content followed by all addenda in order, each clearly labelled. GIVEN an attempt to PATCH the original signed fields THEN 409 `RECORD_SIGNED` regardless of role. GIVEN an addendum THEN a high-value audit event is written. **Perm** `encounter.amend`. **Data** `EncounterAddendum`, `Encounter.version`. **Audit** Yes, with hashes. **Err** Addendum spam; addenda on voided encounters (blocked). **UI** Amend button on the signed view; the dialog states plainly that the original will remain visible. **Dep** AUD-003, AUD-008. **OOS** Retracting an addendum (add another). **Test** Hash-validation-after-amendment test.

**ENC-024 · Print / export the consultation note · P0 · `CLINICIAN`; secondary `RECEPTIONIST`** **AC** GIVEN a signed encounter WHEN printed THEN the document contains the facility header (TEN-003), patient identifiers, visit date, triage vitals, full clerking content, diagnoses, investigations with results (if released), treatment plan, prescriptions, follow-up, provider name/cadre/licence, signature timestamp and version, plus a "Page X of Y". GIVEN an unsigned encounter WHEN printed THEN the document is watermarked "DRAFT — NOT SIGNED" and the action is audited. GIVEN a reprint THEN it is audited with actor and time (AUD-009). **Perm** `encounter.print`. **Dep** TEN-003, RCP-004. **OOS** PDF email/WhatsApp delivery. **Test** Snapshot of A4/A5 layouts; draft watermark.

---

## EPIC 8 — LABORATORY ORDERS AND RESULTS (`LAB`)

### 8.0 Why the V1 lab statuses are what they are

Proposed set, evaluated: `ORDERED`, `AWAITING_PAYMENT`, `READY_FOR_COLLECTION`, `SAMPLE_COLLECTED`, `IN_PROGRESS`, `RESULT_ENTERED`, `VERIFIED`, `RELEASED`, `CANCELLED`.

**Kept, with justification:**

- **`ORDERED`** — the clinician's intent exists; the lab has not accepted it. Needed as the entry state and for "ordered but never actioned" reporting.
- **`AWAITING_PAYMENT`** — mandatory because `PAY_BEFORE` is the dominant Ugandan private-sector rule and the lab must be able to see, but not process, unpaid work. Only entered when policy says so.
- **`READY_FOR_COLLECTION`** — the operational "lab may now proceed" state; distinct from `ORDERED` because the gate (payment/consent/preparation) has cleared. Merging it into `ORDERED` would lose the ability to show the lab an actionable list.
- **`SAMPLE_COLLECTED`** — the physical custody event. Without it, "the patient says they gave blood" is unresolvable and rejection handling has no anchor.
- **`RESULT_ENTERED`** — result exists but is not clinically usable. Essential to prevent clinicians acting on unverified values.
- **`VERIFIED`** — a second (or explicitly configured same-person) check has occurred.
- **`RELEASED`** — visible to the clinician and printable. Kept **separate from `VERIFIED`** because some facilities verify in batch and release individually, and because release is the event that drives the clinician's `RESULTS_READY` state and the patient's report.
- **`CANCELLED`** — terminal, with reason.
- **`SAMPLE_REJECTED`** — **added** (not in the proposed list, but required): haemolysed, insufficient, mislabelled, or wrong container samples are routine, and without an explicit state the order silently stalls. It is a _recoverable_ state (recollection returns the item to `READY_FOR_COLLECTION`) or terminal if the clinician cancels.

**Dropped, with justification:**

- **`IN_PROGRESS`** — for a small clinic lab running RDTs, microscopy and a haematology analyser, the interval between "sample collected" and "result typed" is minutes and no one will maintain a separate click. It adds a mandatory transition with no consumer. **Decision: dropped from V1**; if a facility later needs bench tracking, it can be added without breaking the machine (it would sit between `SAMPLE_COLLECTED` and `RESULT_ENTERED`). Recorded as OD-10 for the pilot to confirm.

State granularity is at the **`LabOrderItem`** (per test) level; the **`LabOrder`** state is derived (LAB-006), because a clinician frequently orders a CBC that comes back in ten minutes and a culture that takes three days.

---

**LAB-001 · Laboratory test catalogue · P0 · `FACILITY_ADMIN`; secondary `LAB_TECH`**
**Story** As an administrator I want to define the tests we offer, with their analytes and reference ranges, so results are structured and consistently reported. **Pre** Lab module enabled. **Trig** Setup. **Flow** Create `LabTestDefinition`: name, short code, specimen type (blood/urine/stool/sputum/swab/other), container/tube, method (optional), result type (`NUMERIC`, `CODED`, `TEXT`, `PANEL`), turnaround target, linked `Service` for pricing (CAT-001), active flag. For `PANEL`, define ordered analytes each with their own result type, unit, decimal places and reference ranges. Ranges may be defined by sex and age band, plus a free-text reference note. **Alt** Seed a starter catalogue for a Ugandan small lab (Malaria RDT, Malaria BS, CBC/FBC panel, Hb, blood group & Rh, RBS/FBS, widal, H. pylori, HIV rapid, urinalysis panel, urine HCG, stool routine, Hep B surface antigen, RPR/syphilis, sickling test, ESR, LFTs, RFTs, urea/creatinine) with editable defaults. **AC** GIVEN a `PANEL` test with 8 analytes THEN result entry presents exactly those 8 fields in the defined order with their units. GIVEN a numeric analyte with a range 4.0–11.0 ×10⁹/L THEN entering 13.2 stores the value and flags it `HIGH` **without any interpretive text**. GIVEN sex- or age-specific ranges THEN the range applied is selected from the patient's sex and age at the time of the result and the applied range is stored on the result. GIVEN a test with no linked priced service THEN it cannot be ordered and an admin setup warning is shown. GIVEN a catalogue change THEN previously released results retain the ranges and units captured at release. **Perm** `lab.catalogue.manage`. **Data** `LabTestDefinition`, `LabAnalyte`, `LabReferenceRange`. **Audit** Definition changes. **Err** Changing a unit after results exist → new version of the definition; old results unaffected. **UI** Test list with panel expansion; range editor with sex/age bands. **Dep** CAT-001. **OOS** LOINC coding, analyser interfacing, quality-control workflows. **Test** Range-selection-by-demographics; snapshot immutability.

**LAB-002 · Clinician orders investigations · P0 · `CLINICIAN`,`MIDWIFE`; secondary `LAB_TECH`**
**Story** As a clinician I want to order one or more tests from inside the encounter so the lab knows exactly what to do and for whom. **Pre** Encounter `OPEN`/`RESULTS_READY`; lab module enabled; `lab.order.create`. **Trig** Clinician opens the Investigations tray. **Flow** Search/select tests (multi-select, with a facility "frequently ordered" shortlist) → set priority per order (`ROUTINE`|`URGENT`) → optional clinical notes to the lab (free text, e.g. "on antimalarials since yesterday") → optional required-by time for urgent → confirm → one `LabOrder` with n `LabOrderItem`s, linked to the encounter, visit and patient. **Alt** (a) Duplicate test already ordered in this visit and not cancelled → warn "CBC already ordered 20 minutes ago (status: sample collected)" and require confirmation. (b) Test's service is not priced → not orderable. (c) Lab module disabled → tray hidden and API 403. **AC**

- GIVEN a patient with an open encounter and a clinician with `lab.order.create` WHEN the clinician orders a CBC THEN a `LabOrder` is created **linked to the existing encounter**, the encounter remains `OPEN` and unsigned, the laboratory work queue displays the order, the clinician may leave the encounter without signing it, and the patient appears in the clinician's "Awaiting results" state once parked (ENC-016).
- GIVEN three tests ordered together THEN one order with three items is created, each item independently trackable.
- GIVEN priority `URGENT` THEN the order sorts above routine orders in the lab queue and is visually marked.
- GIVEN ordering THEN a charge event is emitted per orderable item (LAB-004) exactly once, even on retry with the same idempotency key.
- GIVEN a signed encounter THEN new orders cannot be added to it (a new encounter or an addendum-linked order is required — OD-07).
  **Perm** `lab.order.create` (`CLINICIAN`,`MIDWIFE`; **not** nurses in V1). **Data** `LabOrder`, `LabOrderItem`, charge events, audit. **Audit** Order creation with test list, priority, ordering provider. **Err** Ordering after the patient has left; ordering a test whose specimen the facility can't collect (catalogue should be curated). **UI** Tray with search, shortlist chips, selected-items list with per-item remove, single confirm. **Dep** ENC-001, LAB-001, LAB-004. **OOS** Order sets/protocols, standing orders, external lab referral orders (LAB-025 is P2). **Test** Encounter linkage and open-state assertions (the canonical Journey-B acceptance test).

**LAB-003 · Order priority and clinical notes to the lab · P1 · `CLINICIAN`** **AC** GIVEN priority `URGENT` THEN the lab queue shows the order at the top with an urgent marker and the target turnaround from the catalogue. GIVEN clinical notes THEN they are visible to the lab technician on the work item and are printed on the internal worksheet, but are **not** printed on the patient-facing report unless configured. **Data** `LabOrder.priority`, `clinical_notes`. **Dep** LAB-002. **Test** Sort and visibility.

**LAB-004 · Charge generation on order · P0 · `SYSTEM`** **Story** As a facility I want ordering a test to create the charge automatically so we never do unbilled lab work. **Flow** On order creation, for each item resolve the linked service and facility price → create invoice lines on the visit's invoice with `source=LAB_ORDER_ITEM` and `source_id` → invoice `ISSUED`. **AC** GIVEN three ordered tests THEN three invoice lines exist with the current facility prices snapshotted, referencing the specific order items. GIVEN the same order submitted twice with one idempotency key THEN three lines exist, not six (enforced by a unique constraint on `(invoice, source_type, source_id)`). GIVEN an item is cancelled before collection THEN its invoice line is voided if unpaid, or flagged for refund/credit if paid (LAB-022). GIVEN a lab-only walk-in with no encounter THEN charges attach to the visit's invoice or to a standalone invoice for that patient. **Data** `InvoiceLine`. **Audit** Charge creation with source. **Dep** BIL-001, BIL-013. **Test** Duplicate-line constraint; cancellation refund path.

**LAB-005 · Payment gate for laboratory work · P0 · `SYSTEM`; secondary `CASHIER`,`LAB_TECH`** **Story** As a facility with a pay-before rule I want the lab to be unable to process unpaid tests, while still seeing them. **Flow** If `LABORATORY=PAY_BEFORE`: item state `ORDERED → AWAITING_PAYMENT`; the lab queue shows it in a separate "Awaiting payment" section, not actionable. When the related invoice lines are fully paid (or waived), the items move to `READY_FOR_COLLECTION`. If `PAY_AFTER`/`NO_GATE`: items go straight to `READY_FOR_COLLECTION`. **Alt** Override by a user with `billing.gate.override` (reason mandatory) moves items to `READY_FOR_COLLECTION` while the charge stays outstanding. **AC** GIVEN `PAY_BEFORE` and an unpaid lab charge WHEN the technician attempts to record collection THEN the action is refused with `PAYMENT_REQUIRED` and the outstanding amount is displayed. GIVEN the cashier records full payment for those lines THEN the items become `READY_FOR_COLLECTION` within 15 seconds and appear in the lab's actionable queue. GIVEN a partial payment covering only 2 of 3 tests THEN exactly those 2 items become collectable and the third remains `AWAITING_PAYMENT` (allocation per PAY-005). GIVEN an override THEN the item becomes collectable, the charge remains outstanding, and the audit records the actor and reason. **Data** Item state, `gate_policy_at_charge`. **Audit** Gate transitions and overrides. **Err** Payment reversed after collection → the item continues (work already done) and the invoice returns to outstanding; flagged on REP-008. **Dep** TEN-006, PAY-012. **Test** Partial-payment line-level gating.

**LAB-006 · Derived order status · P0 · `SYSTEM`** **AC** GIVEN an order with items in `RELEASED` and `SAMPLE_COLLECTED` THEN the order status displays as `PARTIALLY_RELEASED`. GIVEN all items `RELEASED`/`CANCELLED`/terminal-rejected THEN the order is `COMPLETED` and the encounter's awaiting-results dependency for that order is satisfied. GIVEN all items `CANCELLED` THEN the order is `CANCELLED`. GIVEN mixed states THEN the queue shows per-item states, never a misleadingly aggregated single state. **Data** Derived (computed, not stored, or stored as a denormalised cache updated in the same transaction). **Test** All state-combination permutations.

**LAB-007 · Laboratory work queue · P0 · `LAB_TECH`,`LAB_VERIFIER`** **Story** As a lab technician I want a prioritised list of work so I know what to do next and nothing is missed. **AC** GIVEN orders exist THEN the queue shows sections: **Awaiting payment** (visible, not actionable), **To collect** (`READY_FOR_COLLECTION`), **Collected / in bench** (`SAMPLE_COLLECTED`), **To verify** (`RESULT_ENTERED`), **Rejected / action needed** (`SAMPLE_REJECTED`). GIVEN each row THEN it shows patient name and number, test(s), priority, ordering clinician, order time and elapsed time. GIVEN an urgent order THEN it sorts first within its section. GIVEN a technician without `lab.result.verify` THEN the "To verify" section is visible but its actions are disabled with an explanatory tooltip. GIVEN 200 items in a day THEN the queue paginates and remains under 2s p95. **Perm** `lab.queue.read`. **Dep** LAB-002, LAB-005. **Test** Section membership per state.

**LAB-008 · Record sample collection / receipt · P0 · `LAB_TECH`; secondary `NURSE`** **Story** As a lab technician I want to record that I have the specimen so custody is clear and the clock starts. **Pre** Item `READY_FOR_COLLECTION`. **Flow** Verify patient identity (name + patient number read-back prompt) → select items collected (may be a subset) → record specimen type (defaulted from the catalogue), collection time (defaults to now, editable within limits), collector → generate a specimen ID per item or per container → print a specimen label if a printer exists → items `SAMPLE_COLLECTED`. **Alt** Sample collected by a nurse in the treatment room → the nurse records collection (with `lab.sample.collect`) and the lab records receipt; both timestamps are stored. Patient not present → cannot collect. **AC** GIVEN two of three items collected THEN only those two become `SAMPLE_COLLECTED` and the third remains `READY_FOR_COLLECTION`. GIVEN collection THEN a unique specimen ID is generated per facility per day and printed on the label with patient name, number, test, date/time and collector initials. GIVEN an attempt to collect an `AWAITING_PAYMENT` item THEN it is refused (LAB-005). GIVEN collection THEN the audit records collector, time and specimen IDs. **Perm** `lab.sample.collect`. **Data** `LabSpecimen`, item state. **Err** Wrong patient's sample → rejection/relabel path (LAB-009) plus an incident note; label printer offline → handwritten fallback with the ID displayed large on screen. **UI** Read-back identity prompt is a required checkbox, not decorative. **Dep** TEN-007 (specimen numbering). **OOS** Barcode scanning (P2), chain-of-custody signatures. **Test** Partial collection; specimen ID uniqueness.

**LAB-009 · Reject a sample / unable to process · P0 · `LAB_TECH`** **Story** As a lab technician I want to record that a sample cannot be processed, with the reason, so the clinician knows and a recollection can happen. **Value** Without this, the order silently dies and the patient waits forever. **Pre** Item `SAMPLE_COLLECTED` (or `READY_FOR_COLLECTION` when the patient cannot provide a sample). **Flow** Select item → reason (`HAEMOLYSED`, `INSUFFICIENT_VOLUME`, `CLOTTED`, `WRONG_CONTAINER`, `MISLABELLED`, `LEAKED`, `PATIENT_UNABLE_TO_PROVIDE`, `REAGENT_UNAVAILABLE`, `EQUIPMENT_DOWN`, `OTHER` + note) → item `SAMPLE_REJECTED` → the ordering clinician's worklist shows an alert; reception/nurse see a recollection task. **Alt** Recollect → item returns to `READY_FOR_COLLECTION` with `recollection_count+1`, retaining the original order and **without a second charge** (unless the reason is patient-caused and facility policy says otherwise — OD-12). Cannot recollect → clinician cancels the item (LAB-022). **AC** GIVEN a rejected sample THEN the ordering clinician sees the rejection with its reason in their worklist within 30 seconds and the encounter remains `AWAITING_RESULTS` if other items are pending, or becomes `RESULTS_READY`/actionable if this was the last one. GIVEN a rejection THEN the patient is **never** left with no next step: the item appears in the "Action needed" lab section and on the reception recollection list. GIVEN recollection THEN no duplicate invoice line is created. GIVEN rejection THEN the audit records the reason, actor and time. **Perm** `lab.sample.reject`. **Data** `LabOrderItem.rejection_*`, `recollection_count`. **Err** Repeated rejections (>2) → flagged to the supervisor. **UI** Reason list with a mandatory note for `OTHER`. **Dep** LAB-018 (notification), LAB-022. **Test** No-double-charge on recollection; dead-end prevention assertion.

**LAB-010 · Enter numeric and panel results · P0 · `LAB_TECH`** **Story** As a lab technician I want to type results into the exact fields the test defines so nothing is ambiguous. **Pre** Item `SAMPLE_COLLECTED`; `lab.result.enter`. **Flow** Open the item → the form renders the analytes from the catalogue with units and decimal precision → enter values → optional per-analyte comment → optional overall comment → save → item `RESULT_ENTERED`. **AC** GIVEN a CBC panel with 8 analytes THEN all 8 fields are shown with units, and saving with 6 filled is allowed only if the unfilled ones are explicitly marked "not done" (no silent blanks in a released report). GIVEN a value outside the sanity bounds for the analyte (e.g. Hb 250 g/dL) THEN the save is rejected with a range error. GIVEN a value outside the reference range THEN it is stored with a `HIGH`/`LOW` flag and rendered with a neutral marker; **no interpretation, no advice, no suggested action is displayed anywhere**. GIVEN the entering technician THEN their identity and the entry time are stored. GIVEN a result saved THEN it is **not** visible to the ordering clinician until released (LAB-015). **Perm** `lab.result.enter`. **Data** `LabResult` (v1), `LabResultAnalyteValue`. **Audit** Entry with values. **Err** Decimal/comma confusion → strict numeric parsing with an explicit hint; unit mismatch. **UI** Keyboard-driven grid, Enter moves to the next analyte, reference range shown greyed beside each field. **Dep** LAB-001. **OOS** Analyser import, delta checks, QC rules. **Test** Not-done handling; invisibility before release.

**LAB-011 · Enter coded results · P0 · `LAB_TECH`** **AC** GIVEN a test defined as `CODED` with options (e.g. Malaria RDT: `POSITIVE`/`NEGATIVE`/`INVALID`; Blood group: `A/B/AB/O` × `POSITIVE/NEGATIVE`) THEN the entry form presents exactly those options as a single-select and free text is not accepted in the coded field. GIVEN `INVALID` THEN a comment is mandatory. GIVEN a coded result THEN it prints as the option label and is countable in reports (REP-009). **Data** `LabResult.coded_value`. **Test** Option enforcement.

**LAB-012 · Enter text/descriptive results · P1 · `LAB_TECH`** **AC** GIVEN a `TEXT` result type (e.g. stool microscopy, urinalysis microscopy description) THEN a structured-lite form with a free-text area up to 2000 characters is provided, optionally with facility-defined template phrases that insert editable text. GIVEN a text result THEN it prints preserving line breaks. **Dep** LAB-010. **Test** Long-text round trip.

**LAB-013 · Attach reference ranges and units to the stored result · P0 · `SYSTEM`** **AC** GIVEN a released result THEN the report displays the value, unit, and the reference range **as it was at the time of release**, and changing the catalogue afterwards does not alter historical reports. GIVEN a patient-specific range selection (by sex/age) THEN the applied range is stored on the result row. **Data** Snapshot fields on `LabResultAnalyteValue`. **Test** Catalogue-change immutability.

**LAB-014 · Save partial results within a panel · P1 · `LAB_TECH`** **AC** GIVEN a panel where only some analytes are complete THEN the technician can save progress without moving the item to `RESULT_ENTERED`, and the queue shows it as "in entry" with the entering technician's name. GIVEN a partial save THEN the values are not visible to clinicians. GIVEN completion THEN the item transitions to `RESULT_ENTERED` in one explicit action. **Dep** LAB-010. **Test** Visibility boundary.

**LAB-015 · Verify and release a result · P0 · `LAB_VERIFIER`; secondary `LAB_TECH`**
**Story** As the lab in-charge I want to check a result before the clinician can act on it, so we don't release a mistyped value. **Value** The safety gate of the lab loop. **Pre** Item `RESULT_ENTERED`; `lab.result.verify`. **Trig** Verifier opens the "To verify" section. **Flow** Review entered values against the reference ranges and any comments → either **Verify & release** (single action, default) or **Verify** then **Release** separately if the facility uses batch verification → item `VERIFIED → RELEASED` with verifier identity and timestamps → release event fires (LAB-018). **Alt** Verifier rejects the entry → item returns to `SAMPLE_COLLECTED`/entry with a mandatory comment to the technician; the previous entry is retained as a non-released version. **AC** GIVEN a result in `RESULT_ENTERED` WHEN the verifier releases it THEN the item becomes `RELEASED`, the ordering clinician's encounter transitions toward `RESULTS_READY` (LAB-018), and the result becomes printable. GIVEN the entering technician lacks `lab.result.verify` THEN they cannot release, and the action is absent and API-refused. GIVEN a released result THEN it cannot be edited; corrections require an amended version (LAB-017). GIVEN verification THEN the audit records the verifier, timestamp, and the exact values released (hash). GIVEN a rejected entry THEN the technician sees the rejection with the comment in their queue. **Perm** `lab.result.verify`. **Data** `LabResult.verified_by/at`, `released_at`, state. **Audit** High-value. **Err** Verifier releasing their own entry — permitted only under LAB-016. **UI** Side-by-side entered values and ranges; single prominent Release action. **Dep** LAB-010, LAB-018. **Test** Author-cannot-self-release enforcement (unless LAB-016 is configured).

**LAB-016 · Single-technician facility configuration · P0 · `FACILITY_ADMIN`** **Story** As a small facility with one lab technician I need results to be releasable by the person who entered them, because there is nobody else. **Value** Without this, the pilot lab stalls; with an unconfigured default, safety is silently lost. **Flow** Facility setting `lab_allow_self_verification` (default **false**). When true, users holding both `lab.result.enter` and `lab.result.verify` may release their own entries; every such release is tagged `self_verified=true`. **AC** GIVEN the setting is false and a technician holding both capabilities WHEN they attempt to release their own entry THEN it is refused with `SELF_VERIFICATION_NOT_ALLOWED`. GIVEN the setting is true THEN release succeeds, the result record is marked `self_verified`, and the fact is included on the printed report footer and in REP-009. GIVEN the setting is changed THEN it is audited with actor and reason. **Perm** `facility.policy.manage`. **Audit** Setting change + each self-verified release. **Dep** LAB-015. **Test** Both configurations.

**LAB-017 · Correct or amend a released result · P0 · `LAB_VERIFIER`; secondary `SUPERVISOR`** **Story** As the lab in-charge I want to correct a released result without erasing what the clinician already saw. **Pre** Item `RELEASED`. **Flow** Create a new result version with corrected values + mandatory reason → previous version retained and marked superseded → the item stays `RELEASED` but at version n+1 → **the ordering clinician is alerted explicitly** and, if the encounter is already signed, an addendum is created noting the corrected result (LAB-023). **AC** GIVEN a released Hb of 3.2 corrected to 13.2 THEN both versions are retained and visible, the report prints "AMENDED RESULT — supersedes version 1 released at [time]" with both values, and the clinician receives a high-visibility alert in their worklist that persists until acknowledged. GIVEN a signed encounter THEN an addendum is created automatically referencing the amendment (content authored by the system, attributed to the lab). GIVEN an amendment THEN the audit records both value sets, actor and reason. GIVEN a patient report was already printed THEN the reprint carries the amended marker and the print history shows both events. **Perm** `lab.result.amend`. **Data** `LabResult` versions. **Audit** High-value. **Err** Amending after the patient has been treated → alert must be unmissable; repeated amendments. **UI** Red banner on the result; acknowledgement required by the clinician (recorded). **Dep** LAB-023, AUD-008. **Test** Acknowledgement persistence; print markers.

**LAB-018 · Result-ready signalling to the clinician · P0 · `SYSTEM`** **Story** As the platform I want to tell the ordering clinician the moment results are usable, so the patient is called back promptly. **Trig** Item release (LAB-015) or last pending item reaching a terminal state. **Flow** On release: if the encounter is `AWAITING_RESULTS` and all items of at least one order are terminal → encounter `AWAITING_RESULTS → RESULTS_READY`; queue entry `ON_HOLD → READY_TO_RESUME`; the clinician's worklist badge increments; if the clinician is off shift, the patient also appears on the department-level ready list. **AC** GIVEN an encounter awaiting three tests WHEN the first is released THEN the encounter remains `AWAITING_RESULTS` and the clinician's row shows "1 of 3 results ready" (partial visibility is permitted and results are readable immediately). GIVEN the last pending item is released THEN within 30 seconds the encounter is `RESULTS_READY` and the patient appears in "Ready to review". GIVEN the last item is instead cancelled or terminally rejected THEN the encounter still becomes `RESULTS_READY` with an indicator explaining why, so the patient never stalls. GIVEN a signed encounter THEN no state change occurs and LAB-023 applies instead. **Data** `Encounter.state`, `QueueEntry.state`. **Audit** State transitions with the triggering event. **Err** Clinician deactivated → department-level fallback; multiple orders across two clinicians → each clinician is signalled for their own orders. **Dep** ENC-016, QUE-006. **Test** Partial vs full readiness; cancellation-driven readiness.

**LAB-019 · Clinician views results inside the encounter · P0 · `CLINICIAN`,`MIDWIFE`** **AC** GIVEN a resumed encounter with released results THEN the results appear inline in the Investigations section showing test, analyte, value, unit, reference range, flag, released time and verifier, without leaving the encounter. GIVEN an unreleased result THEN the clinician sees only the status (e.g. "sample collected 14:20"), never the unverified value. GIVEN previous results for the same test from earlier visits THEN a compact trend (last 3 values with dates) is shown for numeric analytes — values only, **no interpretation**. GIVEN the clinician views results THEN an access-audit event is written. **Perm** `lab.result.read`. **Dep** LAB-015, ENC-002. **Test** Unreleased-value invisibility.

**LAB-020 · Print the laboratory report · P0 · `LAB_TECH`,`RECEPTIONIST`,`CLINICIAN`** **AC** GIVEN released items WHEN printed THEN the report shows the facility header, patient identifiers, order date, specimen type and collection time, each test with values/units/ranges/flags, comments, the ordering clinician, the entering technician, the verifier and release timestamp, an amended marker if applicable, a self-verified marker if applicable, and a "results relate only to the specimen tested" footer. GIVEN unreleased items on the same order THEN they are listed as "pending" rather than omitted. GIVEN a reprint THEN it is audited. GIVEN a patient collecting results in person THEN the receptionist can print without seeing the clinician's notes (payload authorisation). **Perm** `lab.result.print`. **Dep** TEN-003, RCP-004. **OOS** Emailing/WhatsApping results. **Test** Role-scoped print payload; A5/A4 snapshots.

**LAB-021 · Ageing and stuck-order monitoring · P0 · `LAB_TECH`,`SUPERVISOR`,`CLINICIAN`** **Story** As a supervisor I want to see orders that are stuck so no patient is forgotten in the lab loop. **Value** The explicit anti-dead-end guarantee. **AC** GIVEN an item in `AWAITING_PAYMENT` for more than 60 minutes THEN it appears on the reception/cashier "unpaid lab" list naming the patient and amount. GIVEN an item in `READY_FOR_COLLECTION` beyond its turnaround target THEN it is flagged in the lab queue and on the supervisor dashboard. GIVEN an item in `RESULT_ENTERED` for more than 60 minutes THEN it appears as "awaiting verification" on the supervisor dashboard. GIVEN any item non-terminal for more than 24 hours THEN it appears on a daily "stuck orders" report with the patient, ordering clinician, state and age. GIVEN a facility with zero stuck orders THEN the dashboard shows an explicit zero. **Perm** `lab.queue.read`/`supervisor.dashboard`. **Dep** QUE-011, REP-009. **Test** Clock-controlled ageing at each state.

**LAB-022 · Cancel an order or item · P0 · `CLINICIAN`(orderer), `SUPERVISOR`; secondary `LAB_TECH`** **AC** GIVEN an item not yet collected WHEN the ordering clinician cancels it with a reason THEN the item is `CANCELLED`, its unpaid invoice line is voided, and the lab queue removes it. GIVEN an item already collected WHEN cancellation is requested THEN it requires `SUPERVISOR` approval with a reason and the charge remains payable unless explicitly credited (BIL-010). GIVEN a paid item that is cancelled THEN a credit note is created and the refund is handled through PAY-008; the money is never silently retained or silently refunded. GIVEN cancellation of the last pending item THEN the encounter's awaiting-results dependency resolves (LAB-018). **Perm** `lab.order.cancel`. **Audit** Reason mandatory. **Test** Financial consequence matrix (unpaid/paid × collected/not collected).

**LAB-023 · Late results after the encounter is signed · P0 · `SYSTEM`; secondary `CLINICIAN`** **Story** As a clinician who signed and sent the patient home, I want late results brought to my attention and attached to the record. **AC** GIVEN a signed encounter with a pending order WHEN the result is released THEN an addendum of type `LATE_RESULT` is attached to the encounter containing a reference to the result (not a rewrite of the note), the signing clinician receives a persistent "unreviewed result" item in their worklist, and the item remains until they acknowledge it. GIVEN acknowledgement THEN the clinician may add a clinical addendum (ENC-023) and/or create a follow-up appointment (APT-001), and the acknowledgement is audited with a timestamp. GIVEN an abnormal-flagged late result THEN it is sorted to the top of the unreviewed list (a display order only — **no clinical interpretation**). GIVEN no acknowledgement within 48 hours THEN it appears on the supervisor dashboard. **Data** `EncounterAddendum`, `ResultAcknowledgement`. **Audit** Acknowledgement. **Dep** ENC-018, ENC-023. **Test** Persistence until acknowledged; supervisor escalation.

**LAB-024 · Walk-in / external-request lab order · P1 · `LAB_TECH`,`RECEPTIONIST`** **Story** As a lab technician I want to register a test for a patient who arrives with a request from elsewhere, so we can serve and charge them without a consultation. **Flow** Create a `LabOrder` with `external_requester_name`, `external_facility` (free text) and no encounter; visit type `LAB_ONLY` → normal payment/collection/result/release loop → release makes the report printable; there is no clinician-resume step. **AC** GIVEN an external order THEN it requires no encounter and the report prints "Requested by: [external requester]". GIVEN release THEN the patient/reception is notified via the reception "results ready for collection" list. GIVEN a walk-in order THEN charges follow the same gate policy. **Perm** `lab.order.create.external`. **Dep** LAB-002, REC-004. **OOS** Sending results back to the external facility electronically. **Test** Encounter-free path integrity.

**LAB-025 · Refer a test to an external laboratory · P2 · `LAB_TECH`** **AC** GIVEN a test the facility cannot perform THEN the item can be marked `REFERRED_OUT` with the destination lab name, dispatch time and a reference; the item remains non-terminal and appears on the ageing report; results returned on paper can be entered as a text result with an attached scanned document reference and released normally, marked "performed externally at [name]". **Perm** `lab.refer_out`. **OOS** Electronic integration with external labs. **Test** Ageing inclusion.

---

## EPIC 9 — DIAGNOSIS AND TREATMENT (`DX`)

**DX-001 · Record working diagnosis · P0 · `CLINICIAN`,`MIDWIFE`** **AC** GIVEN an open encounter THEN the clinician can record one or more working (provisional) diagnoses, each coded (CAT-004) or free text, with an optional certainty note. GIVEN a working diagnosis THEN it is clearly labelled "working" in the UI and on any draft print, and it is **not** counted in the diagnosis statistics report (REP-014). GIVEN investigations are ordered THEN a working diagnosis is encouraged but not mandatory. **Data** `Diagnosis(type=WORKING)`. **Dep** CAT-004. **Test** Report exclusion.

**DX-002 · Record final diagnosis · P0 · `CLINICIAN`,`MIDWIFE`** **AC** GIVEN an encounter being signed THEN at least one final diagnosis is required, or an explicit `NO_DIAGNOSIS` entry with a mandatory reason (e.g. "referred before diagnosis", "patient declined assessment"). GIVEN multiple final diagnoses THEN exactly one must be marked **primary** and the others secondary. GIVEN a final diagnosis THEN it is counted in REP-014 and appears in the patient's chart history and on the printed note. GIVEN a coded diagnosis THEN its code and label are snapshotted onto the record so later catalogue edits do not rewrite history. **Data** `Diagnosis(type=FINAL, is_primary)`. **Dep** ENC-017. **Test** Primary-uniqueness constraint; sign-blocking.

**DX-003 · Diagnosis certainty and free-text fallback · P1 · `CLINICIAN`** **AC** GIVEN no suitable coded term exists THEN the clinician may enter free text, which saves with `coded=false` and appears in reports grouped as "Uncoded". GIVEN a free-text entry that closely matches a coded term THEN the UI suggests the coded term but never substitutes it automatically. GIVEN more than 20% of a month's diagnoses being uncoded THEN this is surfaced on the admin dashboard as a data-quality note. **Test** No silent substitution.

**DX-004 · Treatment plan and clinical instructions · P0 · `CLINICIAN`,`MIDWIFE`** **AC** GIVEN an encounter THEN the clinician can record a treatment plan as free text (up to 4000 chars) plus structured items: prescriptions (RX), procedures (DX-005), investigations (LAB), referral (DX-007) and follow-up (DX-008). GIVEN patient advice text THEN it is printed on the patient's copy in a clearly separated section. GIVEN signing THEN the plan becomes immutable with the note. **Data** `Encounter.plan`, `Encounter.patient_advice`. **Test** Print separation of clinician-facing vs patient-facing content.

**DX-005 · Order a procedure / nursing treatment · P1 · `CLINICIAN`; secondary `NURSE`** **AC** GIVEN a procedure ordered from the catalogue (CAT-005) THEN a charge is created (per gate policy), a task appears in the treatment-room/nursing worklist with the patient, procedure, instructions and priority, and the encounter shows the procedure as pending. GIVEN the nurse marks it performed THEN the performer, time, batch/lot of any injectable used (free text in V1 unless the item is stocked — OD-15), and any notes are recorded and visible to the clinician. GIVEN the procedure is gated by payment and unpaid THEN the nurse cannot mark it performed and sees the outstanding amount. GIVEN a procedure ordered but not performed by visit closure THEN it appears on the unresolved-tasks report. **Data** `ProcedureOrder`. **Dep** CAT-005, QUE-005. **OOS** Automatic consumable deduction. **Test** Gate enforcement; unresolved reporting.

**DX-006 · Record disposition · P0 · `CLINICIAN`,`MIDWIFE`** **AC** GIVEN signing THEN a disposition is mandatory, chosen from `TREATED_AND_DISCHARGED`, `REVIEW_SCHEDULED`, `REFERRED_OUT`, `ADMITTED_ELSEWHERE`, `LEFT_AGAINST_ADVICE`, `DECEASED`, `OTHER` (+ note). GIVEN `REFERRED_OUT` THEN a referral record is required (DX-007). GIVEN `REVIEW_SCHEDULED` THEN a follow-up date is required (DX-008) and an appointment is offered. GIVEN `DECEASED` THEN the patient deceased flag workflow is offered (PAT-013). GIVEN disposition THEN it is included in the visit summary and REP-002. **Data** `Encounter.disposition`. **Test** Conditional-requirement matrix.

**DX-007 · Create a referral letter · P1 · `CLINICIAN`,`MIDWIFE`** **AC** GIVEN a referral THEN the clinician records the destination facility/specialist (free text), reason for referral, clinical summary (prefilled from the encounter and editable), investigations already done with results, treatment given, and urgency. GIVEN the referral is saved THEN a printable letter is produced with the facility header, patient identifiers, the clinician's name/cadre/licence and signature line, and it is retained on the patient's record. GIVEN a signed encounter THEN the referral content is immutable with it. GIVEN a reprint THEN it is audited. **Data** `Referral`. **Dep** TEN-003. **OOS** Electronic referral transmission, referral tracking/feedback loops. **Test** Prefill accuracy; print snapshot.

**DX-008 · Record follow-up instruction · P0 · `CLINICIAN`,`MIDWIFE`** **AC** GIVEN a follow-up interval or date THEN it is stored on the encounter, printed on the patient's copy, and offered as a one-click appointment creation (APT-001). GIVEN an appointment is created from it THEN the encounter references the appointment. GIVEN no appointment is created THEN the follow-up instruction still prints ("return in 3 days or earlier if worse"). **Dep** APT-001. **Test** Link integrity.

**DX-009 · Sick leave / medical certificate · P2 · `CLINICIAN`** **AC** GIVEN a certificate request THEN the clinician records the number of days, the period, and a generic reason (fit/unfit for duty), producing a printable certificate with the facility header, patient identity, clinician name/cadre/licence, date and a certificate serial number. GIVEN issuance THEN it is recorded on the patient record and audited, and reprints are marked as duplicates. **Data** `MedicalCertificate`. **OOS** Diagnosis disclosure rules per employer. **Test** Serial uniqueness; duplicate marking.

**DX-010 · HMIS-aligned diagnosis grouping for reporting · P2 · `FACILITY_ADMIN`** **AC** GIVEN the diagnosis catalogue THEN each entry may be mapped to an HMIS OPD diagnosis category (aligned to the Uganda outpatient register, HMIS Form 031) so that REP-016 can produce a register-shaped tally. GIVEN unmapped diagnoses THEN they are grouped under "Other" and listed separately so the mapping gap is visible. GIVEN the export THEN it is explicitly labelled as an aid for manual register completion and **not** as a certified HMIS/DHIS2 submission. **Dep** CAT-004, REP-016. **OOS** DHIS2 integration. **Test** Mapping coverage report.

---

## EPIC 10 — PRESCRIPTIONS (`RX`)

**RX-001 · Create a prescription within the encounter · P0 · `CLINICIAN`,`MIDWIFE`** **Story** As a clinician I want to prescribe medicines within the consultation so the pharmacy receives exactly what I intended. **Pre** Encounter `OPEN`; `prescription.create`. **Flow** Open the prescription tray → add items (RX-002) → the prescription exists as `DRAFT` bound to the encounter → activated on signing (RX-005). **AC** GIVEN an open encounter THEN a single `DRAFT` prescription per encounter holds all items (no duplicate drafts). GIVEN a draft prescription THEN it is **not** visible to the pharmacy. GIVEN the encounter is voided THEN the draft is cancelled. **Data** `Prescription(state=DRAFT)`. **Dep** ENC-001. **Test** Pharmacy invisibility of drafts.

**RX-002 · Add a prescription item · P0 · `CLINICIAN`,`MIDWIFE`** **AC** GIVEN the item form THEN the clinician selects a product from the pharmacy catalogue (PHM-001) **or** enters a free-text medicine name (for items the facility does not stock), and records: dose (amount + unit), route (`PO`,`IM`,`IV`,`PR`,`PV`,`TOP`,`INH`,`SL`,`OPTH`,`OTIC`, other), frequency (`OD`,`BD`,`TDS`,`QDS`,`NOCTE`,`PRN`,`STAT`, custom), duration (value + unit), quantity to dispense, and instructions to the patient (free text). GIVEN product, dose, frequency and duration THEN the system **arithmetically** proposes a quantity (dose units × frequency per day × days), which the clinician may override; the proposal is labelled as arithmetic only and performs **no dose checking** (AS-11). GIVEN a free-text medicine THEN the item is flagged `external=true`, cannot be dispensed internally, and prints on an external prescription (RX-007). GIVEN a catalogue product flagged as controlled/Class A THEN it is **not selectable** and the UI states that controlled medicines are not supported in this system (RX-008). GIVEN the patient's recorded allergies THEN they are displayed prominently beside the prescribing form; **no automatic matching or blocking occurs** and the UI must not imply it does. **Data** `PrescriptionItem`. **Err** Quantity zero/negative rejected; duration beyond a configurable maximum (default 90 days) warns. **Test** Quantity arithmetic; controlled-product block; external-item behaviour.

**RX-003 · See allergies and current medications while prescribing · P0 · `CLINICIAN`** **AC** GIVEN the prescribing tray is open THEN the patient's allergies (or NKA / not recorded) and current medications are visible without navigation. GIVEN allergy status is "not recorded" THEN a warning chip is shown and signing is blocked until recorded (ENC-011). GIVEN the platform THEN it performs no interaction or contraindication checking and displays no statement suggesting that it does. **Dep** TRI-004, ENC-010. **Test** UI copy review for any implied CDS.

**RX-004 · Review and edit the prescription before signing · P0 · `CLINICIAN`** **AC** GIVEN a draft prescription THEN items can be edited or removed freely, and a summary shows each item's full sig line ("Amoxicillin 500 mg capsule — 1 cap PO TDS × 5 days = 15 capsules"). GIVEN a duplicate product already on the same prescription THEN a warning is shown requiring confirmation. GIVEN the prescription is empty at signing THEN the encounter signs normally with no prescription created. **Test** Sig-line rendering rules.

**RX-005 · Activate the prescription on signing · P0 · `SYSTEM`** **AC** GIVEN an encounter with a draft prescription WHEN the encounter is signed THEN the prescription becomes `ACTIVE`, records the prescriber identity snapshot (name, cadre, licence), and appears in the pharmacy dispensing queue within 15 seconds. GIVEN activation THEN the prescription content becomes immutable; changes require cancellation and a new prescription (RX-009) or a signed addendum. GIVEN activation THEN charges are **not** created yet (charging happens at dispensing, DSP-007, because quantities may change with availability). GIVEN the pharmacy module is disabled THEN activation still occurs and only the printed external prescription path applies. **Data** `Prescription.state`, prescriber snapshot. **Audit** Activation with item list. **Dep** ENC-017, DSP-001. **Test** Fan-out timing; immutability.

**RX-006 · View prescription history · P1 · `CLINICIAN`,`PHARMACIST`** **AC** GIVEN a patient chart THEN prescriptions from previous visits are listed with date, prescriber, items, and dispensing status (fully/partially/not dispensed). GIVEN an item dispensed THEN the dispensed quantity, batch and date are shown to authorised roles. GIVEN a pharmacist THEN they see prescriptions and allergies but not the full clinical note. **Dep** PAT-009, DSP-012. **Test** Role-scoped payload.

**RX-007 · Print a prescription · P0 · `CLINICIAN`,`PHARMACIST`,`RECEPTIONIST`** **AC** GIVEN an active prescription WHEN printed THEN the document contains the facility header, patient name/number/age/sex (and weight for under-5s), date, each item with full sig, quantity, prescriber name/cadre/licence number, signature line, and a prescription serial number. GIVEN items flagged `external=true` THEN they print on the prescription clearly marked "not dispensed here". GIVEN a reprint THEN it is marked as a duplicate copy and audited. GIVEN a draft prescription THEN printing is blocked. **Dep** TEN-003, USR-003. **Test** Under-5 weight presence; duplicate marking.

**RX-008 · Controlled / Class A medicines are out of scope · P0 · `SYSTEM`** **Story** As the platform I must refuse to handle controlled medicines because V1 cannot satisfy the statutory register and custody requirements. **AC** GIVEN a catalogue product flagged `controlled=true` THEN it cannot be added to a prescription, cannot be received into stock, cannot be dispensed, and cannot be sold, in every code path, with the message "Controlled medicines are not supported in KlinKlik V1 — use your paper controlled-drugs register". GIVEN an attempt via the API THEN 403 `CONTROLLED_NOT_SUPPORTED`. GIVEN an import of catalogue data containing controlled items THEN they are imported as inactive and flagged, never silently enabled. GIVEN the flag THEN only `ORG_OWNER` may set or clear it, and every change is audited. **Data** `Product.controlled`. **Audit** Flag changes; blocked attempts (to detect demand). **Dep** PHM-001, DSP-003. **OOS** Any controlled-drug workflow. **Test** All four code paths refuse.

**RX-009 · Cancel or discontinue a prescription · P1 · `CLINICIAN`(prescriber), `SUPERVISOR`** **AC** GIVEN an `ACTIVE` prescription with no dispensing THEN the prescriber may cancel it with a reason; it becomes `CANCELLED` and disappears from the pharmacy queue with a visible notice to pharmacy. GIVEN partial dispensing has occurred THEN only the undispensed items may be cancelled; dispensed items and their stock movements are untouched. GIVEN cancellation after the pharmacist has started preparing THEN the pharmacist sees an immediate alert on their open dispense screen. **Audit** Reason mandatory. **Test** Race between cancel and dispense (dispense wins if already committed; cancel then fails with 409).

**RX-010 · Repeat / refill an earlier prescription · P2 · `CLINICIAN`** **AC** GIVEN a previous prescription THEN the clinician may copy it into the current encounter as a **draft**, with all items editable and the source prescription referenced. GIVEN a copy THEN it never activates without the current encounter being signed, and the new prescriber is the current clinician. **Test** Provenance recording.

**RX-011 · Nurse/midwife limited prescribing scope · P2 · `FACILITY_ADMIN`** **AC** GIVEN a facility configuration listing products a `MIDWIFE` or `NURSE` may prescribe (e.g. iron/folic acid, paracetamol, ORS) THEN holders of `prescription.create.limited` may prescribe only those products, and attempts to prescribe outside the list are refused with `OUTSIDE_PRESCRIBING_SCOPE`. GIVEN such a prescription THEN it prints with that provider's cadre and licence and is flagged as limited-scope in the audit. **Dep** RX-002, USR-003. **OOS** Any clinical protocol enforcement.

---

## EPIC 11 — PHARMACY CATALOGUE (`PHM`)

**PHM-001 · Create a product · P0 · `PHARMACIST`,`FACILITY_ADMIN`** **AC** GIVEN the product form THEN the user records: generic name (required), brand/trade name (optional), dosage form (`TABLET`,`CAPSULE`,`SYRUP`,`SUSPENSION`,`INJECTION`,`CREAM`,`OINTMENT`,`DROPS`,`INHALER`,`SUPPOSITORY`,`SACHET`,`OTHER`), strength (text, e.g. "500 mg", "125 mg/5 mL"), pack description, dispensing unit (`TABLET`,`CAPSULE`,`ML`,`BOTTLE`,`SACHET`,`VIAL`,`TUBE`,`PIECE`), category (`MEDICINE`,`CONSUMABLE`,`SUNDRY`), prescription-only flag, controlled flag (RX-008), active flag. GIVEN a duplicate generic+strength+form in one facility THEN a warning with the existing product is shown; creation requires confirmation. GIVEN a product THEN it is searchable by generic and brand name. GIVEN creation/edit THEN it is audited. **Data** `Product`. **Err** Strength typed inconsistently ("500mg" vs "500 mg") → normalise on save for search. **OOS** National drug register import, ATC coding. **Test** Search by both names.

**PHM-002 · Set selling price · P0 · `PHARMACIST`,`FACILITY_ADMIN`** **AC** GIVEN a product THEN a selling price per dispensing unit is set per facility, with an optional pack price. GIVEN a dispense or sale THEN the price is snapshotted onto the invoice line so later price changes never alter historical invoices. GIVEN a price change THEN it is audited with old/new and actor and appears in the price-history view. GIVEN a product with no price THEN it cannot be dispensed or sold and appears on the setup-warnings list. **Data** `ProductPrice`. **Dep** CAT-002. **OOS** Automatic margin calculation from cost (P2: display-only margin is allowed if cost is captured in INV-002). **Test** Snapshot immutability.

**PHM-003 · Link products to prescribing · P0 · `SYSTEM`** **AC** GIVEN the prescribing search THEN it returns active, non-controlled products with their form and strength, showing current stock availability as an indicator (`In stock`, `Low`, `Out of stock`) **without exposing exact stock counts to clinicians unless they hold `inventory.read`**. GIVEN an out-of-stock product THEN the clinician may still prescribe it (the patient may buy elsewhere) but sees the indicator. **Dep** RX-002, INV-006. **Test** Indicator accuracy and permission scoping.

**PHM-004 · Deactivate a product · P1 · `PHARMACIST`** **AC** GIVEN a product with zero stock THEN it may be deactivated, disappearing from prescribing, dispensing and sale searches while remaining in historical records and reports. GIVEN a product with stock on hand THEN deactivation is blocked with the quantity shown, requiring adjustment or disposal first. GIVEN reactivation THEN it is audited. **Test** Stock-blocking rule.

**PHM-005 · Product search performance · P1 · `PHARMACIST`,`CLINICIAN`** **AC** GIVEN a catalogue of 3,000 products WHEN a user types three characters THEN results return within 300 ms p95 from the server, ranked by exact-prefix, then generic-name match, then brand match, then frequency of use at that facility. **Test** Latency and ranking.

**PHM-006 · Consumables and sundries · P1 · `PHARMACIST`** **AC** GIVEN category `CONSUMABLE`/`SUNDRY` (gloves, syringes, gauze, cotton, plasters) THEN the item participates in stock, sale and adjustment workflows but is excluded from prescribing search by default and from the "medicines" reports, appearing instead in consumables reporting. **Dep** INV-001. **Test** Search exclusion.

**PHM-007 · Import a starter catalogue · P1 · `FACILITY_ADMIN`** **AC** GIVEN a CSV in the published template THEN the system validates every row before importing any, reports row-level errors with line numbers, and imports only on a clean file or on explicit "import valid rows only". GIVEN a row flagged as controlled THEN it is imported inactive with the controlled flag set. GIVEN an import THEN it is audited with the file name, row counts and actor. **Err** Duplicate rows; malformed prices; encoding issues. **OOS** Automatic mapping to any national register. **Test** All-or-nothing and partial modes.

**PHM-008 · Product dispensing instructions template · P2 · `PHARMACIST`** **AC** GIVEN a product THEN a default patient instruction (e.g. "Take with food") may be stored and is auto-inserted, **editable**, into the dispense label and the prescription instruction field. GIVEN no template THEN nothing is inserted. **Dep** DSP-010. **OOS** Any clinical advice library.

---

## EPIC 12 — INVENTORY AND STOCK (`INV`)

**INV-001 · Stock locations · P1 · `FACILITY_ADMIN`** **AC** GIVEN a facility THEN at least one stock location exists (default "Main Pharmacy"); additional locations (Store, Dispensary, Lab Store, Treatment Room) may be created. GIVEN multiple locations THEN stock balances are tracked per location and dispensing draws from a configured default location. GIVEN a location with stock THEN it cannot be deleted, only deactivated after transfer. **Data** `StockLocation`. **Dep** INV-007. **Test** Per-location balance isolation.

**INV-002 · Receive stock (goods received note) · P0 · `STORE_KEEPER`,`PHARMACIST`** **Story** As a pharmacist I want to record medicines received from a supplier, with batches and expiry dates, so stock and expiry control are accurate. **Pre** Products exist. **Trig** Delivery arrives. **Flow** Create a GRN: supplier name (free text or from a simple supplier list), invoice/delivery-note reference, received date, receiving location, and lines of: product, batch/lot number, expiry date (month precision minimum), quantity received in the dispensing unit, unit cost (optional but recommended), and any pack-to-unit conversion. Save → stock ledger entries created → balances increase. **AC** GIVEN a GRN line with an expiry date in the past WHEN saved THEN it is **rejected** with `EXPIRED_STOCK_CANNOT_BE_RECEIVED`. GIVEN a GRN line with an expiry within 3 months THEN it is accepted with a prominent warning recorded on the GRN. GIVEN a saved GRN THEN each line creates a `StockLedger(IN)` entry referencing the GRN, the batch record is created or incremented, and the balance for that product/batch/location increases by exactly the received quantity. GIVEN the same GRN submitted twice with one idempotency key THEN stock increases once. GIVEN a GRN THEN it is printable and immutable after posting; corrections require a stock adjustment (INV-011) with a reason. **Perm** `inventory.receive`. **Data** `GoodsReceipt`, `GoodsReceiptLine`, `Batch`, `StockLedger`, `StockBalance`. **Audit** Posting with all lines. **Err** Duplicate batch numbers from different suppliers → batch identity is `(product, batch_no, expiry)`; missing expiry on a product that requires it → blocked. **UI** Fast line-entry grid with keyboard navigation; running total. **OOS** Purchase orders, supplier invoices/payables, barcode scanning. **Test** Past-expiry rejection; idempotency; ledger arithmetic.

**INV-003 · Batch and expiry tracking · P0 · `SYSTEM`** **AC** GIVEN any stock movement THEN it is attributed to a specific batch with its expiry date; no movement may exist without a batch for products flagged as batch-tracked (all `MEDICINE` products are batch-tracked by default). GIVEN a batch THEN its remaining quantity per location is always derivable from the ledger and matches the cached balance (a nightly reconciliation job asserts this and raises a discrepancy alert). GIVEN a batch reaching zero THEN it remains visible in history and is excluded from dispensing selection. **Data** `Batch`, `StockLedger`, `StockBalance`. **Test** Ledger-vs-balance reconciliation.

**INV-004 · FEFO batch selection · P0 · `SYSTEM`; secondary `PHARMACIST`** **Story** As a pharmacist I want the system to propose the earliest-expiring usable batch so we don't accumulate expiries. **AC** GIVEN three batches with different expiry dates WHEN a dispense or sale is prepared THEN the system proposes the **non-expired** batch with the earliest expiry that has sufficient quantity, and displays the batch number and expiry. GIVEN insufficient quantity in the earliest batch THEN the system proposes a split across batches in expiry order and shows the split explicitly. GIVEN the pharmacist selects a different (non-expired) batch THEN a reason is required and the deviation is audited and reported (INV-016). GIVEN only expired batches exist THEN the product is treated as out of stock and dispensing is refused (INV-005). **Data** Batch selection recorded on the dispense line. **Audit** FEFO deviations. **Dep** INV-005, DSP-003. **Test** Split-batch arithmetic; deviation audit.

**INV-005 · Expired stock can never be dispensed or sold · P0 · `SYSTEM`**
**Story** As a facility I need absolute certainty that expired medicines cannot leave the pharmacy through this system. **Value** Patient safety and NDA compliance; the highest-severity rule in the product.
**AC**

- GIVEN a batch whose expiry date is before today WHEN it is offered for dispensing, sale, transfer-out to a dispensing location, or prescription fulfilment THEN it is excluded from selection in every interface.
- GIVEN a direct API request specifying an expired batch THEN the request is rejected with 422 `EXPIRED_BATCH` regardless of the caller's role, including `ORG_OWNER` and `SYS_ADMIN`.
- GIVEN **no** configuration setting, permission, capability, reason code, or override parameter exists anywhere in the system that permits dispensing expired stock (verified by a code-level test that no such flag exists and by an API fuzz test asserting refusal).
- GIVEN a batch that expires while reserved in an in-progress dispense THEN the dispense cannot be confirmed and the pharmacist is instructed to reselect a batch.
- GIVEN expired stock on hand THEN the only permitted movements are quarantine (INV-010) and disposal write-off (INV-011).
- GIVEN a dispense attempt on an expired batch THEN the attempt is audited as a blocked action.
  **Perm** No permission grants this. **Data** None created on refusal; audit of the blocked attempt. **Dep** INV-004, DSP-003. **OOS** Any override mechanism — permanently. **Test** **Security-grade test suite**: role matrix × interface matrix × direct API, all refusing; plus a static check that no `allow_expired` flag exists in the codebase.

**INV-006 · Stock balance view · P0 · `PHARMACIST`,`STORE_KEEPER`,`FACILITY_ADMIN`** **AC** GIVEN the stock list THEN it shows, per product: total quantity on hand at the facility, quantity by location, number of batches, earliest expiry, and status chips (`OK`, `LOW`, `OUT`, `EXPIRING_SOON`, `EXPIRED`). GIVEN a product is expanded THEN each batch is listed with batch number, expiry, location and quantity. GIVEN expired batches THEN they are shown in a visually distinct, non-selectable style with the quantity counted separately from usable stock (usable stock excludes expired). GIVEN a search THEN it filters by product name, status and location. **Perm** `inventory.read`. **Test** Usable-vs-total arithmetic.

**INV-007 · Stock transfer between locations · P1 · `STORE_KEEPER`,`PHARMACIST`** **AC** GIVEN stock at the Store THEN a transfer to the Dispensary creates paired ledger entries (OUT at source, IN at destination) preserving batch and expiry, leaving the facility total unchanged. GIVEN an expired batch THEN it may be transferred **only** to a location flagged as quarantine (INV-010). GIVEN a transfer THEN it is audited with actor, batches and quantities. GIVEN insufficient quantity THEN it is rejected. **Data** `StockTransfer`, ledger pairs. **Test** Total-conservation invariant.

**INV-008 · Low-stock threshold and alerts · P0 · `PHARMACIST`,`FACILITY_ADMIN`** **AC** GIVEN a reorder level set per product per facility THEN products at or below it appear on the low-stock list and on the pharmacy dashboard with the current quantity and the level. GIVEN a product with no reorder level THEN it is excluded from alerts and appears on a "thresholds not set" list. GIVEN a dispense that takes stock below the level THEN the product appears on the low-stock list on the next refresh. GIVEN the low-stock list THEN it is exportable to CSV for ordering. **Data** `Product.reorder_level` (per facility). **Dep** REP-012. **Test** Threshold-crossing detection.

**INV-009 · Expiry warnings · P0 · `PHARMACIST`,`FACILITY_ADMIN`** **AC** GIVEN batches expiring within a configurable horizon (default 90 days) THEN they appear on the expiring-stock list with product, batch, expiry, quantity, location and days remaining, sorted by soonest. GIVEN batches already expired THEN they appear on a separate expired list with a prompt to quarantine or write off. GIVEN the pharmacy dashboard THEN it shows counts for both. GIVEN a batch crossing the expiry date overnight THEN it moves from expiring to expired without manual action (evaluated on read; a nightly job refreshes cached flags). **Dep** REP-012. **Test** Date-boundary behaviour at midnight EAT.

**INV-010 · Quarantine expired or damaged stock · P1 · `PHARMACIST`,`STORE_KEEPER`** **AC** GIVEN expired or damaged stock THEN it can be moved to a quarantine location, which is excluded from all availability calculations and from dispensing entirely. GIVEN quarantined stock THEN it remains on the books until written off (INV-011) so it can be counted and reconciled. GIVEN quarantine THEN the reason and actor are recorded. **Data** `StockLocation(is_quarantine=true)`. **Test** Availability exclusion.

**INV-011 · Stock adjustment and write-off with reason · P0 · `PHARMACIST`,`STORE_KEEPER`; approval `FACILITY_ADMIN`** **AC** GIVEN a discrepancy THEN an adjustment can be recorded per product/batch/location with a signed quantity, a mandatory reason (`EXPIRY_DISPOSAL`, `DAMAGE`, `BREAKAGE`, `THEFT_LOSS`, `COUNT_CORRECTION`, `RETURN_TO_SUPPLIER`, `DONATION_OUT`, `OTHER` + note) and an optional reference (disposal certificate number). GIVEN an adjustment above a configurable value threshold THEN it requires `FACILITY_ADMIN` approval before posting, and remains `PENDING_APPROVAL` until then. GIVEN posting THEN a ledger entry is created and the balance changes by exactly that amount; the adjustment record is immutable thereafter. GIVEN a write-off of expired stock THEN the value is reported separately in REP-012 so wastage is visible. GIVEN any adjustment THEN it is audited with the actor, reason and before/after balances. **Data** `StockAdjustment`, ledger. **Err** Adjustment making a balance negative → rejected. **Test** Approval threshold; negative-balance prevention.

**INV-012 · Automatic stock deduction on dispense/sale · P0 · `SYSTEM`** **AC** GIVEN a confirmed dispense or sale THEN a `StockLedger(OUT)` entry is created per batch per line **in the same database transaction** as the dispense record, and the balance decreases accordingly. GIVEN insufficient stock at the moment of confirmation (a race with another dispense) THEN the whole dispense fails atomically with `INSUFFICIENT_STOCK` and the pharmacist is asked to reselect; no partial deduction occurs. GIVEN a reversal (DSP-016) THEN a compensating `IN` entry is created referencing the original, never a deletion. GIVEN any ledger entry THEN it is immutable. **Test** Concurrency race with two pharmacists dispensing the last pack.

**INV-013 · Stock count (physical inventory) · P1 · `PHARMACIST`,`STORE_KEEPER`** **AC** GIVEN a count session THEN the system produces a count sheet (printable) listing products/batches at a location with a blank counted-quantity column and **without showing the system quantity** by default (blind count, configurable). GIVEN counted quantities are entered THEN variances are shown per line with value impact. GIVEN the count is posted THEN adjustments are created automatically with reason `COUNT_CORRECTION` referencing the count session, subject to the approval threshold (INV-011). GIVEN an open count session THEN dispensing at that location is allowed but flagged, and movements during the count are listed so the variance can be interpreted. GIVEN posting THEN the session becomes immutable. **Data** `StockCount`, `StockCountLine`. **Test** Variance arithmetic; movements-during-count reporting.

**INV-014 · Stock ledger / movement history · P0 · `PHARMACIST`,`FACILITY_ADMIN`,`SUPERVISOR`** **AC** GIVEN a product THEN a chronological ledger shows every movement with date/time, type (`IN_GRN`, `OUT_DISPENSE`, `OUT_SALE`, `TRANSFER_IN/OUT`, `ADJUSTMENT`, `REVERSAL`), quantity, batch, location, running balance, actor and source reference (GRN, dispense, sale, adjustment, count). GIVEN the ledger THEN the running balance recomputed from zero equals the current balance (asserted by test and by a nightly job). GIVEN any user with `inventory.read` THEN they can filter by date range, batch and movement type, and export to CSV (audited). **Test** Recomputation invariant.

**INV-015 · Suppliers list · P2 · `STORE_KEEPER`** **AC** GIVEN a simple supplier record (name, contact person, phone, notes) THEN GRNs may reference it, and a supplier view lists all GRNs received from them. GIVEN no supplier record THEN free-text supplier names remain permitted on GRNs. **OOS** Payables, purchase orders, supplier performance analytics.

**INV-016 · FEFO deviation report · P2 · `SUPERVISOR`,`FACILITY_ADMIN`** **AC** GIVEN dispenses where a non-earliest batch was chosen THEN a report lists them with product, chosen batch, earliest available batch, reason, pharmacist and date, so the practice can be reviewed. **Dep** INV-004.

---

## EPIC 13 — PHARMACY DISPENSING AND RETAIL (`DSP`)

**DSP-001 · Pharmacy dispensing queue · P0 · `PHARMACIST`** **AC** GIVEN active prescriptions THEN the pharmacy queue lists them with patient name and number, prescriber, time prescribed, item count, payment status of any related charges, and age. GIVEN a prescription is `ACTIVE` and undispensed THEN it appears within 15 seconds of the encounter being signed. GIVEN a prescription is being prepared by another pharmacist THEN it shows as claimed with that person's name and cannot be opened for dispensing concurrently (409). GIVEN partially dispensed prescriptions THEN they appear in a separate "Partially dispensed" section with the outstanding items listed. GIVEN a prescription older than a configurable window (default 7 days) and undispensed THEN it moves to an "Expired/uncollected" section and stops cluttering the active queue while remaining retrievable. **Perm** `dispense.queue.read`. **Dep** RX-005. **Test** Claim concurrency.

**DSP-002 · Open a prescription and check availability · P0 · `PHARMACIST`** **AC** GIVEN a prescription is opened THEN each item shows the prescribed product, dose, frequency, duration, prescribed quantity, current usable stock (excluding expired), the FEFO-proposed batch(es), the unit price and the line total. GIVEN an item that is out of stock THEN it is marked `OUT_OF_STOCK` with a proposed action (partially dispense, substitute per DSP-006, or not dispense). GIVEN an item that is an external free-text medicine THEN it is displayed as "not stocked here — patient to obtain externally" and excluded from the dispensable set. GIVEN patient allergies THEN they are displayed prominently on the dispensing screen; **no automatic checking occurs**. GIVEN the prescription is opened THEN the pharmacist claims it and an access-audit event is written. **Perm** `dispense.perform`. **Test** Availability accuracy against usable stock.

**DSP-003 · Select batches (FEFO enforced) · P0 · `PHARMACIST`** **AC** GIVEN a dispensable item THEN the FEFO batch is preselected and displayed with batch number and expiry. GIVEN the pharmacist changes the batch THEN only non-expired batches with stock are selectable and a reason is required (INV-004). GIVEN a quantity greater than the selected batch holds THEN the system splits across batches in expiry order and shows each batch and quantity explicitly on the screen and on the label. GIVEN any expired batch THEN it is not selectable anywhere (INV-005). **Dep** INV-004, INV-005. **Test** Split display and label accuracy.

**DSP-004 · Adjust dispensed quantity · P0 · `PHARMACIST`** **AC** GIVEN a prescribed quantity of 15 and only 10 in stock THEN the pharmacist may dispense 10, and the item is recorded as partially dispensed with the outstanding 5 retained on the prescription. GIVEN a dispensed quantity greater than prescribed THEN it is rejected with `EXCEEDS_PRESCRIBED_QUANTITY` (no over-dispensing without a new prescription). GIVEN a reduced quantity THEN the charge is calculated on the dispensed quantity only. GIVEN a quantity change THEN the reason is recorded when it is below the prescribed amount. **Test** Charge-quantity coupling.

**DSP-005 · Record items not dispensed · P0 · `PHARMACIST`** **AC** GIVEN an item that cannot be dispensed THEN the pharmacist records a reason (`OUT_OF_STOCK`, `PATIENT_DECLINED`, `PATIENT_CANNOT_AFFORD`, `PRESCRIBER_CANCELLED`, `NOT_STOCKED`, `OTHER` + note), and no charge is created for it. GIVEN a not-dispensed item THEN the prescribing clinician sees it in their worklist with the reason within 60 seconds, so they can substitute or advise. GIVEN all items are not dispensed THEN the prescription becomes `NOT_DISPENSED` (terminal) with reasons retained. GIVEN out-of-stock reasons THEN they are aggregated into a "missed sales / stock-out impact" report (REP-011). **Dep** REP-011. **Test** Clinician notification; report aggregation.

**DSP-006 · Generic/brand substitution · P1 · `PHARMACIST`** **AC** GIVEN a prescribed product THEN the pharmacist may dispense a different product only when it is flagged as an equivalent (same generic name, same strength, same form) or when explicitly authorised by the prescriber. GIVEN a substitution THEN the substituted product, the reason, and whether the prescriber was consulted (yes/no + who) are recorded, and both the prescribed and dispensed products appear on the label, the receipt and the record. GIVEN a substitution across a different strength or form THEN it is **blocked** and requires a new prescription. GIVEN a substitution THEN the prescriber sees it in their worklist. **Test** Equivalence rule enforcement (same generic+strength+form only).

**DSP-007 · Generate dispensing charges · P0 · `SYSTEM`** **AC** GIVEN the pharmacist confirms the dispensing basket THEN invoice lines are created for exactly the quantities to be dispensed, at the current facility selling price snapshotted per line, referencing the prescription item and the dispense. GIVEN the same basket submitted twice with one idempotency key THEN lines are created once. GIVEN a change to the basket before payment THEN the previous unpaid lines are voided and new ones created, with both actions audited. GIVEN a retail sale (DSP-013) THEN charges are created identically without a prescription reference. **Dep** BIL-001. **Test** Basket-edit line hygiene.

**DSP-008 · Payment gate for medicines · P0 · `SYSTEM`; secondary `CASHIER`,`PHARMACIST`** **AC** GIVEN `MEDICINE=PAY_BEFORE` THEN the dispense record is created in `AWAITING_PAYMENT`, stock is **not** deducted, and the pharmacist cannot confirm handover until the related lines are paid; the screen shows the outstanding amount and the invoice number to give the patient. GIVEN the cashier records payment THEN the dispense becomes confirmable within 15 seconds and the pharmacist's screen updates. GIVEN `PAY_AFTER` THEN the dispense may be confirmed immediately and the charge remains outstanding on the visit invoice. GIVEN an override by `billing.gate.override` THEN the dispense proceeds, the charge remains outstanding, and actor + reason are audited. GIVEN a pharmacist who also holds `CASHIER` THEN they may take payment in the same session; the payment and the dispense are separate audited records. **Dep** TEN-006, PAY-012. **Test** No-stock-deduction-before-payment assertion.

**DSP-009 · Confirm dispense (handover) · P0 · `PHARMACIST`** **Story** As a pharmacist I want to confirm that the medicines were physically handed over, which is the moment stock leaves. **AC** GIVEN a payment-cleared (or non-gated) basket WHEN the pharmacist confirms THEN, in a single transaction: the `Dispense` record is created with lines, batches and quantities; stock ledger OUT entries are written; balances decrease; the prescription state updates to `DISPENSED` or `PARTIALLY_DISPENSED`; the dispenser identity and timestamp are recorded; and the record becomes immutable. GIVEN insufficient stock at confirmation THEN the entire transaction fails with no partial effect and the pharmacist reselects. GIVEN confirmation THEN the label(s) and receipt become printable. GIVEN a duplicate confirmation with the same idempotency key THEN exactly one dispense exists and stock is deducted once. GIVEN confirmation THEN an audit event records all lines, batches and quantities. **Perm** `dispense.perform`. **Data** `Dispense`, `DispenseLine`, `StockLedger`, `Prescription.state`. **Test** Atomicity under injected failure; idempotency.

**DSP-010 · Print dispensing label · P0 · `PHARMACIST`** **AC** GIVEN a confirmed dispense THEN a label per item is printable containing: facility name, patient name, date, product name and strength, quantity dispensed, the sig in plain language (e.g. "Take ONE tablet THREE times a day for 5 days"), any product instruction (PHM-008), batch number and expiry, and the dispenser's initials. GIVEN a syrup or suspension THEN the label includes the volume and the measuring instruction where provided. GIVEN a reprint THEN it is permitted and audited. GIVEN a label printer is unavailable THEN a compact A5 "medicines given" sheet can be printed instead, listing all items. **Dep** TEN-003, RCP-004. **Test** Sig rendering from structured fields; snapshot per layout.

**DSP-011 · Record counselling and receiver · P1 · `PHARMACIST`** **AC** GIVEN handover THEN the pharmacist records who received the medicines (`PATIENT`, `GUARDIAN`, `RELATIVE` + name) and ticks the counselling points covered from a facility-configurable list (dose, timing, food, storage, side-effects to watch, completion of course). GIVEN counselling is not recorded THEN the dispense still completes but the omission is reported in REP-011. GIVEN a guardian receiving on behalf of a patient THEN their name is stored and printed on the receipt. **Data** `Dispense.received_by_*`, `counselling_points[]`. **OOS** Counselling content library.

**DSP-012 · Dispensing history · P1 · `PHARMACIST`,`CLINICIAN`** **AC** GIVEN a patient THEN all dispenses are listed with date, items, quantities, batches, dispenser and prescriber, filtered by date range. GIVEN a clinician THEN they see dispensing history in the encounter context (ENC-010 prefill source). GIVEN a batch recall scenario THEN the pharmacist can search dispenses by batch number to identify affected patients. **Perm** `dispense.read`. **Test** Batch-based lookup.

**DSP-013 · Over-the-counter retail sale · P0 · `PHARMACIST`** **Story** As a pharmacist I want to sell directly to a walk-in customer without a clinical visit, because that is a large part of daily revenue. **Flow** New sale → optional customer (existing patient, or name-only, or anonymous) → add products with quantity (FEFO batches) → totals → payment (cash/manual MoMo) → confirm → stock deducted, receipt printed. **AC** GIVEN an anonymous sale THEN no patient record is required and the sale completes with a receipt. GIVEN a prescription-only product (PHM-001 flag) THEN selling it requires either a linked prescription or a recorded reason with the pharmacist's acknowledgement, and such sales are listed on a separate report (this is a control, not a prohibition — OD-13). GIVEN a controlled product THEN the sale is refused (RX-008). GIVEN a sale THEN it creates an invoice, a payment and a receipt with the same rigour as clinical billing, and deducts stock atomically. GIVEN a sale to an identified patient THEN it appears in their dispensing history. **Dep** INV-012, PAY-002, RCP-001. **Test** Anonymous-sale completeness; POM control.

**DSP-014 · Dispensing log for inspection · P1 · `PHARMACIST`,`FACILITY_ADMIN`** **AC** GIVEN a date range THEN a chronological dispensing log can be produced and printed/exported containing: date/time, patient name or "OTC", product, strength, quantity, batch, expiry, prescriber (or "OTC"), dispenser, and prescription reference — the fields a National Drug Authority inspection or an internal audit would expect from a dispensing register. GIVEN the export THEN it is audited (AUD-009). GIVEN controlled medicines THEN they are absent because they are unsupported (RX-008), and the log states this explicitly so no one assumes coverage. **Dep** REP-011. **Test** Field completeness; export audit.

**DSP-015 · Expired-stock dispensing is impossible (dispense-path assertion) · P0 · `SYSTEM`** **AC** GIVEN every dispensing and sale entry point (prescription dispense, retail sale, procedure consumable use) THEN expired batches are absent from selection and refused by the API (INV-005). GIVEN a dispense prepared before midnight and confirmed after a batch expires THEN confirmation is refused and the pharmacist must reselect. GIVEN a test suite THEN it asserts refusal across all entry points for all roles. **Dep** INV-005. **Test** Midnight-boundary case.

**DSP-016 · Reverse or correct a dispense · P1 · `PHARMACIST` with `SUPERVISOR` approval** **AC** GIVEN a dispense recorded in error (wrong patient, wrong product) and the medicines are physically returned THEN a reversal creates compensating stock IN entries referencing the original dispense, marks the dispense `REVERSED` with a mandatory reason, and either voids the unpaid charge or triggers a credit/refund path (PAY-008) if paid. GIVEN medicines that were **not** returned THEN reversal is refused and the correction must be handled as a write-off (INV-011) so stock records remain truthful. GIVEN a reversal THEN the original record is retained in full and both records are linked and audited. GIVEN a reversal THEN returned stock re-enters the **same batch** and remains subject to expiry rules. **Perm** `dispense.reverse`. **Test** Returned-vs-not-returned branches; financial consequence.

---

## EPIC 14 — BILLING AND INVOICING (`BIL`)

**BIL-001 · Automatic charge capture from clinical events · P0 · `SYSTEM`** **Story** As a facility I want every chargeable act to raise a charge automatically so we stop losing revenue to forgetfulness. **AC** GIVEN a chargeable event (check-in consultation REC-005, lab order LAB-004, procedure order DX-005, dispense/sale DSP-007) THEN an invoice line is created on the visit's open invoice (or a new one if none exists) within the same transaction as the clinical event where possible, or via a guaranteed-delivery event handler otherwise. GIVEN the clinical event fails THEN no charge is created. GIVEN the charge creation fails THEN the failure is logged, the clinical event still succeeds, and the missing charge appears on the unbilled-events exception report (REP-007) within 15 minutes. GIVEN any charge THEN it records `source_type`, `source_id`, the price snapshot, the service/product reference, the gate policy at charge time, and the creating actor. **Data** `Invoice`, `InvoiceLine`. **Audit** Each line with source. **Test** Failure-mode reconciliation; no orphan charges.

**BIL-002 · One open invoice per visit · P0 · `SYSTEM`** **AC** GIVEN a visit THEN at most one invoice is in a non-terminal state at any time, accumulating consultation, lab, procedure and medicine lines. GIVEN a retail sale with no visit THEN a standalone invoice is created. GIVEN a concurrent charge from two sources THEN both lines land on the same invoice without duplication or deadlock (row-level locking with retry). GIVEN an invoice THEN the displayed total always equals the sum of its non-voided lines (asserted by test and a nightly integrity job). **Test** Concurrency; arithmetic invariant.

**BIL-003 · Add a manual invoice line · P1 · `CASHIER`,`FACILITY_ADMIN`** **AC** GIVEN a service in the catalogue THEN a cashier may add it manually to a visit's invoice with a quantity, and the price is taken from the catalogue (not typed). GIVEN a service not in the catalogue THEN a free-text line with a typed amount requires `billing.manual_line` and a mandatory description and reason, and such lines are listed on a monthly review report. GIVEN any manual line THEN it is audited with actor and reason. **Test** Free-text line reporting.

**BIL-004 · Void an invoice line · P0 · `CASHIER`,`FACILITY_ADMIN`** **AC** GIVEN an unpaid line THEN it may be voided with a mandatory reason; the line remains visible marked `VOID` with strike-through and is excluded from totals. GIVEN a paid or partially paid line THEN voiding is refused; a credit note (BIL-010) or payment reversal (PAY-008) is required. GIVEN voiding a lab or medicine line THEN the corresponding clinical record's payment gate re-evaluates (e.g. the lab item may return to `AWAITING_PAYMENT` or become gate-free). GIVEN voiding THEN it is audited with before/after totals. **Test** Gate re-evaluation.

**BIL-005 · Issue / finalise an invoice · P0 · `SYSTEM`,`CASHIER`** **AC** GIVEN an invoice with at least one line THEN it is `ISSUED` and visible to the cashier with a facility invoice number (TEN-007). GIVEN an issued invoice THEN new lines may still be added while it is unpaid or partially paid (outpatient reality), and every addition updates the total and is audited. GIVEN a fully paid invoice THEN adding a line moves it back to `PARTIALLY_PAID` with the new balance, and the cashier and the patient's balance display update immediately. **Test** Post-payment line addition.

**BIL-006 · Cashier's awaiting-payment list · P0 · `CASHIER`** **AC** GIVEN issued invoices with an outstanding balance THEN they appear in the cashier's list with patient name and number, invoice number, total, paid, balance, the services included (grouped by type), the age of the invoice, and where the patient currently is (QUE-010). GIVEN a new charge is created anywhere in the facility THEN it appears in the cashier's list within 15 seconds. GIVEN a gated service blocking a patient (lab awaiting payment, medicines awaiting payment) THEN the row is marked as blocking so the cashier prioritises it. GIVEN a search by patient name, number or invoice number THEN the invoice is found immediately. **Perm** `invoice.read`. **Test** Freshness and blocking indicators.

**BIL-007 · View invoice detail · P0 · `CASHIER`,`FACILITY_ADMIN`,`SUPERVISOR`; limited `RECEPTIONIST`** **AC** GIVEN an invoice THEN its detail shows every line with description, quantity, unit price, line total, source (which order/dispense created it), status, plus payments made with method, reference, date and receipt number, and the outstanding balance. GIVEN a receptionist THEN they see totals and balance but not clinical descriptions beyond service names. GIVEN a voided line THEN it is displayed with its reason and the voiding actor. **Test** Role-scoped payload.

**BIL-008 · Patient balance across visits · P1 · `CASHIER`,`RECEPTIONIST`** **AC** GIVEN a patient with unpaid invoices from previous visits THEN their total outstanding balance is displayed on the patient header for finance-capable roles and at check-in (REC-001). GIVEN a payment THEN it may be allocated across invoices oldest-first or explicitly chosen (PAY-005). GIVEN a facility policy requiring settlement before new services THEN check-in shows a blocking warning that `FACILITY_ADMIN` can override with a reason (BIL-014). **Test** Multi-invoice arithmetic.

**BIL-009 · Discounts, waivers and exemptions · P1 · `FACILITY_ADMIN`,`SUPERVISOR`** **AC** GIVEN authority THEN a discount may be applied to a line or an invoice as a percentage or a fixed amount, with a mandatory reason from a configurable list (`STAFF`, `INDIGENT`, `GOODWILL`, `PROMOTION`, `MANAGEMENT_DECISION`, `OTHER` + note). GIVEN a discount THEN the original amount, the discount and the net are all retained and printed, so nothing is silently rewritten. GIVEN a full waiver THEN the invoice reaches zero balance through a waiver record, **never** by deleting lines. GIVEN a discount above a configurable threshold THEN it requires `FACILITY_ADMIN`. GIVEN any discount THEN it is audited and appears on a discounts report (REP-008). **Data** `InvoiceDiscount`. **Test** Threshold enforcement; report totals.

**BIL-010 · Credit note · P1 · `FACILITY_ADMIN`** **AC** GIVEN a paid line for a service that was not delivered (cancelled lab test after payment, reversed dispense) THEN a credit note is created against the invoice with a mandatory reason and reference to the original line, reducing the amount due or creating a refundable credit. GIVEN a credit note THEN the original invoice and payment records are unchanged, the credit note has its own number, and it is printable. GIVEN a refundable credit THEN the refund is executed as a payment reversal or a cash refund record (PAY-008), never by editing the original payment. **Test** Ledger consistency between invoice, payment and credit note.

**BIL-011 · Invoice line grouping by category on print · P0 · `CASHIER`** **AC** GIVEN an invoice with mixed lines THEN the printed invoice groups them under Consultation, Laboratory, Procedures and Medicines with subtotals, then the grand total, amount paid and balance. GIVEN medicines THEN each line shows the product, strength, quantity and unit price. GIVEN laboratory THEN each test is named individually. **Dep** RCP-002. **Test** Grouping snapshot.

**BIL-012 · Print or reprint an invoice · P1 · `CASHIER`** **AC** GIVEN an invoice THEN it can be printed showing the facility header, invoice number, date, patient identity, grouped lines, totals, payments and balance, plus "This is not a receipt" when unpaid. GIVEN a reprint THEN it is audited. **Dep** TEN-003. **Test** Unpaid-marking.

**BIL-013 · Prevent duplicate charges · P0 · `SYSTEM`** **AC** GIVEN a charge source (order item, dispense line, visit consultation) THEN a database unique constraint on `(invoice, source_type, source_id)` prevents a second line for the same source. GIVEN a retried request THEN the constraint plus idempotency returns the original line without error. GIVEN a legitimate repeat of the same service (a second CBC the same day) THEN it has a distinct source ID and is charged separately. GIVEN a duplicate-charge attempt THEN it is logged for monitoring. **Test** Constraint behaviour under retry and under legitimate repeats.

**BIL-014 · Outstanding balance at visit closure · P0 · `CASHIER`,`FACILITY_ADMIN`** **AC** GIVEN a visit with an outstanding balance WHEN closure is attempted THEN it is blocked with the amount and the blocking lines listed. GIVEN `FACILITY_ADMIN` authority THEN the visit may be closed with the balance recorded as a debt/credit-sale with a mandatory reason and a follow-up flag, and the amount appears on the debtors report (REP-008). GIVEN a waiver instead THEN BIL-009 applies and the balance becomes zero through a waiver record. GIVEN any of these THEN the audit records which path was used, by whom and why. **Dep** REC-011. **Test** All three closure paths.

---

## EPIC 15 — CASHIER AND PAYMENTS (`PAY`)

**PAY-001 · Payment methods configuration · P0 · `FACILITY_ADMIN`** **AC** GIVEN the facility THEN the enabled payment methods are `CASH` (always), `MOBILE_MONEY_MANUAL` (with a required transaction-reference field and an optional provider label such as MTN/Airtel), and up to three facility-defined manual methods (e.g. `BANK_DEPOSIT_SLIP`, `POS_CARD_TERMINAL`, `COMPANY_ACCOUNT`) each with a configurable reference-required flag. GIVEN a method THEN it can be deactivated without affecting historical payments. GIVEN no direct integration THEN the UI never claims a payment is verified with a provider — mobile money references are **operator-entered evidence only**. **Data** `PaymentMethodConfig`. **OOS** MoMo/bank/card APIs, automatic reconciliation. **Test** Reference-required enforcement.

**PAY-002 · Record a payment · P0 · `CASHIER`; secondary `PHARMACIST`(retail)** **Story** As a cashier I want to record money received against an invoice so the patient can proceed and our books are right. **Pre** Invoice with a balance; `payment.record`; an open shift if shifts are enabled (PAY-009). **Flow** Open the invoice → enter the amount received → select the method → enter the reference if required → optionally enter the amount tendered for cash to compute change → confirm → payment recorded, allocated (PAY-005), receipt generated and printed (RCP-001), gates released (PAY-012). **AC** GIVEN an invoice with a balance of UGX 45,000 and cash of 50,000 tendered THEN the payment records 45,000 received with 5,000 change displayed, and the invoice becomes `PAID`. GIVEN a mobile-money payment without a reference when the method requires one THEN it is rejected with `REFERENCE_REQUIRED`. GIVEN an amount exceeding the balance THEN it is rejected unless the facility allows credit balances (default: not allowed; the cashier must adjust the amount). GIVEN a payment THEN it is immutable; corrections require reversal (PAY-008). GIVEN a duplicate submission with the same idempotency key THEN exactly one payment exists and one receipt is issued. GIVEN a payment THEN the audit records amount, method, reference, actor, shift, invoice and allocations. GIVEN a recorded payment THEN any gated service is released within 15 seconds. **Perm** `payment.record`. **Data** `Payment`, `PaymentAllocation`, `Receipt`. **Test** Idempotency; over-payment rule; gate release timing.

**PAY-003 · Partial payment · P0 · `CASHIER`** **AC** GIVEN a balance of 60,000 and 20,000 paid THEN the invoice becomes `PARTIALLY_PAID` with a 40,000 balance, a receipt is issued for 20,000 showing the remaining balance, and the patient can return to pay the rest. GIVEN multiple partial payments THEN each has its own receipt and the invoice shows the full payment history. GIVEN partial payment under a `PAY_BEFORE` gate THEN only the specific gated lines that are fully covered by the allocation are released (PAY-005/LAB-005). **Test** Line-level release from partial payment.

**PAY-004 · Payment against multiple invoices · P2 · `CASHIER`** **AC** GIVEN a patient with two outstanding invoices THEN one payment may be allocated across them, with the allocation shown explicitly before confirmation and printed on the receipt. GIVEN no explicit allocation THEN the default is oldest-invoice-first. **Dep** PAY-005.

**PAY-005 · Payment allocation rules · P0 · `SYSTEM`,`CASHIER`** **AC** GIVEN a payment THEN it is allocated to invoice lines with an explicit, deterministic and displayed rule: **gated unpaid lines that are currently blocking a service first (in the order the services were requested), then remaining lines oldest-first**. GIVEN the cashier wants a different allocation THEN they may allocate manually line by line before confirming. GIVEN allocation THEN each `PaymentAllocation` row records the line and the amount, the sum of allocations equals the payment amount exactly, and no line is over-allocated. GIVEN an allocation THEN it is displayed on the receipt so the patient knows what they have paid for. **Test** Sum invariant; blocking-first ordering; manual override.

**PAY-006 · Cash change calculation · P1 · `CASHIER`** **AC** GIVEN cash tendered THEN change is computed and displayed prominently before confirmation and printed on the receipt; the stored payment amount is the amount **received against the invoice**, never the tendered amount. GIVEN tendered less than the amount being paid THEN it is rejected. **Test** Stored-amount correctness.

**PAY-007 · Payment lookup and history · P0 · `CASHIER`,`FACILITY_ADMIN`** **AC** GIVEN a date range, method, cashier or patient filter THEN matching payments are listed with time, patient, invoice, amount, method, reference, cashier, shift and receipt number, and can be exported (audited). GIVEN a receipt number THEN the payment is found directly. **Perm** `payment.read`. **Test** Filter correctness.

**PAY-008 · Payment reversal / correction · P0 · `SUPERVISOR`,`FACILITY_ADMIN`** **Story** As a supervisor I want to reverse a payment recorded in error, in a way that leaves the original visible. **AC** GIVEN a payment THEN it can never be edited or deleted. GIVEN a reversal request with a mandatory reason (`WRONG_AMOUNT`, `WRONG_INVOICE`, `WRONG_PATIENT`, `DUPLICATE_ENTRY`, `SERVICE_NOT_RENDERED_REFUND`, `OTHER` + note) THEN a reversal record is created referencing the original, the allocations are undone, the invoice balance is restored, and any released gates are re-evaluated (services already delivered are not undone but are flagged). GIVEN a reversal THEN both the original receipt and the reversal are retained, a reversal note is printable, and the original receipt is marked reversed on reprint. GIVEN a cash refund THEN it is recorded with the refunding cashier and shift so the drawer reconciles. GIVEN a reversal after the shift is closed THEN it is recorded against the current open shift with a reference to the original shift, and both shift reports show it. GIVEN a reversal THEN it is a high-severity audit event and appears on the daily reversals report reviewed by the owner. **Perm** `payment.reverse` (**not** granted to `CASHIER` by default). **Test** Balance restoration; cross-shift accounting; gate re-evaluation.

**PAY-009 · Cashier shift open/close and reconciliation · P0 · `CASHIER`,`SUPERVISOR`** **AC** GIVEN a cashier starts work THEN they open a shift recording an opening float; payments they record are attributed to that shift. GIVEN shift close THEN the system shows expected totals by method (cash expected = float + cash received − cash refunds), the cashier enters the counted cash, and any variance is computed, requires a comment if non-zero, and is recorded. GIVEN a closed shift THEN it is immutable and a shift report is printable listing every transaction, totals by method, reversals and the variance. GIVEN an attempt to record a payment without an open shift when shifts are enabled THEN it is refused with `NO_OPEN_SHIFT`. GIVEN a shift left open past a configurable period THEN it appears on the supervisor dashboard, and `SUPERVISOR` may force-close it with a reason. GIVEN a variance beyond a configurable threshold THEN the supervisor is alerted. **Data** `CashierShift`. **Test** Expected-total arithmetic including reversals; force-close path.

**PAY-010 · Daily cash-up / handover · P1 · `SUPERVISOR`,`FACILITY_ADMIN`** **AC** GIVEN end of day THEN a facility-level summary aggregates all shifts: total collected by method, number of transactions, refunds/reversals, discounts and waivers granted, outstanding debts created, and the day's revenue by service group. GIVEN the summary THEN it is printable and exportable and reconciles exactly with the sum of shift reports (asserted by test). **Dep** REP-006, REP-010. **Test** Cross-report reconciliation.

**PAY-011 · Duplicate-payment prevention · P0 · `SYSTEM`** **AC** GIVEN a payment submitted twice due to a double click or a network retry THEN the idempotency key ensures one payment and one receipt. GIVEN two payments of the identical amount for the same invoice within 60 seconds by the same cashier without an idempotency match THEN a confirmation prompt appears warning of a possible duplicate, which the cashier must explicitly accept (some patients genuinely pay twice for two people). GIVEN acceptance THEN the second payment is flagged `possible_duplicate` for the daily review report. **Test** Both automatic and heuristic paths.

**PAY-012 · Payment events release gated services · P0 · `SYSTEM`** **AC** GIVEN a payment that fully covers a gated lab item's line THEN the item transitions `AWAITING_PAYMENT → READY_FOR_COLLECTION` and appears in the lab's actionable queue within 15 seconds. GIVEN a payment covering medicine lines THEN the dispense becomes confirmable within 15 seconds. GIVEN a payment covering the consultation THEN any clinician-side warning clears. GIVEN a reversal THEN gates re-evaluate and any not-yet-delivered service returns to its gated state with a visible notice to the affected department. **Dep** LAB-005, DSP-008. **Test** Event propagation latency and reversal behaviour.

**PAY-013 · Mobile money manual reference capture · P0 · `CASHIER`** **AC** GIVEN a mobile-money payment THEN the cashier records the provider label, the transaction reference (validated for a minimum length and uniqueness within the facility over a rolling 90 days) and the payer phone number if given. GIVEN a duplicate reference within the window THEN a warning appears requiring confirmation, because duplicates usually indicate a mis-keyed or reused reference. GIVEN the reference THEN it prints on the receipt and appears in the payments-by-method report so manual reconciliation against the MoMo statement is possible. GIVEN the system THEN it never asserts that the transaction was verified with the provider. **Test** Duplicate-reference warning; receipt content.

**PAY-014 · Payment permissions and segregation of duties · P0 · `SYSTEM`** **AC** GIVEN a `CASHIER` THEN they may record payments and print receipts but **not** reverse payments, apply discounts above the threshold, or void paid lines. GIVEN a user holding both `payment.record` and `payment.reverse` THEN the combination is permitted (small facilities) but is listed on the segregation-of-duties report (REP-013) for owner awareness. GIVEN any privileged financial action THEN it is audited with actor, reason and amount. **Dep** AUTH-008, REP-013. **Test** Capability matrix enforcement.

---

## EPIC 16 — RECEIPTS AND PRINTING (`RCP`)

**RCP-001 · Generate and print a receipt · P0 · `CASHIER`,`PHARMACIST`** **AC** GIVEN a recorded payment THEN a receipt is generated immediately with a unique facility receipt number, containing the facility header (name, address, phone, TIN), receipt number, date/time, patient name and number (or "walk-in" for anonymous sales), the items paid for with amounts (allocation from PAY-005), the total paid, the method and reference, the change given for cash, the remaining balance if any, the cashier's name, and the facility footer text. GIVEN the payment THEN the receipt prints automatically to the configured printer and can be reprinted. GIVEN a reprint THEN it is marked "DUPLICATE" and audited with actor and time. GIVEN a reversed payment THEN reprints are marked "REVERSED" with the reversal date. **Data** `Receipt`. **Test** Numbering uniqueness; duplicate/reversed markings.

**RCP-002 · Print layouts for 80mm thermal and A5/A4 · P0 · `SYSTEM`** **AC** GIVEN a receipt THEN an 80mm thermal layout is provided that prints legibly with a monochrome logo and no clipped content. GIVEN lab reports, invoices, prescriptions, consultation notes and ANC cards THEN A5 or A4 layouts are provided as appropriate. GIVEN any layout THEN page breaks preserve table headers and no content is lost at boundaries. GIVEN a printer that is unavailable THEN a print-preview view is shown that can be printed later or photographed, and the document is retrievable from the record at any time. **Test** Snapshot tests per document per size; long-content page-break test.

**RCP-003 · Reprint with audit · P0 · `SYSTEM`** **AC** GIVEN any printable clinical or financial document THEN reprinting is permitted to authorised roles and every print and reprint writes an audit event with document type, record ID, actor, timestamp and copy number. GIVEN a document's print history THEN it is viewable by `SUPERVISOR`/`FACILITY_ADMIN`. GIVEN clinical documents THEN reprint counts appear in the access-review report (AUD-011). **Dep** AUD-009. **Test** Copy numbering.

**RCP-004 · Document header/footer service · P0 · `SYSTEM`** **AC** GIVEN any printable document THEN it renders the facility header from TEN-003 and a standard footer containing the page number, the generating user, the generation timestamp, and (for clinical documents) the phrase identifying the source system and record version. GIVEN a facility profile change THEN newly generated documents use the new values while previously generated PDFs stored on records (if any) remain as generated. **Test** Header presence across all document types.

**RCP-005 · Printer configuration per workstation · P1 · `FACILITY_ADMIN`** **AC** GIVEN a workstation THEN a default document-to-printer mapping (receipts → thermal, reports → A4) can be stored as a non-PHI local preference and applied through the browser print flow. GIVEN no configuration THEN the standard browser print dialog is used and nothing breaks. **OOS** Direct raw printing/driver integration. **Test** No PHI in stored preferences.

**RCP-006 · Patient visit summary printout · P1 · `RECEPTIONIST`,`CLINICIAN`** **AC** GIVEN a completed visit THEN a one-page patient-facing summary can be printed containing the diagnosis (if the clinician has marked it shareable), the medicines dispensed with instructions, the tests done with results if released, follow-up instructions, the next appointment, and the amount paid. GIVEN clinician-only content (full clerking notes, working differentials) THEN it is excluded from the patient summary. **Test** Content-exclusion assertions.

**RCP-007 · Document numbering and uniqueness · P0 · `SYSTEM`** **AC** GIVEN receipts, invoices, credit notes, lab reports, prescriptions, referrals and certificates THEN each has a unique, sequential, non-reusable number per facility per type. GIVEN concurrent generation THEN no duplicates occur. GIVEN a voided document THEN its number is retired, never reissued. **Dep** TEN-007. **Test** Concurrency and retirement.

---

## EPIC 17 — ANTENATAL CARE (`ANC`)

> ANC in V1 is **documentation and scheduling**, aligned to the structure of the Uganda MoH integrated antenatal record (HMIS Form 071) and the WHO/Uganda eight-contact model. It records what the midwife did and what she observed. **It provides no clinical decision support, no risk scoring, no protocol enforcement and no guidance text** unless the facility has explicitly authored that text itself (OD-09).

**ANC-001 · Enrol a patient in ANC · P0 · `MIDWIFE`; secondary `CLINICIAN`** **AC** GIVEN a pregnant patient THEN the midwife creates an ANC enrolment recording: ANC number (facility sequence, TEN-007), LMP (with a "certain/uncertain" flag) or an ultrasound-based EDD, gravida, para, number of living children, previous pregnancy outcomes summary, blood group if known, and the enrolment date and provider. GIVEN an LMP THEN the EDD is computed as LMP + 280 days and displayed as derived, editable only by entering a clinician-supplied EDD with a reason (e.g. ultrasound dating), in which case both values and the basis are stored. GIVEN an active enrolment THEN a second concurrent enrolment for the same patient is blocked. GIVEN enrolment THEN the patient's chart shows an ANC banner with EDD and current gestational age. GIVEN an obstetric summary that also exists in ENC-013 THEN a single stored record is used by both. **Data** `ANCEnrolment`. **Test** EDD arithmetic; single-active-enrolment constraint.

**ANC-002 · Start an ANC contact/visit · P0 · `MIDWIFE`** **AC** GIVEN an enrolled patient checked in with visit type `ANC` THEN the midwife starts an ANC encounter, which is an `Encounter` of type `ANC` with an attached `ANCVisit` record carrying the contact sequence number (1..8+, auto-incremented and editable) and the visit date. GIVEN a start THEN the gestational age in completed weeks and days is computed from the EDD basis and displayed and stored on the visit. GIVEN a patient not yet enrolled THEN the midwife is prompted to enrol first (ANC-001) in the same flow. GIVEN an ANC encounter THEN all encounter lifecycle rules (draft, autosave, park for results, sign, amend) apply identically (Epic 7). **Data** `ANCVisit`. **Test** GA computation at boundaries; reuse of encounter lifecycle.

**ANC-003 · Maternal, obstetric and medical history · P0 · `MIDWIFE`** **AC** GIVEN the first contact THEN the midwife records: previous pregnancy details (year, outcome, mode of delivery, birth weight, complications) as repeatable rows; medical history (hypertension, diabetes, HIV status and ART if disclosed, TB, epilepsy, sickle cell, surgery); allergies (shared with TRI-004); and family/social history. GIVEN subsequent contacts THEN the history is displayed read-only with an "update history" action that versions the change. GIVEN HIV or other sensitive status THEN it is stored as recorded by the provider with no automatic disclosure in printed documents unless the document is explicitly the ANC card and the facility has enabled it (OD-17). **Test** Version history; sensitive-field print control.

**ANC-004 · ANC vitals and measurements · P0 · `MIDWIFE`,`NURSE`** **AC** GIVEN a contact THEN the provider records BP, pulse, temperature, weight, height (first contact), MUAC, and Hb if tested at point of care, using the shared vitals component (TRI-002) with the same validation. GIVEN weight across contacts THEN the change since the previous contact is displayed as a computed difference **without interpretation**. GIVEN a BP value THEN it is displayed with an out-of-range marker per the configured reference band and no advice text. **Dep** TRI-002. **Test** Shared-component consistency.

**ANC-005 · Risk-factor documentation · P0 · `MIDWIFE`** **AC** GIVEN a facility-configured checklist of risk factors (e.g. age <18 or >35, previous caesarean, previous stillbirth, multiple pregnancy, anaemia, hypertension, diabetes, HIV, previous PPH, grand multiparity) THEN the midwife may tick those present and add free-text notes. GIVEN ticked factors THEN they are displayed prominently on the ANC banner for subsequent contacts and printed on the ANC card. GIVEN the platform THEN it computes **no risk score, no risk category and no recommended action**, and the UI contains no such language. GIVEN a facility that wishes to display its own guidance THEN that text is authored and owned by the facility (OD-09) and is clearly attributed to them. **Data** `ANCRiskFactor[]`. **Test** UI copy audit for absence of CDS language.

**ANC-006 · Obstetric examination · P0 · `MIDWIFE`** **AC** GIVEN a contact at an appropriate gestation THEN the midwife records fundal height (cm), presentation (`CEPHALIC`,`BREECH`,`TRANSVERSE`,`UNDETERMINED`), lie, fetal heart rate (bpm, or `NOT_HEARD` with a note), fetal movements (`PRESENT`,`ABSENT`,`NOT_ASSESSED`), oedema (`NONE`,`MILD`,`MODERATE`,`SEVERE`), pallor, and general examination notes. GIVEN fundal height THEN it is stored with the gestational age at that contact so the pair is retrievable; **no automatic comparison or flagging is performed**. GIVEN FHR outside a configured band THEN a neutral out-of-range marker is displayed with no advice. **Test** Field persistence; absence of derived clinical judgement.

**ANC-007 · ANC investigations · P0 · `MIDWIFE`** **AC** GIVE

# KlinKlik V1 Functional Specification — Continued (Part 3 of 6)

**Resuming at Epic REC.** Parts 1–2 covered executive summary, actors, assumptions, journeys A–F, epic catalogue, Global Story Contract, and epics AUTH, TEN, USR, CAT, PAT (stories AUTH‑001 → PAT‑007).

This part delivers **REC (Reception & Check‑in)**, **QUE (Queue Management)**, and **TRI (Triage)** — 36 stories, plus the Queue‑Entry state machine and the Attendance‑loop handoff rows. Part 4 resumes at ENC.

---

## Reminder: Global Story Contract (applies to every story below, not repeated per story)

| Default           | Rule                                                                                                                                                                                                                                |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Tenancy           | Every query is filtered by `organisation_id` + `facility_id` from the session context, enforced at the PostgreSQL RLS layer, not only in the ORM. Cross‑facility read attempt → 404 (not 403), so record existence is not leaked.   |
| Permission denial | Missing permission → HTTP 403, no partial data, no record IDs in the error body. UI hides the control _and_ the API rejects.                                                                                                        |
| Audit             | Every mutation writes `audit_event(actor_user_id, actor_role, facility_id, entity_type, entity_id, action, before_json, after_json, ip, user_agent, request_id, occurred_at)`. Every PHI read of a patient chart writes `PHI_READ`. |
| Idempotency       | All POSTs that create money, clinical or stock records accept `Idempotency-Key`; replay returns the original 201 body.                                                                                                              |
| Concurrency       | Mutable records return `ETag`; `If-Match` required on PUT/PATCH; mismatch → 409 with server's current version.                                                                                                                      |
| Validation        | Server is authoritative. Client validation is convenience only.                                                                                                                                                                     |
| UI                | List views ≤ 400 ms p95 on 3G‑equivalent, keyboard‑operable, no PHI in localStorage/sessionStorage/IndexedDB, access token in memory only.                                                                                          |
| Tests             | Each story ships: unit tests on the service function, API contract tests incl. 403/404/409, one UI happy path, one negative path, one tenant‑isolation test.                                                                        |

---

# EPIC REC — Reception & Check‑In

Purpose: turn a person standing at the desk into a **Visit** record with a queue position, correct payer type, and correct first destination. Reception never enters clinical content.

---

### REC‑001 — Check in a returning patient and open a Visit

**Epic** REC · **Priority** P0 · **Primary role** RECEPTIONIST · **Secondary** FACILITY_ADMIN, NURSE (small clinics where nurse doubles as reception)

**User story** As a receptionist, I want to check in an existing patient so that a Visit is opened and the patient appears on today's queue for triage.

**Business value** This is the single entry point for the attendance loop. Without it, no downstream record (encounter, invoice, lab order) has a parent, and daily attendance cannot be counted for HMIS 031.

**Pre** Patient record exists in this facility's tenant. Receptionist authenticated with a facility selected. Facility is `ACTIVE` and not closed for the day. Facility has at least one active `Department` flagged as check‑in destination.

**Trig** Receptionist searches the patient (PAT‑003), opens the patient summary, and clicks **Check in**.

**Flow**

1. System shows a check‑in panel: patient name, age, sex, facility patient number, last visit date, outstanding balance (if any), and any allergy flag banner.
2. Receptionist selects **Visit type** (`OUTPATIENT_NEW`, `OUTPATIENT_REVIEW`, `ANC`, `LAB_ONLY`, `PHARMACY_ONLY`, `FOLLOW_UP_RESULTS`).
3. Receptionist selects **Payer type** (`CASH`, `SELF_PAY_MOMO`) — V1 has no insurance.
4. Receptionist optionally types a short **reason for visit** (free text, ≤ 120 chars) — administrative, not a clinical complaint.
5. Receptionist selects **Destination department** — defaults from visit type per TEN‑005 routing rules.
6. Receptionist clicks **Confirm check‑in**.
7. System creates `Visit` (state `OPEN`), creates `QueueEntry` (state `WAITING`, queue = triage queue of destination department), assigns visit number from the facility numbering scheme (TEN‑007), and, if the facility's gating policy is `CHARGE_AT_CHECKIN` (TEN‑006), creates a draft `Invoice` with the consultation line (BIL‑002).
8. System prints/offers the visit slip (RCP‑002) showing visit number, queue token, date, and facility header.

**Alt**

- **A1 Patient already has an OPEN visit today** → system blocks creation, shows the existing visit with its current state and location, and offers "Go to existing visit". See REC‑011.
- **A2 Patient has an outstanding balance from a prior visit** → warning banner with amount and prior visit number; receptionist may proceed (V1 does not hard‑block care for debt) but the warning is audited.
- **A3 Facility gating policy is `PAY_BEFORE_TRIAGE`** → queue entry is created in state `WAITING_PAYMENT` and does not appear on the triage list until the consultation invoice is paid (PAY‑003).
- **A4 Destination department is disabled mid‑session** → validation error, receptionist must pick another.

**AC**

- GIVEN an active patient with no open visit, WHEN the receptionist confirms check‑in with visit type `OUTPATIENT_NEW` and payer `CASH`, THEN a `Visit` is created with `state=OPEN`, `opened_at=now()`, `opened_by=<user>`, and a `QueueEntry` with `state=WAITING` and `queue_type=TRIAGE` exists for the destination department.
- GIVEN the same patient, WHEN the receptionist attempts a second check‑in on the same calendar day at the same facility, THEN the API returns 409 with `code=VISIT_ALREADY_OPEN` and the existing `visit_id`, and no second `Visit` or `QueueEntry` is created.
- GIVEN facility policy `CHARGE_AT_CHECKIN` with an active consultation service priced at UGX 20,000, WHEN check‑in is confirmed, THEN exactly one `Invoice` in state `DRAFT` exists for the visit containing one line `CONSULTATION` at 20,000, and the invoice total equals 20,000.
- GIVEN facility policy `PAY_BEFORE_TRIAGE`, WHEN check‑in is confirmed, THEN the queue entry state is `WAITING_PAYMENT` and the entry is absent from `GET /api/v1/queues/triage`.
- GIVEN two facilities in the same organisation, WHEN a receptionist at Facility B requests the visit created at Facility A, THEN the response is 404.
- GIVEN a check‑in is confirmed, WHEN the audit log is queried, THEN one `VISIT_OPENED` event and one `QUEUE_ENTRY_CREATED` event exist with the actor's user ID and the visit ID.

**Perm** `visit.create` (RECEPTIONIST, FACILITY_ADMIN, NURSE). `visit.read` required to view. Clinicians have `visit.read` but not `visit.create` unless also granted.

**Data** Insert `visit`, `queue_entry`; conditional insert `invoice` + `invoice_line`. Update `patient.last_seen_at`. No clinical fields written.

**Audit** `VISIT_OPENED`, `QUEUE_ENTRY_CREATED`, conditional `INVOICE_DRAFTED`, conditional `OUTSTANDING_BALANCE_OVERRIDDEN` (A2).

**Err** Duplicate open visit → 409. Inactive patient → 422 `PATIENT_INACTIVE`. Missing consultation price for the visit type → 422 `SERVICE_NOT_PRICED` with the service code, and check‑in is refused (no free care by accident). Double‑submit → idempotency key returns the original visit.

**UI** Single screen, no modal chain. Payer and visit type are radio groups, not dropdowns (faster on desk). Confirm button disabled until visit type + destination chosen. After success, focus returns to patient search so the next patient can be handled immediately. Visit number displayed large for verbal call‑out.

**Dep** PAT‑001, PAT‑003, TEN‑005, TEN‑006, TEN‑007, CAT‑002, QUE‑001, BIL‑002.

**OOS** Insurance/scheme selection, appointment matching (APT‑005 handles that), triage vitals, clinical complaint coding, patient photo capture.

**Test** Table test across the 6 visit types × 2 gating policies. Concurrency test: two receptionists check in the same patient simultaneously — exactly one visit created, the other gets 409. Verify invoice is `DRAFT` not `ISSUED`.

---

### REC‑002 — Register and check in a new walk‑in in one flow

**Epic** REC · **P0** · **Primary** RECEPTIONIST

**User story** As a receptionist, I want to register a brand‑new patient and check them in without navigating between two modules, so the desk queue does not back up during morning rush.

**Business value** Roughly 30–40% of daily attendance at a new private clinic is first‑time patients; a two‑module flow doubles desk time per patient.

**Pre** Receptionist has `patient.create` and `visit.create`. Facility active.

**Trig** Patient search (PAT‑003) returns no match; receptionist clicks **Register new patient**.

**Flow**

1. Registration form (PAT‑001 fields: names, sex, DOB or estimated age, phone, village/parish/sub‑county/district, next of kin name + phone).
2. On submit, system runs duplicate detection (PAT‑002) before persisting.
3. If no probable duplicate, patient is created, facility patient number assigned, and the flow continues directly into the REC‑001 check‑in panel with the patient pre‑selected.
4. Receptionist completes visit type, payer, destination and confirms.

**Alt**

- **A1 Probable duplicate found** → candidate list with match score and last visit date; receptionist chooses "Use this patient" (continues to check‑in with the existing record) or "Not the same — create new" (reason captured, audited).
- **A2 Registration succeeds but check‑in fails** (e.g. no priced consultation service) → patient record is retained, receptionist is shown the check‑in error and can retry; no orphaned visit.

**AC**

- GIVEN a completed new‑patient form with no duplicate match, WHEN submitted, THEN a `Patient` is created with a facility patient number matching the configured scheme, AND the UI lands on the check‑in panel with that patient bound, in one navigation step.
- GIVEN a form whose surname + sex + DOB matches an existing patient exactly, WHEN submitted, THEN the API returns 200 with `duplicate_candidates[]` (not 201) and no patient is created until the receptionist resolves the choice.
- GIVEN the receptionist chooses "Not the same", WHEN they supply the override reason, THEN the patient is created AND an audit event `DUPLICATE_OVERRIDE` records the reason text and the candidate IDs rejected.
- GIVEN registration succeeds and check‑in then fails with `SERVICE_NOT_PRICED`, WHEN the receptionist reloads, THEN the patient exists exactly once and zero visits exist for that patient.

**Perm** `patient.create` + `visit.create` both required for the combined flow; a user with only `patient.create` completes registration and stops at the patient summary.

**Data** Insert `patient`, `patient_identifier`, `patient_contact`, then `visit`, `queue_entry`.

**Audit** `PATIENT_CREATED`, optional `DUPLICATE_OVERRIDE`, then REC‑001 events.

**Err** As PAT‑001 plus REC‑001. Network failure between the two writes must not create a visit without a patient (single transaction boundary for patient creation; visit creation is a separate, retryable transaction).

**UI** Two‑pane: form on the left, live duplicate‑candidate panel on the right that updates as surname and DOB are typed (debounced 400 ms). Age can be entered as years when DOB unknown — system stores `dob_estimated=true`, common in Uganda where DOB is often unknown for adults.

**Dep** PAT‑001, PAT‑002, PAT‑004, REC‑001.

**OOS** NIN verification against NIRA, biometric capture, photograph.

**Test** Duplicate‑detection matrix (exact name+DOB, phonetic name variant, same phone different name, same name different sex). Verify partial‑failure behaviour.

---

### REC‑003 — Select and record payer type and price list for the visit

**Epic** REC · **P0** · **Primary** RECEPTIONIST · **Secondary** CASHIER

**User story** As a receptionist, I want the visit's payer type recorded at check‑in so every charge raised later in the day uses the right price and the cashier knows how payment will be collected.

**Business value** Prevents end‑of‑day reconciliation disputes and the common failure where a MoMo payment is recorded as cash.

**Pre** Facility has at least one active price list. Visit is being created or is `OPEN` and unbilled.

**Trig** Payer selection during REC‑001, or **Change payer** on an open visit before any payment exists.

**Flow** Receptionist picks `CASH` or `SELF_PAY_MOMO`; system binds `visit.payer_type` and `visit.price_list_id`. All subsequent charge capture reads the bound price list, not the live default, so mid‑day price changes do not retroactively alter open visits.

**Alt**

- **A1 Payer changed after charges exist but before payment** → system recalculates all `DRAFT` invoice lines against the new price list, shows a before/after diff, requires confirmation, and audits the delta.
- **A2 Payer change attempted after a payment is recorded** → blocked; requires a supervisor‑approved invoice adjustment (BIL‑010).

**AC**

- GIVEN a visit created with payer `CASH` and price list "Standard 2026", WHEN the facility admin publishes a new price list at 14:00, THEN charges added to that visit at 15:00 still use "Standard 2026".
- GIVEN a visit with a `DRAFT` invoice totalling 20,000, WHEN the payer type is changed and the new price list prices consultation at 25,000, THEN the UI shows the diff (+5,000), and on confirmation the invoice total becomes 25,000 and an audit event `INVOICE_REPRICED` records old and new totals.
- GIVEN a visit with any `Payment` in state `CONFIRMED`, WHEN a payer change is attempted, THEN the API returns 409 `PAYER_LOCKED`.

**Perm** `visit.update_payer` (RECEPTIONIST, CASHIER, FACILITY_ADMIN).

**Data** Update `visit.payer_type`, `visit.price_list_id`; possible rewrite of `invoice_line.unit_price` for `DRAFT` lines only.

**Audit** `VISIT_PAYER_SET`, `INVOICE_REPRICED`.

**Err** No active price list → 422 `NO_PRICE_LIST`, check‑in blocked.

**UI** Payer shown as a persistent chip in the visit header, visible to every downstream role.

**Dep** CAT‑002, TEN‑006, BIL‑002.

**OOS** Insurance, corporate accounts, split payer, discounts (BIL‑009 covers discounts).

**Test** Price‑list immutability test across a publish event.

---

### REC‑004 — Route the checked‑in patient to the correct first destination

**Epic** REC · **P0** · **Primary** RECEPTIONIST

**User story** As a receptionist, I want visit type to drive the first queue automatically so that a lab‑only or pharmacy‑only walk‑in is not forced through triage and a consultation.

**Business value** A patient collecting results or buying prescribed medicines should not consume a clinician slot or be charged a consultation fee.

**Pre** TEN‑005 routing rules configured.

**Trig** Visit type selection in REC‑001.

**Flow** System resolves destination: `OUTPATIENT_*` → TRIAGE queue; `ANC` → ANC/midwife queue (skips general triage, ANC has its own vitals set); `LAB_ONLY` → LAB queue and no consultation charge; `PHARMACY_ONLY` → PHARMACY queue and no consultation charge; `FOLLOW_UP_RESULTS` → CLINICIAN queue directly, with the flag `results_review=true`.

**Alt**

- **A1 Receptionist overrides the default destination** → allowed, reason optional, audited.
- **A2 `FOLLOW_UP_RESULTS` chosen but the patient has no released results** → warning "No released results found for this patient"; override permitted.

**AC**

- GIVEN visit type `LAB_ONLY`, WHEN check‑in is confirmed, THEN the queue entry `queue_type=LAB`, AND no consultation invoice line is created, AND the visit does not appear on the triage list.
- GIVEN visit type `FOLLOW_UP_RESULTS` and the patient has a lab order in state `RESULT_RELEASED`, WHEN check‑in is confirmed, THEN the clinician queue entry displays the badge "Results ready" and the released result count.
- GIVEN visit type `ANC`, WHEN check‑in is confirmed, THEN the entry lands on the ANC queue and the general triage queue count is unchanged.
- GIVEN the receptionist overrides destination from TRIAGE to CLINICIAN, WHEN confirmed, THEN audit event `ROUTING_OVERRIDDEN` records default and chosen destinations.

**Perm** `visit.create`; override requires the same permission (no separate gate in V1).

**Data** `queue_entry.queue_type`, `queue_entry.department_id`, `visit.results_review_flag`.

**Audit** `ROUTING_OVERRIDDEN` when non‑default.

**Err** No department of the required type configured → 422 with a link to facility setup (admin only sees the link).

**UI** Destination shown as a preview line: "This patient will go to: Triage — Room 2" before confirmation.

**Dep** TEN‑005, QUE‑001, LAB‑014.

**OOS** Skill‑based or load‑balanced routing to a named clinician, appointment‑driven routing.

**Test** One case per visit type verifying queue type, charge creation, and list membership.

---

### REC‑005 — Block or warn on duplicate open visit

**Epic** REC · **P0** · **Primary** RECEPTIONIST

**User story** As a receptionist, I want the system to stop me creating a second visit for a patient who is already in the building, so the queue and the day's attendance count stay accurate.

**Business value** Duplicate visits inflate HMIS attendance, split the clinical record across two encounters, and create two invoices for one episode.

**Pre** Patient has a `Visit` in state `OPEN` or `IN_PROGRESS` at this facility.

**Trig** Check‑in attempt.

**Flow** System detects the open visit and presents it with current state, current queue/location, assigned clinician if any, and actions: **Open existing visit**, **Reprint slip**, **Close previous visit as abandoned** (permission‑gated).

**Alt**

- **A1 The open visit is from a previous calendar day** (staff forgot to close) → offer auto‑close as `ABANDONED` with reason, then permit the new check‑in.
- **A2 The patient legitimately needs a second episode the same day** (e.g. returned after an accident) → supervisor‑approved second visit with mandatory reason; both visits linked via `related_visit_id`.

**AC**

- GIVEN an `OPEN` visit created today, WHEN check‑in is attempted, THEN 409 `VISIT_ALREADY_OPEN` and the response includes `visit_id`, `visit_state`, `current_queue`, `assigned_clinician`.
- GIVEN an `OPEN` visit created 3 days ago, WHEN check‑in is attempted and the receptionist selects "close as abandoned", THEN the old visit moves to `CLOSED_ABANDONED` with `closed_reason`, its queue entry moves to `REMOVED`, its `DRAFT` invoice is `VOIDED`, and the new visit is created.
- GIVEN an old visit with a `PAID` invoice, WHEN auto‑close is attempted, THEN the close proceeds but the invoice is untouched and the visit closes as `CLOSED_INCOMPLETE`.
- GIVEN a supervisor override for a same‑day second visit, WHEN created, THEN both visits carry `related_visit_id` pointing at each other and `SECOND_VISIT_OVERRIDE` is audited with the reason.

**Perm** `visit.create`; abandonment close requires `visit.close_abandoned` (FACILITY_ADMIN, SUPERVISOR, RECEPTIONIST‑with‑grant); same‑day duplicate requires `visit.override_duplicate` (SUPERVISOR, FACILITY_ADMIN).

**Data** Update prior `visit.state`, `closed_reason`, `closed_by`; void draft invoice; insert new visit.

**Audit** `VISIT_ABANDONED`, `SECOND_VISIT_OVERRIDE`, `INVOICE_VOIDED`.

**Err** Attempting to abandon a visit with a signed encounter → 409; must use the normal close path (ENC‑018).

**UI** The conflict panel is informative, not a dead end — every branch has a button. Never show a bare error toast here.

**Dep** REC‑001, BIL‑011, QUE‑008.

**OOS** Cross‑facility duplicate detection within the same organisation (BRN‑004 covers visibility only).

**Test** Matrix of prior‑visit states × invoice states.

---

### REC‑006 — Reprint the visit slip / queue token

**Epic** REC · **P1** · **Primary** RECEPTIONIST

**User story** As a receptionist, I want to reprint a visit slip when the patient loses it, so they can be identified at triage and the pharmacy window.

**Pre** Visit exists and is not `CLOSED` older than 24 h.

**Trig** **Reprint slip** on the visit or attendance list.

**Flow** System regenerates the slip PDF with the identical visit number and queue token, marks it `REPRINT #n`, and sends it to the browser print dialog.

**AC**

- GIVEN a visit slip printed once, WHEN reprinted, THEN the document body is identical except a visible "REPRINT (2)" marker, AND `DOCUMENT_REPRINTED` is audited with the count.
- GIVEN a closed visit older than 24 h, WHEN reprint is attempted, THEN 422 `REPRINT_WINDOW_EXPIRED`.

**Perm** `visit.print_slip`.
**Data** Increment `visit.slip_print_count`. **Audit** `DOCUMENT_REPRINTED`.
**Err** Missing facility print header → 422 pointing to TEN‑003.
**UI** A5 layout, works on 58 mm thermal and A4; facility name, phone, visit number, queue token, date/time, patient name and number. No diagnosis, no clinical data on the slip.
**Dep** TEN‑003, RCP‑001. **OOS** Barcode/QR scanning (P2), SMS of the token.
**Test** Render test for both paper sizes; assert no PHI beyond name and number.

---

### REC‑007 — View and filter today's attendance list

**Epic** REC · **P0** · **Primary** RECEPTIONIST · **Secondary** FACILITY_ADMIN, SUPERVISOR

**User story** As a receptionist, I want a live list of everyone checked in today with their current stage, so I can answer "where is my patient / how long more" without walking the corridor.

**Business value** The desk is the information hub; without this, staff interrupt clinicians to locate patients.

**Pre** Authenticated at a facility.

**Trig** Opening **Today** from the main navigation; auto‑refresh every 20 s.

**Flow** List shows: queue token, patient name + number, age/sex, visit type, current stage (`Waiting triage`, `In triage`, `Waiting clinician`, `With clinician`, `Awaiting lab`, `Awaiting payment`, `At pharmacy`, `Ready to leave`, `Closed`), waiting time in the current stage, assigned staff, payment status chip, and actions.

**Alt**

- **A1 Filter** by stage, visit type, payer, or overdue (> 45 min in one stage).
- **A2 Search** within today's list by name or token.

**AC**

- GIVEN 12 patients checked in today across 5 stages, WHEN the attendance list loads, THEN all 12 appear with correct stage labels derived from live queue‑entry and encounter states, sorted by check‑in time ascending by default.
- GIVEN a patient whose queue entry moves from `WAITING` to `IN_SERVICE`, WHEN the list auto‑refreshes, THEN the stage label changes within one refresh cycle without a full page reload.
- GIVEN the "overdue" filter, WHEN applied, THEN only entries whose `current_stage_since` is older than the facility's configured threshold are shown, and each row displays elapsed minutes.
- GIVEN a receptionist (no clinical permission), WHEN viewing the list, THEN no diagnosis, complaint, vitals or medication data is present in the API response payload, verified at the contract level.
- GIVEN facility B's session, WHEN the list loads, THEN zero facility A visits appear.

**Perm** `visit.read_list`. Clinical columns are permission‑filtered server‑side, not hidden in CSS.

**Data** Read‑only. **Audit** No `PHI_READ` for the list itself (name + number only); opening an individual chart does audit.

**Err** Refresh failure shows a stale‑data banner with last‑updated time rather than blanking the list.

**UI** Dense table, colour‑coded waiting time (green < 20 min, amber 20–45, red > 45). Works on a 13" laptop at 100% zoom without horizontal scroll. Count badges per stage across the top.

**Dep** QUE‑002, ENC‑002. **OOS** Historical attendance analytics (REP‑002), cross‑branch view (BRN‑004).

**Test** Contract test asserting absence of clinical fields for a receptionist token. Load test with 300 same‑day visits.

---

### REC‑008 — Record referral‑in source

**Epic** REC · **P2** · **Primary** RECEPTIONIST

**User story** As a receptionist, I want to record where a patient was referred from, so the owner can see which referral sources drive attendance.

**Pre** Visit being created.
**Trig** Optional field in the check‑in panel.
**Flow** Select source type (`SELF`, `REFERRED_FACILITY`, `REFERRED_PERSON`, `CAMP_OUTREACH`, `WALK_BY`) and optional free‑text name.

**AC**

- GIVEN source `REFERRED_FACILITY` with name "Kisenyi HC IV", WHEN saved, THEN `visit.referral_source_type` and `visit.referral_source_name` persist and appear in REP‑006.
- GIVEN no selection, WHEN check‑in is confirmed, THEN the field defaults to `SELF` and check‑in is not blocked.

**Perm** `visit.create`. **Data** Two visit columns. **Audit** Included in `VISIT_OPENED` payload.
**Err** Free text > 100 chars → truncation warning, not an error.
**UI** Collapsed "More details" section so it never slows the common path.
**Dep** REC‑001, REP‑006. **OOS** Referral letter attachment, referral‑out (not in V1).
**Test** Default‑value test.

---

### REC‑009 — Mark a patient as "left without being seen"

**Epic** REC · **P1** · **Primary** RECEPTIONIST · **Secondary** NURSE, SUPERVISOR

**User story** As a receptionist, I want to remove a patient who left before being seen, so the queue reflects reality and the clinician is not called to an empty room.

**Business value** LWBS rate is a real quality metric and a queue hygiene requirement.

**Pre** Queue entry in `WAITING` or `CALLED`. No signed encounter for the visit.

**Trig** **Mark as left** on the queue or attendance row.

**Flow** Confirm dialog requiring a reason (`LEFT_WITHOUT_BEING_SEEN`, `WENT_ELSEWHERE`, `COST`, `WAIT_TOO_LONG`, `OTHER` + text). System sets queue entry `REMOVED`, visit `CLOSED_LWBS`, and voids any `DRAFT` invoice.

**Alt**

- **A1 The patient has already paid** → invoice is not voided; visit closes as `CLOSED_LWBS_PAID` and a refund task is flagged for the cashier (PAY‑008).
- **A2 The patient returns later the same day** → REC‑005 A2 path creates a linked new visit; the LWBS visit is not reopened.

**AC**

- GIVEN a `WAITING` entry with a `DRAFT` invoice, WHEN marked LWBS with reason `WAIT_TOO_LONG`, THEN queue entry = `REMOVED`, visit = `CLOSED_LWBS`, invoice = `VOIDED`, and three audit events are written.
- GIVEN a `WAITING` entry whose invoice is `PAID`, WHEN marked LWBS, THEN the invoice remains `PAID`, visit = `CLOSED_LWBS_PAID`, and a `RefundRequest` in state `PENDING` is created and visible to the cashier.
- GIVEN a visit with a `SIGNED` encounter, WHEN LWBS is attempted, THEN 409 `ENCOUNTER_EXISTS`.
- GIVEN LWBS is recorded, WHEN REP‑002 is run for the day, THEN the visit is counted in "left without being seen", not in "attended".

**Perm** `queue.remove_entry` (RECEPTIONIST, NURSE, SUPERVISOR, FACILITY_ADMIN).
**Data** `queue_entry.state`, `visit.state`, `visit.closed_reason`, invoice void, optional refund request.
**Audit** `QUEUE_ENTRY_REMOVED`, `VISIT_CLOSED_LWBS`, conditional `REFUND_REQUESTED`.
**Err** Entry already `IN_SERVICE` → 409, ask the clinician to close the encounter instead.
**UI** Reason is mandatory and selected from a list; free text only for `OTHER`.
**Dep** QUE‑008, BIL‑011, PAY‑008, REP‑002.
**Test** Both invoice branches; report attribution.

---

### REC‑010 — Undo an erroneous check‑in within a grace window

**Epic** REC · **P1** · **Primary** RECEPTIONIST

**User story** As a receptionist, I want to cancel a check‑in I created by mistake (wrong patient) within a short window, so I don't leave a phantom visit and a phantom charge.

**Pre** Visit `OPEN`, created < 15 minutes ago, no vitals, no encounter, no payment.

**Trig** **Cancel check‑in** button, visible only inside the grace window.

**Flow** Confirm with reason → visit `CANCELLED_ERROR`, queue entry `REMOVED`, draft invoice `VOIDED`, visit number is _not_ reused.

**AC**

- GIVEN a visit created 4 minutes ago with no downstream records, WHEN cancelled with reason "wrong patient selected", THEN visit = `CANCELLED_ERROR`, queue entry = `REMOVED`, invoice = `VOIDED`, and the visit remains queryable in audit but is excluded from attendance reports.
- GIVEN a visit created 20 minutes ago, WHEN cancel is attempted, THEN 422 `GRACE_WINDOW_EXPIRED` and the user is directed to REC‑009 instead.
- GIVEN a visit with a triage record, WHEN cancel is attempted, THEN 409 `CLINICAL_DATA_EXISTS` regardless of elapsed time.
- GIVEN a cancelled visit, WHEN the next check‑in occurs, THEN the new visit number is the next in sequence — cancelled numbers are never recycled.

**Perm** `visit.cancel_error`.
**Data** State changes only; nothing hard‑deleted.
**Audit** `VISIT_CANCELLED_ERROR` with reason and elapsed seconds.
**Err** Any downstream record → 409 naming the blocking record type.
**UI** Countdown chip showing remaining grace minutes.
**Dep** REC‑001, TRI‑003. **OOS** Hard delete, number recycling.
**Test** Boundary tests at 14:59 and 15:01 minutes; blocking‑record matrix.

---

### REC‑011 — Resume an in‑progress visit from the desk

**Epic** REC · **P1** · **Primary** RECEPTIONIST

**User story** As a receptionist, I want to reopen a patient's active visit to add or correct administrative details, so I don't create a duplicate to fix a typo.

**Pre** Visit `OPEN` or `IN_PROGRESS`.
**Trig** Clicking the patient on the attendance list.
**Flow** Visit workspace (administrative view) shows visit header, payer, destination, invoice summary, queue history, and edit actions for payer (REC‑003), routing (REC‑004), and referral source (REC‑008). Clinical sections are visible only as locked summaries ("Triage completed 09:14 by S. Nabirye") with no values.

**AC**

- GIVEN a receptionist opens an in‑progress visit, WHEN the workspace loads, THEN vitals values, complaint text, diagnoses and medicines are absent from the API payload, and only completion timestamps and staff names are returned.
- GIVEN the same visit opened by a clinician, WHEN the workspace loads, THEN clinical values are present.
- GIVEN a receptionist edits the payer type, WHEN saved, THEN REC‑003 rules apply including the payment lock.

**Perm** `visit.read`, `visit.update_admin`. Clinical read requires `encounter.read`.
**Audit** `PHI_READ` is written only when clinical values are actually returned.
**UI** Locked clinical sections show a padlock and the reason ("Requires clinical role"), which prevents staff assuming the system is broken.
**Dep** REC‑001, ENC‑002. **OOS** Clinical editing by non‑clinical roles (never permitted).
**Test** Two‑role payload diff test.

---

### REC‑012 — Close the visit at the exit desk

**Epic** REC · **P0** · **Primary** RECEPTIONIST · **Secondary** CASHIER, CLINICIAN

**User story** As a receptionist, I want to close a visit when the patient leaves, so the day's queue empties and the visit can be counted, invoiced and reported.

**Business value** Open visits are the main source of dirty data in small clinics; closing must be easy and safe.

**Pre** Visit `IN_PROGRESS`. All encounters are `SIGNED`, `CANCELLED` or explicitly abandoned.

**Trig** **Close visit**, or automatic prompt when the last queue entry completes.

**Flow**

1. System runs a close checklist: encounters signed? invoice issued? invoice settled or explicitly marked unpaid‑debt? prescriptions dispensed or explicitly cancelled? lab orders resulted, cancelled or explicitly deferred?
2. Blocking items are listed with links; non‑blocking items are warnings requiring acknowledgment.
3. On confirmation, visit → `CLOSED_COMPLETED`, `closed_at`, `closed_by` recorded.

**Alt**

- **A1 Outstanding lab result** → visit may close as `CLOSED_PENDING_RESULTS`; the lab order stays live and the patient returns under visit type `FOLLOW_UP_RESULTS`.
- **A2 Unpaid balance** → close requires `visit.close_with_debt` (SUPERVISOR/FACILITY_ADMIN) and records the debt amount.
- **A3 Unsigned encounter** → hard block; only the authoring clinician can sign (ENC‑015).

**AC**

- GIVEN a visit with one `SIGNED` encounter, a `PAID` invoice and a fully dispensed prescription, WHEN close is confirmed, THEN visit = `CLOSED_COMPLETED` and it disappears from all active queues and the attendance "in building" count.
- GIVEN a visit with an `OPEN` encounter, WHEN close is attempted, THEN 409 `UNSIGNED_ENCOUNTER` naming the encounter ID and the responsible clinician.
- GIVEN a visit with a lab order in state `IN_PROGRESS`, WHEN the receptionist selects "patient will return for results", THEN visit = `CLOSED_PENDING_RESULTS`, the lab order remains actionable by the lab, and the released result later appears on the patient's chart linked to the original encounter.
- GIVEN an invoice with balance 15,000 and a receptionist without `visit.close_with_debt`, WHEN close is attempted, THEN 403 with the required permission named and a "request supervisor" action.
- GIVEN a closed visit, WHEN any role attempts to add a charge to it, THEN 409 `VISIT_CLOSED`.

**Perm** `visit.close`; debt path `visit.close_with_debt`.
**Data** `visit.state`, `closed_at`, `closed_by`, `closed_reason`, `debt_amount`.
**Audit** `VISIT_CLOSED` with the checklist snapshot embedded in `after_json` — this snapshot is what a supervisor reviews later.
**Err** Concurrent close by two users → second gets 409 with current state, not an error page.
**UI** Checklist with green ticks and red blockers; the close button remains disabled while any blocker exists, with each blocker clickable.
**Dep** ENC‑015, BIL‑006, PAY‑003, DSP‑006, LAB‑010.
**OOS** Automatic nightly auto‑close (OPS‑004 covers the sweeper for stale visits), discharge summaries.
**Test** Full matrix of blocking conditions; verify `CLOSED_PENDING_RESULTS` keeps the lab loop alive.

---

# EPIC QUE — Queue Management

Purpose: a queue entry is the patient's position in one stage. A visit generates several sequential queue entries (triage → clinician → lab → cashier → pharmacy). Queue entries are cheap, auditable, and never deleted.

---

### QUE‑001 — Create a queue entry when a stage begins

**Epic** QUE · **P0** · **Primary** SYSTEM · **Secondary** RECEPTIONIST, CLINICIAN, NURSE

**User story** As the system, I want to create a queue entry whenever a patient is routed to a new stage, so every wait is measurable and every stage has an explicit worklist.

**Pre** Visit `OPEN`/`IN_PROGRESS`; target queue exists and is enabled.

**Trig** Check‑in (REC‑001), triage completion (TRI‑006), clinician send‑to‑lab (LAB‑003), clinician send‑to‑pharmacy (RX‑007), charge requiring payment (BIL‑005).

**Flow** Insert `queue_entry(visit_id, queue_type, department_id, state=WAITING, priority, entered_at, source_stage, token)`. Priority inherits triage acuity if triage has occurred, otherwise `STANDARD`.

**AC**

- GIVEN triage completes with acuity `EMERGENCY`, WHEN the clinician queue entry is created, THEN `priority=EMERGENCY` and the entry sorts above all `PRIORITY` and `STANDARD` entries regardless of arrival time.
- GIVEN a patient already has an active entry on the same queue, WHEN a second creation is attempted, THEN no duplicate is created and the existing entry is returned (idempotent by `visit_id + queue_type + active`).
- GIVEN an entry is created, WHEN it is read, THEN `entered_at` is server time, never client time.

**Perm** Internal service call; no direct public create endpoint except reception check‑in.
**Data** Insert `queue_entry`. **Audit** `QUEUE_ENTRY_CREATED` with source stage.
**Err** Disabled target queue → 422 and the calling action is rolled back so a clinician never thinks a patient was sent when they were not.
**UI** None (system).
**Dep** REC‑001, TRI‑006. **OOS** Multi‑queue simultaneous membership.
**Test** Idempotency and priority‑inheritance tests.

---

### QUE‑002 — View my stage's queue

**Epic** QUE · **P0** · **Primary** NURSE, CLINICIAN, LAB_TECH, CASHIER, PHARMACIST

**User story** As a staff member at any stage, I want to see only the patients waiting for my stage, ordered correctly, so I know who to serve next.

**Business value** Shared, role‑scoped worklists are what replace paper cards and shouting names down a corridor.

**Pre** User has a role mapped to at least one queue type.

**Trig** Opening the role home screen; refresh every 15 s.

**Flow** List sorted by priority DESC, then `entered_at` ASC. Each row: token, patient name, age/sex, wait time, priority chip, brief context (triage acuity for the clinician queue; test names for the lab queue; amount due for the cashier queue; item count for the pharmacy queue), and the primary action button.

**Alt**

- **A1 Multi‑role user** → queue switcher tabs with unread counts.
- **A2 Empty queue** → explicit empty state with the count of patients at earlier stages, so staff know work is coming.

**AC**

- GIVEN three waiting entries — Emergency arrived 10:00, Standard arrived 09:00, Priority arrived 09:30 — WHEN the clinician queue loads, THEN the order is Emergency, Priority, Standard.
- GIVEN a lab tech's session, WHEN the queue loads, THEN each row shows requested test names but no diagnosis and no clinical notes, verified in the API payload.
- GIVEN a cashier's session, WHEN the queue loads, THEN each row shows the amount due and invoice number but no test names, diagnosis or medicines.
- GIVEN an entry is taken into service by another user, WHEN my list refreshes, THEN the row shows "In service — Dr. Okello" and its action button is disabled.
- GIVEN facility A's queue, WHEN a facility B user requests it, THEN 404.

**Perm** `queue.read:<queue_type>` per role. Field‑level payload filtering is server‑side.
**Data** Read‑only. **Audit** No per‑row PHI_READ; opening a patient does audit.
**Err** Refresh failure → stale banner with timestamp; the last good list stays visible so work can continue.
**UI** One screen, no nested navigation to start work. Large touch targets — clinicians often use tablets. Wait time in minutes, colour‑coded. Row count and longest wait in the header.
**Dep** QUE‑001, TRI‑006. **OOS** Cross‑department "all queues" view (SUPERVISOR gets this in QUE‑010), drag‑and‑drop reordering.
**Test** Per‑role payload snapshot tests; ordering test; concurrency display test.

---

### QUE‑003 — Call the next patient

**Epic** QUE · **P0** · **Primary** CLINICIAN, NURSE, LAB_TECH, CASHIER, PHARMACIST

**User story** As a staff member, I want to call the next patient with one action so the entry is locked to me and no colleague calls the same person.

**Pre** At least one `WAITING` entry on my queue.

**Trig** **Call next** button, or clicking a specific row's **Call**.

**Flow** System selects the top entry by the QUE‑002 ordering, transitions `WAITING → CALLED`, sets `called_by`, `called_at`, and displays the patient with their stage context. A soft lock on the entry expires after the configured no‑show timeout.

**Alt**

- **A1 Staff calls a specific patient out of order** → allowed with `queue.call_out_of_order`; reason optional; audited with the skipped count.
- **A2 Two staff press "Call next" simultaneously** → optimistic locking; the loser receives the next entry, not an error.
- **A3 No‑show** → QUE‑004.

**AC**

- GIVEN two clinicians press "Call next" within the same second on a queue with two waiting patients, WHEN both requests resolve, THEN each clinician receives a different patient and no entry has two `called_by` values.
- GIVEN an entry is `CALLED` by user X, WHEN user Y attempts to start service on it, THEN 409 `ENTRY_LOCKED` naming user X, with an option to request takeover (QUE‑007).
- GIVEN a call out of order skipping 3 higher entries, WHEN performed, THEN `QUEUE_CALLED_OUT_OF_ORDER` is audited with `skipped_count=3`.
- GIVEN an entry is called, WHEN 10 minutes (configurable) elapse without service start, THEN the entry returns to `WAITING` with `no_show_count += 1` and reappears on the queue.

**Perm** `queue.call:<queue_type>`; out‑of‑order needs `queue.call_out_of_order`.
**Data** `queue_entry.state`, `called_by`, `called_at`, `no_show_count`.
**Audit** `QUEUE_CALLED`, conditional `QUEUE_CALLED_OUT_OF_ORDER`, `QUEUE_CALL_EXPIRED`.
**Err** Empty queue → 200 with `null`, not an error.
**UI** After calling, the patient's name and token are large on screen for verbal call‑out. A single primary button "Start" moves to service.
**Dep** QUE‑002, QUE‑004. **OOS** Audio announcement, display‑board integration (P2, BRN‑006 stub).
**Test** Race test with 5 concurrent callers; timeout expiry test.

---

### QUE‑004 — Handle a no‑show

**Epic** QUE · **P1** · **Primary** all serving roles

**User story** As a clinician, I want to mark a called patient absent so the queue advances instead of stalling on someone who stepped outside.

**Pre** Entry in `CALLED`.
**Trig** **No show** button, or automatic timeout.
**Flow** First no‑show: entry returns to `WAITING` at the _back_ of its priority band with `no_show_count=1`. Second no‑show: entry state `NO_SHOW`, visit flagged for reception follow‑up. Third strike is not needed in V1.

**AC**

- GIVEN a `CALLED` entry with `no_show_count=0`, WHEN marked no‑show, THEN state = `WAITING`, `no_show_count=1`, and the entry sorts last within its priority band.
- GIVEN `no_show_count=1`, WHEN marked no‑show again, THEN state = `NO_SHOW` and the entry leaves the active queue and appears on reception's follow‑up list.
- GIVEN an `EMERGENCY` priority entry, WHEN marked no‑show, THEN it stays `EMERGENCY` and reception receives an immediate alert row — an emergency patient who disappears is a safety event.

**Perm** `queue.mark_no_show`. **Data** state + counter. **Audit** `QUEUE_NO_SHOW`.
**Err** Marking no‑show on a `WAITING` entry → 409.
**UI** Confirm dialog only for emergency‑priority entries.
**Dep** QUE‑003. **OOS** Automated recall notifications (no SMS in V1).
**Test** Band re‑sorting; emergency alert path.

---

### QUE‑005 — Start service (take the patient into a stage)

**Epic** QUE · **P0** · **Primary** all serving roles

**User story** As a staff member, I want to start service so the entry is marked in‑service, the wait clock stops, and the stage's working record is created or opened.

**Pre** Entry `CALLED` and locked to me.
**Trig** **Start**.
**Flow** `CALLED → IN_SERVICE`; `service_started_at` set; the stage record is created if absent — triage record (TRI‑002), encounter (ENC‑001), lab worklist item (LAB‑006), payment session (PAY‑002), dispense session (DSP‑002).

**AC**

- GIVEN a `CALLED` clinician‑queue entry with no existing encounter, WHEN service starts, THEN exactly one `Encounter` is created in state `OPEN` linked to the visit and to me as author, and the queue entry is `IN_SERVICE`.
- GIVEN the visit already has an `AWAITING_RESULTS` encounter authored by me, WHEN service starts from a results‑review queue entry, THEN **no new encounter is created**; the existing encounter is reopened to `OPEN` and its ID is unchanged. (This is the central design rule of V1.)
- GIVEN the existing open encounter was authored by a different clinician, WHEN I start service, THEN I am shown a choice: continue the colleague's encounter as co‑author (permission `encounter.coauthor`) or open a new encounter linked as a continuation; both paths are audited.
- GIVEN service starts, WHEN wait metrics are computed, THEN `wait_seconds = service_started_at − entered_at` and this value is frozen on the entry.

**Perm** `queue.start_service:<queue_type>` plus the stage's own create permission.
**Data** `queue_entry.state`, `service_started_at`, `wait_seconds`; stage record insert or reopen.
**Audit** `QUEUE_SERVICE_STARTED`, plus the stage's own creation/reopen event.
**Err** Entry locked to another user → 409. Stage record creation failure rolls the entry back to `CALLED` so the patient is not lost between states.
**UI** Immediate transition into the stage workspace — no intermediate confirmation screen.
**Dep** QUE‑003, ENC‑001, ENC‑011. **OOS** Time‑and‑motion analytics.
**Test** The encounter‑reuse case is a mandatory regression test for every release.

---

### QUE‑006 — Complete a stage and hand off

**Epic** QUE · **P0** · **Primary** all serving roles

**User story** As a staff member, I want to complete my stage and send the patient onward, so the next role sees them immediately with the right context.

**Pre** Entry `IN_SERVICE`; the stage's own completion rules satisfied.

**Trig** The stage's completion action (Complete triage, Sign encounter, Release result, Confirm payment, Complete dispense).

**Flow** Entry `IN_SERVICE → COMPLETED`, `completed_at` set, `service_seconds` computed; the next queue entry is created per the routing decision made in the stage (QUE‑001); the visit's `current_stage` is recomputed.

**Alt**

- **A1 Terminal stage** (patient leaves) → no next entry; visit close prompt (REC‑012).
- **A2 Multiple next stages** (e.g. lab _and_ pharmacy) → V1 rule: create the payment entry first if the facility gates on payment, then lab, then pharmacy, sequenced not parallel, to avoid the patient being on two queues at once.

**AC**

- GIVEN a triage entry `IN_SERVICE` with all mandatory vitals recorded, WHEN triage is completed, THEN triage entry = `COMPLETED`, a clinician queue entry = `WAITING` exists with priority equal to the recorded acuity, and the visit `current_stage = Waiting clinician`.
- GIVEN a clinician orders two lab tests and one prescription and completes the stage with facility policy `PAY_BEFORE_SERVICE`, WHEN completion occurs, THEN exactly one next entry is created on the CASHIER queue, and the LAB entry is created only after payment confirmation.
- GIVEN mandatory stage data is missing, WHEN completion is attempted, THEN 422 listing every missing field, and the entry remains `IN_SERVICE`.
- GIVEN completion succeeds, WHEN the next role's queue is queried, THEN the patient appears within one refresh cycle with the correct context fields populated.

**Perm** `queue.complete:<queue_type>` plus the stage completion permission.
**Data** Entry update + next entry insert (single transaction).
**Audit** `QUEUE_SERVICE_COMPLETED`, `QUEUE_HANDOFF` with `from_stage`, `to_stage`, `reason`.
**Err** Partial failure must not leave the patient with a completed stage and no next stage; the transaction is atomic, and OPS‑003 reconciliation detects any orphan.
**UI** The completion dialog states in plain words where the patient goes next: "Send to Cashier — 2 patients ahead."
**Dep** QUE‑001, QUE‑005, all stage epics. **OOS** Parallel queue membership.
**Test** Atomicity test with an injected failure on next‑entry creation.

---

### QUE‑007 — Take over an entry locked by another user

**Epic** QUE · **P1** · **Primary** SUPERVISOR, FACILITY_ADMIN · **Secondary** CLINICIAN

**User story** As a supervisor, I want to release a queue entry that a colleague locked and then went off shift, so the patient is not stuck.

**Pre** Entry `CALLED` or `IN_SERVICE`, inactive for longer than the configured threshold (default 30 min).

**Trig** **Release / take over** on the entry.

**Flow** Confirm with reason → lock is released; if `IN_SERVICE` with an open stage record, the record is left intact and the new user becomes co‑author or the record is reassigned per stage rules (an encounter is never silently reassigned; see ENC‑017).

**AC**

- GIVEN an entry `IN_SERVICE` idle for 45 min, WHEN a supervisor takes over with reason, THEN the entry's `assigned_user` changes, `QUEUE_TAKEOVER` is audited with both user IDs and the reason, and the original open encounter remains authored by the original clinician.
- GIVEN an entry idle for 5 min, WHEN takeover is attempted, THEN 422 `TAKEOVER_TOO_EARLY` with remaining minutes.
- GIVEN a takeover of an entry with an open encounter, WHEN the new clinician writes notes, THEN the encounter records both a primary author and a co‑author, and each note line carries its own author ID.

**Perm** `queue.takeover` (SUPERVISOR, FACILITY_ADMIN).
**Audit** `QUEUE_TAKEOVER`. **Err** Original user active in the last 5 min → blocked.
**UI** Clear warning naming the current holder and their last activity time.
**Dep** QUE‑005, ENC‑017. **OOS** Automatic takeover without human decision.
**Test** Idle‑threshold boundary; authorship preservation.

---

### QUE‑008 — Remove an entry from a queue

**Epic** QUE · **P0** · **Primary** RECEPTIONIST, SUPERVISOR

**User story** As a receptionist, I want to remove a queue entry that should not be there, so the worklist is trustworthy.

**Pre** Entry active (`WAITING`, `CALLED`, `NO_SHOW`).
**Trig** **Remove from queue**, mandatory reason.
**Flow** `→ REMOVED` with reason (`LWBS`, `SENT_ELSEWHERE`, `DUPLICATE_ENTRY`, `ROUTED_IN_ERROR`, `OTHER`). Entry rows are never deleted.

**AC**

- GIVEN a `WAITING` entry removed with reason `ROUTED_IN_ERROR`, WHEN the queue reloads, THEN the entry is absent from the active list but retrievable via the visit's queue history with its reason and remover.
- GIVEN an `IN_SERVICE` entry, WHEN removal is attempted, THEN 409 — complete or cancel the stage first.
- GIVEN removal, WHEN wait‑time reports run, THEN the entry is excluded from service‑time averages but counted in a "removed" tally.

**Perm** `queue.remove_entry`. **Audit** `QUEUE_ENTRY_REMOVED` with reason.
**UI** Queue history is always visible on the visit workspace — a small timeline showing every stage, timestamp and actor.
**Dep** QUE‑001. **OOS** Hard delete.
**Test** History retrieval; report exclusion.

---

### QUE‑009 — Change a waiting patient's priority

**Epic** QUE · **P0** · **Primary** NURSE, CLINICIAN · **Secondary** SUPERVISOR

**User story** As a triage nurse, I want to escalate a waiting patient whose condition has deteriorated, so they are seen before others.

**Pre** Entry `WAITING` or `CALLED`.
**Trig** **Change priority** with mandatory reason.
**Flow** Priority updated; list re‑sorts; escalation to `EMERGENCY` raises a visible alert on the clinician queue.

**AC**

- GIVEN a `STANDARD` entry escalated to `EMERGENCY` with reason "SpO2 88% on recheck", WHEN the clinician queue refreshes, THEN the entry is first in the list and displays a red escalation banner with the reason and the escalating nurse's name.
- GIVEN a de‑escalation from `PRIORITY` to `STANDARD`, WHEN performed by a nurse, THEN it is permitted only with `queue.deescalate` (CLINICIAN, SUPERVISOR) — nurses may escalate but not de‑escalate.
- GIVEN any priority change, WHEN audited, THEN old value, new value, reason and actor are recorded.

**Perm** `queue.escalate` (NURSE, CLINICIAN, SUPERVISOR); `queue.deescalate` (CLINICIAN, SUPERVISOR).
**Data** `queue_entry.priority`, `priority_changed_at`, `priority_reason`.
**Audit** `QUEUE_PRIORITY_CHANGED`.
**Err** Change on a `COMPLETED` entry → 409.
**UI** Reason is free text with three quick‑pick suggestions; the reason is displayed to the receiving clinician, not buried in audit.
**Dep** TRI‑005, QUE‑002. **OOS** Automated deterioration scoring (that would be clinical decision support — explicitly out of V1 scope).
**Test** Permission asymmetry test between escalate and de‑escalate.

---

### QUE‑010 — Supervisor view of all queues

**Epic** QUE · **P1** · **Primary** SUPERVISOR, FACILITY_ADMIN, ORG_OWNER

**User story** As a supervisor, I want a single board showing every queue's depth and longest wait, so I can move staff to the bottleneck.

**Pre** Supervisory role at the facility.
**Trig** Opening **Flow board**; refresh 30 s.
**Flow** Card per stage: waiting count, in‑service count, longest wait, median wait today, staff currently serving. Clicking a card opens that queue read‑only.

**AC**

- GIVEN 4 waiting at triage (longest 38 min) and 9 waiting for clinicians (longest 71 min), WHEN the board loads, THEN both cards show the correct counts and longest waits, and the clinician card is flagged red per the configured threshold.
- GIVEN a supervisor without clinical permissions, WHEN they open a queue from the board, THEN the payload contains no clinical values, only counts, names and timings.
- GIVEN an organisation owner with two facilities, WHEN the board loads, THEN only the currently selected facility's data is shown (cross‑branch roll‑up is BRN‑004).

**Perm** `queue.read_board`. **Audit** None (aggregate, no PHI).
**UI** Deliberately simple: 5–7 cards, no charts. It must be readable from 2 m on a wall‑mounted screen.
**Dep** QUE‑002. **OOS** Predictive wait times, staffing recommendations.
**Test** Aggregate correctness against seeded data; payload PHI absence.

---

### QUE‑011 — Queue history on the visit record

**Epic** QUE · **P1** · **Primary** all roles with `visit.read`

**User story** As any staff member, I want to see the full stage timeline of a visit, so I can explain to a patient or a supervisor exactly where time was spent.

**Pre** Visit exists.
**Trig** Opening the visit workspace timeline.
**Flow** Chronological list of every queue entry with stage, entered/called/started/completed timestamps, actor names, waits, and any removal or escalation reason.

**AC**

- GIVEN a visit that passed through triage, clinician, cashier, lab, clinician (resumed) and pharmacy, WHEN the timeline loads, THEN six entries appear in chronological order with the second clinician entry labelled "Resumed — results review" and linked to the same encounter ID as the first.
- GIVEN a removed entry, WHEN the timeline loads, THEN it appears greyed with its removal reason and actor.
- GIVEN total visit duration, WHEN displayed, THEN it equals `last_completed_at − visit.opened_at` and the sum of waits plus services plus untracked gaps is reconcilable.

**Perm** `visit.read`. **Audit** None beyond standard.
**UI** Vertical timeline; each node collapsible. Waits shown in minutes.
**Dep** QUE‑001–008. **OOS** Export of the timeline (REP‑008 covers exports).
**Test** Reconciliation arithmetic test.

---

### QUE‑012 — Daily queue reset and stale‑entry sweep

**Epic** QUE · **P1** · **Primary** SYSTEM · **Secondary** FACILITY_ADMIN

**User story** As a facility admin, I want yesterday's abandoned queue entries cleared automatically, so today's board is not polluted by stale rows.

**Pre** Scheduled job enabled; facility timezone Africa/Kampala.
**Trig** Nightly at the facility's configured cut‑off (default 23:59) plus an on‑demand admin action.
**Flow** Entries still `WAITING`/`CALLED`/`NO_SHOW` from previous days → `EXPIRED` with reason `DAY_ROLLOVER`. Their visits → `CLOSED_ABANDONED` unless they have a signed encounter (then `CLOSED_INCOMPLETE`) or a paid invoice (then flagged for supervisor review). `IN_SERVICE` entries are never auto‑expired; they are listed on an exceptions report instead.

**AC**

- GIVEN an entry `WAITING` since yesterday, WHEN the sweep runs, THEN it becomes `EXPIRED` and its visit becomes `CLOSED_ABANDONED`, both audited with actor `SYSTEM`.
- GIVEN an `IN_SERVICE` entry from yesterday, WHEN the sweep runs, THEN it is untouched and appears on the exceptions list shown to the facility admin at next login.
- GIVEN a visit with a paid invoice and a waiting entry, WHEN the sweep runs, THEN the visit is closed but flagged `REVIEW_REQUIRED` with the paid amount, so money is never silently written off.
- GIVEN the sweep runs twice, WHEN the second run executes, THEN no additional state changes occur (idempotent).

**Perm** System job; manual trigger requires `ops.run_sweep` (FACILITY_ADMIN).
**Audit** `QUEUE_SWEEP_RUN` summary event plus per‑entity events.
**Err** Job failure is retried with backoff and raises an ops alert after 3 failures; never partially applied without an audit record.
**UI** Exceptions list on the admin dashboard with a count badge.
**Dep** REC‑012, OPS‑004. **OOS** Configurable per‑department cut‑offs.
**Test** Idempotency; timezone correctness across the 00:00 boundary; the paid‑invoice guard.

---

# EPIC TRI — Triage

Purpose: capture the structured observation set that determines acuity and gives the clinician a head start. Triage is a nursing record, editable by nurses, readable by clinicians, and never overwritten silently.

---

### TRI‑001 — See the triage worklist with waiting context

**Epic** TRI · **P0** · **Primary** NURSE

**User story** As a triage nurse, I want a worklist of checked‑in patients awaiting triage with age and visit type visible, so I can pull an infant or an obviously unwell adult forward.

**Pre** Nurse role with `queue.read:TRIAGE`.
**Trig** Opening the triage home screen.
**Flow** QUE‑002 list filtered to `queue_type=TRIAGE`, with extra columns: age (in months if < 5 years), sex, visit type, wait time, and a flag if the patient is under 5 or pregnant (from the patient record / prior ANC).

**AC**

- GIVEN a patient aged 11 months, WHEN the worklist renders, THEN age is displayed as "11 mo" and the row carries an "Under 5" chip.
- GIVEN a patient with an active ANC episode, WHEN the worklist renders, THEN the row carries an "ANC" chip and the nurse action button routes to the ANC vitals form (ANC‑004) rather than general triage.
- GIVEN a nurse's session, WHEN the payload is inspected, THEN no prior diagnoses or notes are included.

**Perm** `queue.read:TRIAGE`. **UI** Under‑5 and pregnancy chips are colour‑coded and must survive colour‑blind review (icon + text, not colour alone).
**Dep** QUE‑002, PAT‑001. **OOS** Prior‑visit clinical summary on the worklist.
**Test** Age formatting boundaries (0–23 months, 2–4 years, ≥ 5 years).

---

### TRI‑002 — Start a triage record

**Epic** TRI · **P0** · **Primary** NURSE

**User story** As a triage nurse, I want to open a triage record for a called patient so I can record observations against the correct visit.

**Pre** Queue entry `CALLED` and locked to me; no completed triage on this visit.
**Trig** **Start triage**.
**Flow** System creates `TriageRecord(visit_id, patient_id, state=DRAFT, recorded_by, started_at)` and opens the observation form pre‑filled with the patient's last recorded height (if within 12 months) and known allergies banner.

**AC**

- GIVEN a called patient with no triage record, WHEN triage starts, THEN one `TriageRecord` in state `DRAFT` exists and the queue entry is `IN_SERVICE`.
- GIVEN the patient has a height recorded 3 months ago, WHEN the form opens, THEN the height field is pre‑filled and marked "from 12 Mar 2026 — confirm or change"; the value is only persisted to this record if the nurse confirms.
- GIVEN a completed triage already exists for the visit, WHEN start is attempted, THEN the existing record opens in amend mode (TRI‑009), and no second record is created.
- GIVEN a triage record is started and the nurse's session expires, WHEN they log back in, THEN the `DRAFT` record is recoverable with any autosaved values.

**Perm** `triage.create`. **Data** Insert `triage_record`. **Audit** `TRIAGE_STARTED`.
**Err** Visit closed → 409.
**UI** Allergy banner is red, persistent, and appears above the form. Autosave every 20 s to the server (never to browser storage).
**Dep** QUE‑005, PAT‑007. **OOS** Device integration for vitals capture.
**Test** Draft recovery; single‑record invariant.

---

### TRI‑003 — Record vital signs

**Epic** TRI · **P0** · **Primary** NURSE

**User story** As a triage nurse, I want to record temperature, blood pressure, pulse, respiratory rate, oxygen saturation, weight and height with unit‑safe validation, so the clinician can trust the numbers.

**Business value** Vitals are the most reused clinical data in the system: they drive acuity, dosing, ANC risk flags and follow‑up comparison.

**Pre** Triage record `DRAFT`.
**Trig** Entering values in the vitals form.

**Flow**

1. Nurse enters: temperature °C, systolic/diastolic mmHg, pulse bpm, respiratory rate /min, SpO2 %, weight kg, height cm; MUAC mm appears automatically for patients 6–59 months.
2. System computes BMI for ≥ 18 years and weight‑for‑age percentile band for < 5 years (simple table lookup, not a growth‑chart engine).
3. Out‑of‑range values raise a soft warning requiring confirmation; physiologically impossible values are hard‑rejected.
4. Nurse may mark any field **Not done** with a reason instead of leaving it blank.

**Alt**

- **A1 Equipment unavailable** → "Not done — equipment unavailable" is a first‑class value and does not block completion.
- **A2 Patient refuses** → "Not done — patient declined", audited.

**AC**

- GIVEN temperature 39.4 °C entered, WHEN saved, THEN the value persists and the field is flagged `abnormal_high` in the payload so the clinician queue can display a fever chip.
- GIVEN temperature 45.0 °C entered, WHEN saved, THEN 422 `VALUE_IMPLAUSIBLE` with the accepted range 30.0–43.0, and nothing is persisted.
- GIVEN systolic 90 and diastolic 120 entered, WHEN saved, THEN 422 `DIASTOLIC_EXCEEDS_SYSTOLIC`.
- GIVEN a patient aged 14 months, WHEN the form renders, THEN MUAC is present and required‑with‑reason, and BMI is not displayed.
- GIVEN a patient aged 34 years with weight 68 kg and height 170 cm, WHEN saved, THEN BMI is computed and stored as 23.5 (one decimal, server‑computed, never client‑computed).
- GIVEN SpO2 of 88%, WHEN saved, THEN the record is flagged `critical_low` and TRI‑005 pre‑selects `EMERGENCY` acuity with the reason pre‑filled, which the nurse may change.
- GIVEN a field marked "Not done — equipment unavailable", WHEN triage is completed, THEN completion is allowed and the clinician view displays "Not done (equipment unavailable)" rather than a blank.
- GIVEN any vital is saved, WHEN the audit log is read, THEN a `TRIAGE_VITALS_RECORDED` event contains the full value set.

**Perm** `triage.record_vitals` (NURSE, CLINICIAN, MIDWIFE).
**Data** `triage_record` vitals columns + `vitals_flags` JSON. Also written to a `vital_observation` table keyed by patient for longitudinal retrieval (TRI‑010).
**Audit** `TRIAGE_VITALS_RECORDED`; amendments audited separately (TRI‑009).
**Err** Non‑numeric input rejected at field level. Unit confusion is prevented by fixed units printed beside each field — no unit selector, because a wrong unit selection is a real safety risk.
**UI** Numeric keypad on mobile. Tab order follows the physical order of measurement. Each field shows its normal range for the patient's age band in small grey text. Abnormal values turn amber; critical values turn red with an icon.
**Dep** TRI‑002, PAT‑001 (age). **OOS** Growth charts, paediatric early warning scores, automated device capture, trend graphs (TRI‑010 gives a table, not a graph).
**Test** Age‑band matrix for range validation (neonate, infant, child, adolescent, adult, elderly). Server‑side BMI computation test. Implausible‑value rejection for every field.

---

### TRI‑004 — Record presenting complaint and duration

**Epic** TRI · **P0** · **Primary** NURSE

**User story** As a triage nurse, I want to record why the patient came and for how long, so the clinician starts the consultation already oriented.

**Pre** Triage record `DRAFT`.
**Trig** Complaint section of the triage form.
**Flow** Nurse selects one or more complaints from a facility‑configurable short list (fever, cough, diarrhoea, vomiting, abdominal pain, headache, injury, rash, difficulty breathing, dizziness, pregnancy‑related, review of results, other), each with a duration value + unit (hours/days/weeks), plus optional free text ≤ 500 chars. This is a **nursing observation**, explicitly not a diagnosis.

**AC**

- GIVEN complaints "fever" (3 days) and "cough" (5 days), WHEN saved, THEN both persist as separate structured rows with their durations, and both appear on the clinician's encounter screen as read‑only pre‑population.
- GIVEN "other" selected, WHEN free text is empty, THEN 422 `OTHER_REQUIRES_TEXT`.
- GIVEN "difficulty breathing" selected, WHEN saved, THEN the record is flagged as a danger sign and TRI‑005 suggests at least `PRIORITY`.
- GIVEN the clinician later records a diagnosis, WHEN the encounter is viewed, THEN the triage complaint remains visible and unmodified — the clinician cannot edit the nurse's complaint entry, only add their own history.

**Perm** `triage.record_complaint`. **Data** `triage_complaint` rows. **Audit** included in `TRIAGE_VITALS_RECORDED` or its own `TRIAGE_COMPLAINT_RECORDED`.
**Err** More than 5 complaints → 422 (triage is not a full history).
**UI** Chip‑style multi‑select with a duration stepper per selected chip. The free‑text box is deliberately small to discourage nurses writing the whole history at triage.
**Dep** TRI‑002, CAT‑006 (complaint list). **OOS** ICD coding at triage, symptom‑to‑diagnosis suggestion (that is CDS — out of scope).
**Test** Complaint‑limit rule; immutability from the clinician side.

---

### TRI‑005 — Assign triage acuity

**Epic** TRI · **P0** · **Primary** NURSE

**User story** As a triage nurse, I want to assign an acuity level with a documented reason, so the clinician queue orders patients by clinical need rather than arrival time.

**Business value** This is the single most important safety feature of the attendance loop.

**Pre** Vitals recorded or explicitly marked not done; complaint recorded.
**Trig** Acuity section, or auto‑suggestion from TRI‑003/TRI‑004 flags.

**Flow**

1. System suggests an acuity from recorded danger signs and critical vitals, with the triggering reason listed.
2. Nurse selects `EMERGENCY` (see immediately), `PRIORITY` (see before standard), or `STANDARD` (routine).
3. If the nurse selects a level **lower** than the suggestion, a reason is mandatory.
4. Acuity is written to the triage record and propagated to the clinician queue entry priority on completion.

**AC**

- GIVEN SpO2 88% recorded, WHEN the acuity section loads, THEN `EMERGENCY` is pre‑selected with the reason "SpO2 88% (critical low)" displayed.
- GIVEN the suggestion is `EMERGENCY` and the nurse selects `STANDARD`, WHEN they attempt to save without a reason, THEN 422 `DOWNGRADE_REASON_REQUIRED`; with a reason, the save succeeds and `TRIAGE_ACUITY_DOWNGRADED` is audited with both levels, the reason and the nurse ID.
- GIVEN acuity `EMERGENCY` is assigned, WHEN triage completes, THEN the clinician queue entry has `priority=EMERGENCY`, sorts first, and a visible alert appears on the clinician queue header ("1 emergency waiting").
- GIVEN no danger signs and all vitals normal, WHEN the acuity section loads, THEN `STANDARD` is pre‑selected and no reason is required.
- GIVEN acuity is assigned, WHEN the clinician opens the encounter, THEN the acuity and its reason are displayed in the header.

**Perm** `triage.assign_acuity` (NURSE, CLINICIAN, MIDWIFE).
**Data** `triage_record.acuity`, `acuity_source` (`SUGGESTED`/`MANUAL`), `acuity_reason`.
**Audit** `TRIAGE_ACUITY_ASSIGNED`, conditional `TRIAGE_ACUITY_DOWNGRADED`.
**Err** Attempting to complete triage without acuity → 422.
**UI** Three large buttons, colour + label + icon. The suggestion is shown as a hint, never as a locked value — the nurse is accountable for the decision.
**Dep** TRI‑003, TRI‑004, QUE‑001, QUE‑009.
**OOS** Validated scoring instruments (SATS, MTS), automatic escalation without a human, deterioration prediction.
**Test** Suggestion matrix across vitals and danger‑sign combinations; downgrade‑reason enforcement; priority propagation.

---

### TRI‑006 — Complete triage and send to the clinician

**Epic** TRI · **P0** · **Primary** NURSE

**User story** As a triage nurse, I want to complete triage and place the patient on the correct clinician queue, so the handoff is explicit and timed.

**Pre** Triage record `DRAFT` with vitals (or not‑done reasons), complaint and acuity present.
**Trig** **Complete triage**.

**Flow**

1. Completeness check; missing mandatory items are listed.
2. Nurse selects the destination: general clinician queue, a named clinician, or a specific department.
3. Triage record → `COMPLETED`, `completed_at`, `completed_by` set; the record becomes read‑only except via amendment (TRI‑009).
4. Triage queue entry → `COMPLETED`; clinician queue entry created with the acuity priority (QUE‑001/QUE‑006).

**Alt**

- **A1 Acuity `EMERGENCY`** → the patient is placed at the top of the queue _and_ the nurse is prompted to notify a clinician directly; the system records that the prompt was shown and whether the nurse confirmed notification.
- **A2 Patient needs a lab test before seeing a clinician** (facility protocol, e.g. malaria RDT) → nurse may route to LAB first with `nurse_initiated=true`; this is permitted only for tests on the facility's nurse‑orderable list (CAT‑007).

**AC**

- GIVEN a complete triage record with acuity `PRIORITY`, WHEN completed with destination "General clinician queue", THEN the triage record is `COMPLETED` and immutable, and a `WAITING` clinician queue entry exists with `priority=PRIORITY`.
- GIVEN acuity `EMERGENCY`, WHEN triage is completed, THEN the notification prompt is displayed, the nurse's confirmation (or dismissal) is recorded in `TRIAGE_COMPLETED.after_json`, and the clinician queue shows a red banner.
- GIVEN the nurse routes to a named clinician who is not on duty today, WHEN completion is attempted, THEN a warning is shown with the option to use the general queue; proceeding is allowed and audited.
- GIVEN missing acuity, WHEN completion is attempted, THEN 422 listing "Acuity required" and the record stays `DRAFT`.
- GIVEN triage completes, WHEN the clinician opens the patient, THEN vitals, complaints, acuity and the nurse's name and time are all visible without further navigation.
- GIVEN a nurse‑initiated malaria RDT under A2, WHEN triage completes, THEN a lab order exists with `ordered_by=<nurse>`, `nurse_initiated=true`, and the patient goes to the LAB queue, not the clinician queue.

**Perm** `triage.complete`; nurse‑initiated ordering requires `lab.order_nurse_scope`.
**Data** `triage_record` state + timestamps; queue transitions; conditional lab order.
**Audit** `TRIAGE_COMPLETED`, `QUEUE_HANDOFF`, conditional `LAB_ORDER_CREATED`.
**Err** Concurrent completion → 409 with current state.
**UI** The completion screen summarises what the clinician will see, so the nurse can check it reads correctly. Destination defaults to the general queue.
**Dep** TRI‑003, TRI‑004, TRI‑005, QUE‑006, CAT‑007, LAB‑002.
**OOS** Nurse prescribing, nurse diagnosis, standing orders beyond the configured nurse‑orderable test list.
**Test** Mandatory‑field matrix; emergency prompt recording; nurse‑initiated lab path end to end.

---

### TRI‑007 — Clinician views triage information

**Epic** TRI · **P0** · **Primary** CLINICIAN · **Secondary** MIDWIFE

**User story** As a clinician, I want the triage data presented at the top of the encounter without clicking, so I begin the consultation informed.

**Business value** The user explicitly identified this as a granular requirement; it is also the main reason clinicians trust or ignore a triage module.

**Pre** Visit has a `COMPLETED` triage record; clinician has started service.
**Trig** Opening the encounter workspace.

**Flow** A fixed triage panel shows: acuity chip + reason; vitals in a single row with abnormal values highlighted and normal ranges on hover; complaints with durations; recorded‑by name and time; "recorded 23 min ago" freshness indicator; a link to the previous visit's vitals for comparison.

**AC**

- GIVEN triage recorded temp 39.4, BP 130/85, pulse 104, RR 22, SpO2 97, weight 62 kg, WHEN the encounter opens, THEN all seven values are visible above the fold without scrolling on a 1366×768 screen, with temp and pulse highlighted amber.
- GIVEN a vital marked "Not done — equipment unavailable", WHEN the panel renders, THEN it shows "BP: not done (equipment unavailable)" and not a blank or a zero.
- GIVEN triage was recorded 3 hours ago (patient waited long), WHEN the panel renders, THEN a freshness warning appears: "Vitals are 3 h old — consider repeating."
- GIVEN the patient has vitals from a prior visit, WHEN the clinician clicks "Compare", THEN a table of the last three visits' vitals is shown with dates, and this read is audited as `PHI_READ`.
- GIVEN a clinician amends nothing, WHEN they leave the encounter, THEN the triage record is byte‑identical to what the nurse saved.

**Perm** `triage.read` (CLINICIAN, MIDWIFE, NURSE, SUPERVISOR). Cashier, receptionist and pharmacist do **not** have it.
**Data** Read‑only. **Audit** `PHI_READ` on encounter open covers the triage panel.
**Err** No triage record (patient routed directly) → panel shows "No triage recorded for this visit" with a **Record vitals now** action if the clinician has `triage.record_vitals`.
**UI** The panel is collapsible but defaults to expanded and its state is per‑user, stored server‑side in user preferences (not browser storage).
**Dep** TRI‑003–006, ENC‑002, TRI‑010.
**OOS** Graphical trends, automatic interpretation of vitals.
**Test** Above‑the‑fold rendering test at the target resolution; freshness threshold; not‑done rendering.

---

### TRI‑008 — Clinician or nurse repeats vitals during the visit

**Epic** TRI · **P1** · **Primary** CLINICIAN, NURSE

**User story** As a clinician, I want to record a second set of vitals during the same visit, so deterioration or response to treatment is documented without altering the triage record.

**Pre** Visit `IN_PROGRESS`; a completed triage record exists.
**Trig** **Repeat vitals**.
**Flow** A new `vital_observation` set is created with `context=REPEAT`, `sequence=n`, linked to the visit and encounter; the original triage record is untouched.

**AC**

- GIVEN a triage set at 09:10 and a repeat set at 10:25, WHEN the encounter is viewed, THEN both sets are listed chronologically with their contexts and authors, and the triage record's own values are unchanged.
- GIVEN a repeat set shows SpO2 dropping from 96% to 89%, WHEN saved, THEN the value is flagged critical and the clinician is offered a one‑click escalation of the queue priority (QUE‑009) if the patient is returning to a queue.
- GIVEN a nurse records the repeat set while the encounter is open, WHEN the clinician's screen refreshes, THEN the new set appears without losing any unsaved note text the clinician has typed.

**Perm** `triage.record_vitals`.
**Data** Insert `vital_observation` rows only; never update triage.
**Audit** `VITALS_RECORDED` with context `REPEAT`.
**Err** Same validation as TRI‑003.
**UI** Compact inline form; only the fields being repeated need values.
**Dep** TRI‑003, ENC‑002. **OOS** Continuous monitoring, observation charts.
**Test** Concurrent‑edit test proving the clinician's unsaved text survives.

---

### TRI‑009 — Amend a completed triage record

**Epic** TRI · **P1** · **Primary** NURSE (author) · **Secondary** SUPERVISOR

**User story** As the nurse who recorded triage, I want to correct a transcription error, so the record is accurate while the original value remains visible for audit.

**Business value** Clinical records must be correctable but never silently rewritable.

**Pre** Triage record `COMPLETED`; amendment within the facility's window (default 24 h) or with supervisor permission.
**Trig** **Amend** on the triage record.

**Flow** Nurse edits values and supplies a mandatory reason. System stores an `amendment` row with before/after values, author and reason; the current record shows the corrected value with an "Amended" marker; the original remains retrievable.

**AC**

- GIVEN temperature was recorded as 3.74 (typo for 37.4), WHEN the author amends it to 37.4 with reason "transcription error", THEN the displayed value is 37.4, an "Amended" badge with a hover showing "was 3.74, corrected by S. Nabirye 09:32, reason: transcription error" is present, and `TRIAGE_AMENDED` records both values.
- GIVEN a non‑author nurse attempts amendment, WHEN submitted, THEN 403 unless they hold `triage.amend_any` (SUPERVISOR).
- GIVEN the 24 h window has passed, WHEN the author attempts amendment, THEN 422 `AMENDMENT_WINDOW_EXPIRED` with instruction to request supervisor amendment.
- GIVEN an amendment changes acuity after the clinician has already seen the patient, WHEN saved, THEN the queue priority is **not** retroactively changed and a notice explains why.
- GIVEN any amendment, WHEN the encounter is later printed, THEN the printed record shows the current value and an amendment footnote.

**Perm** `triage.amend_own` (author, within window), `triage.amend_any` (SUPERVISOR, FACILITY_ADMIN).
**Data** Insert `record_amendment`; update the live record.
**Audit** `TRIAGE_AMENDED` with full before/after JSON and reason.
**Err** Empty reason → 422. Amendment of a record on a closed and reported visit → allowed but flagged in REP‑009 data‑quality report.
**UI** Amended fields carry a small badge everywhere they appear, including the clinician's triage panel.
**Dep** TRI‑006, AUD‑003. **OOS** Deleting a triage record (never permitted).
**Test** Author vs non‑author permission; window boundary; badge propagation to all views.

---

### TRI‑010 — View the patient's vitals history

**Epic** TRI · **P1** · **Primary** CLINICIAN, NURSE, MIDWIFE

**User story** As a clinician, I want to see this patient's previous vitals in a table, so I can judge whether today's values represent a change.

**Pre** Patient has ≥ 1 prior recorded vital set at this facility.
**Trig** **Compare / history** in the triage panel.
**Flow** Table: date, context (triage/repeat/ANC), each vital, recorded by. Default last 5 sets, expandable to 12 months.

**AC**

- GIVEN 8 prior vital sets, WHEN history opens, THEN the 5 most recent are shown newest first, with a "show more" control.
- GIVEN sets recorded at another facility in the same organisation, WHEN history opens, THEN they are included only if the organisation's cross‑branch sharing setting is enabled (BRN‑003), and each row is labelled with its facility.
- GIVEN cross‑branch sharing is disabled, WHEN history opens, THEN only this facility's sets appear and no count of hidden records is leaked.
- GIVEN history is opened, WHEN audited, THEN one `PHI_READ` event is recorded with the patient ID and the record count returned.

**Perm** `triage.read`, plus `patient.read_cross_facility` for the shared case.
**UI** Plain table. Abnormal values highlighted with the same rules as TRI‑003. Deliberately no charts in V1.
**Dep** TRI‑003, BRN‑003. **OOS** Trend graphs, growth charts, export.
**Test** Cross‑branch visibility both ways; audit event correctness.

---

### TRI‑011 — Record allergies and current medicines at triage

**Epic** TRI · **P0** · **Primary** NURSE · **Secondary** CLINICIAN, PHARMACIST

**User story** As a triage nurse, I want to record or confirm known allergies and medicines the patient is already taking, so prescribing and dispensing are safer.

**Business value** This is the only medication‑safety data V1 collects; it must be captured by someone, and triage is the reliable point.

**Pre** Triage record `DRAFT`.
**Trig** Allergy section of the triage form; mandatory to either enter or explicitly confirm "no known allergies".

**Flow** Nurse records allergen (free text with a facility short list of common ones: penicillin, sulfa, aspirin/NSAIDs, other), reaction type (rash, swelling, breathing difficulty, other) and severity (mild/severe). Current medicines are free‑text lines. Allergies persist at **patient** level, not visit level, and appear on every subsequent visit.

**AC**

- GIVEN a nurse records "Penicillin — rash — mild", WHEN saved, THEN a `patient_allergy` row is created at patient level with `recorded_by`, `recorded_at`, and the red allergy banner appears on every screen showing this patient thereafter, including the pharmacist's dispense screen.
- GIVEN the nurse selects "No known allergies", WHEN saved, THEN `patient.allergy_status = NKA` with a timestamp, and the banner shows a neutral "No known allergies (confirmed 20 Aug 2026)".
- GIVEN neither allergies nor NKA is set, WHEN triage completion is attempted, THEN 422 `ALLERGY_STATUS_REQUIRED`.
- GIVEN an allergy exists and a clinician prescribes an item whose generic name string‑matches the recorded allergen, WHEN the prescription line is saved, THEN a **warning** is displayed requiring explicit acknowledgment with a reason, and the acknowledgment is audited. (String match only — this is not a drug‑interaction engine and is documented as such.)
- GIVEN an allergy was recorded at a previous visit, WHEN today's triage opens, THEN it is displayed as existing with a **Confirm still accurate** action rather than requiring re‑entry.
- GIVEN a recorded allergy is later found to be wrong, WHEN a clinician marks it `REFUTED` with a reason, THEN it is not deleted; it is displayed struck‑through in history and removed from the active banner.

**Perm** `patient.record_allergy` (NURSE, CLINICIAN, MIDWIFE, PHARMACIST); refute requires `patient.refute_allergy` (CLINICIAN).
**Data** `patient_allergy`, `patient.allergy_status`, `patient_current_medicine`.
**Audit** `ALLERGY_RECORDED`, `ALLERGY_CONFIRMED`, `ALLERGY_REFUTED`, `ALLERGY_WARNING_OVERRIDDEN`.
**Err** Free‑text allergen > 100 chars → 422.
**UI** The banner is the same component everywhere (triage, encounter, prescription, dispense) so it is unmissable. It is never dismissible.
**Dep** PAT‑007, RX‑004, DSP‑004.
**OOS** Coded allergen terminologies, cross‑reactivity logic, drug–drug interaction checking, any form of clinical decision support beyond exact‑string matching.
**Test** Banner presence on all five screens; the override‑acknowledgment path; NKA enforcement.

---

### TRI‑012 — Triage a patient without a prior check‑in (walk‑in emergency)

**Epic** TRI · **P1** · **Primary** NURSE

**User story** As a triage nurse, I want to start triage immediately for a collapsing patient and let reception complete registration afterwards, so care is never delayed by paperwork.

**Business value** A system that forces registration before emergency assessment will be bypassed on paper, and the record will be lost.

**Pre** Nurse has `triage.create_emergency`.
**Trig** **Emergency triage** button on the triage home screen.

**Flow**

1. Nurse enters a minimum identity set: any known name (or "Unknown male, approx 30"), approximate age, sex.
2. System creates a provisional `Patient` with `is_provisional=true`, a temporary identifier, plus a `Visit` and a `TriageRecord`, and places the patient at the top of the clinician queue with `EMERGENCY` priority.
3. A task appears on reception's list: "Complete registration — provisional patient".
4. Reception later merges or completes the record (PAT‑002 merge path) without breaking the encounter link.

**AC**

- GIVEN the nurse enters "Unknown male, approx 30", WHEN emergency triage is created, THEN a provisional patient, an open visit and a triage record exist, the clinician queue shows the entry first with an `EMERGENCY` chip and a "Provisional record" chip, and reception's follow‑up list has one item.
- GIVEN a provisional patient, WHEN reception later matches them to an existing patient record and merges, THEN the visit, triage record and any encounter re‑point to the surviving patient ID, the provisional record is retired (not deleted), and `PATIENT_MERGED` is audited with both IDs and all moved record counts.
- GIVEN a provisional patient, WHEN an invoice is created, THEN it is permitted, and after a merge the invoice belongs to the surviving patient.
- GIVEN a provisional patient record older than 24 h that has not been completed, WHEN the daily sweep runs, THEN it appears on the data‑quality exceptions report (REP‑009) and is not auto‑deleted.
- GIVEN a receptionist without `triage.create_emergency`, WHEN they attempt this action, THEN 403.

**Perm** `triage.create_emergency` (NURSE, CLINICIAN, MIDWIFE).
**Data** Insert provisional `patient`, `visit`, `triage_record`, `queue_entry`.
**Audit** `PROVISIONAL_PATIENT_CREATED`, `TRIAGE_STARTED`, later `PATIENT_MERGED`.
**Err** Merge conflicts (both records have allergies) → merge screen requires explicit resolution per conflicting field; no silent overwrite.
**UI** The emergency button is visually distinct and requires a single confirmation tap; the form has four fields maximum.
**Dep** PAT‑002, REC‑001, QUE‑001.
**OOS** Mass‑casualty batch registration, unidentified‑patient photography.
**Test** Full merge test verifying referential integrity across visit, triage, encounter, invoice and payment.

---

# Queue Entry — State Machine (delivered here since QUE is complete)

**States:** `WAITING`, `WAITING_PAYMENT`, `CALLED`, `IN_SERVICE`, `COMPLETED`, `NO_SHOW`, `REMOVED`, `EXPIRED`.
**Terminal:** `COMPLETED`, `REMOVED`, `EXPIRED`. (`NO_SHOW` is semi‑terminal — reception can re‑queue it.)

| From                         | To                | Trigger                               | Who                      | Guard                                                       |
| ---------------------------- | ----------------- | ------------------------------------- | ------------------------ | ----------------------------------------------------------- |
| —                            | `WAITING`         | Check‑in / stage handoff              | RECEPTIONIST, SYSTEM     | Visit open; target queue enabled; no active duplicate entry |
| —                            | `WAITING_PAYMENT` | Check‑in under `PAY_BEFORE_*` policy  | SYSTEM                   | Facility gating policy set; invoice drafted                 |
| `WAITING_PAYMENT`            | `WAITING`         | Payment confirmed                     | CASHIER, SYSTEM          | Invoice balance ≤ 0 for gated items                         |
| `WAITING`                    | `CALLED`          | Call next / call specific             | Serving role             | Entry not locked; caller has queue permission               |
| `CALLED`                     | `IN_SERVICE`      | Start service                         | Locking user             | Lock still valid; stage record creatable                    |
| `CALLED`                     | `WAITING`         | No‑show (1st) or lock timeout         | Serving role, SYSTEM     | `no_show_count < 1`                                         |
| `CALLED`                     | `NO_SHOW`         | No‑show (2nd)                         | Serving role             | `no_show_count ≥ 1`                                         |
| `IN_SERVICE`                 | `COMPLETED`       | Stage completion                      | Serving role             | Stage mandatory data satisfied                              |
| `IN_SERVICE`                 | `WAITING`         | Service abandoned (staff called away) | Serving role, SUPERVISOR | Reason required; stage record left in DRAFT                 |
| `IN_SERVICE`                 | reassigned        | Takeover                              | SUPERVISOR               | Idle > threshold; reason required                           |
| `WAITING`/`CALLED`/`NO_SHOW` | `REMOVED`         | Manual removal / LWBS                 | RECEPTIONIST, SUPERVISOR | Reason required; no signed stage record                     |
| `WAITING`/`CALLED`/`NO_SHOW` | `EXPIRED`         | Nightly sweep                         | SYSTEM                   | Entry from a previous service day                           |

**Invariants:** a visit has at most one active (non‑terminal) queue entry at any moment; `wait_seconds` freezes at `IN_SERVICE`; entries are never hard‑deleted; every transition writes an audit event with actor and reason where a reason is required.

---

# Handoff Matrix — Attendance Loop rows (Reception → Triage → Clinician)

| From role        | Action                                            | To role                  | Record + new state                                                           | What the receiving role sees                                                                                                  |
| ---------------- | ------------------------------------------------- | ------------------------ | ---------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| RECEPTIONIST     | Confirm check‑in (REC‑001)                        | NURSE                    | `Visit=OPEN`, `QueueEntry(TRIAGE)=WAITING`                                   | Token, name, age (months if <5), sex, visit type, wait timer, under‑5 / ANC chips                                             |
| RECEPTIONIST     | Check in `LAB_ONLY` (REC‑004)                     | LAB_TECH                 | `QueueEntry(LAB)=WAITING`                                                    | Token, name, prior released orders, no consultation charge flag                                                               |
| RECEPTIONIST     | Check in `FOLLOW_UP_RESULTS` (REC‑004)            | CLINICIAN                | `QueueEntry(CLINICIAN)=WAITING`, `results_review=true`                       | "Results ready (n)" badge, link to released results, the original encounter ID                                                |
| CASHIER          | Confirm consultation payment (PAY‑003)            | NURSE                    | `QueueEntry=WAITING_PAYMENT → WAITING`                                       | Patient now appears on the triage list; payment chip = Paid                                                                   |
| NURSE            | Complete triage (TRI‑006)                         | CLINICIAN                | `TriageRecord=COMPLETED`, `QueueEntry(CLINICIAN)=WAITING` at acuity priority | Acuity chip + reason, all vitals with abnormal highlighting, complaints + durations, allergy banner, recording nurse and time |
| NURSE            | Escalate priority (TRI‑005 / QUE‑009)             | CLINICIAN                | `QueueEntry.priority=EMERGENCY`                                              | Red banner "1 emergency waiting" with the escalation reason and nurse name                                                    |
| NURSE            | Nurse‑initiated RDT (TRI‑006 A2)                  | LAB_TECH                 | `LabOrder=REQUESTED`, `QueueEntry(LAB)=WAITING`                              | Test name, `nurse_initiated` flag, ordering nurse, triage acuity                                                              |
| NURSE            | Emergency triage of provisional patient (TRI‑012) | CLINICIAN + RECEPTIONIST | Provisional `Patient`, `Visit=OPEN`, `QueueEntry=WAITING/EMERGENCY`          | Clinician: top of queue with "Provisional record" chip. Reception: "Complete registration" task                               |
| Any serving role | Mark LWBS (REC‑009)                               | RECEPTIONIST             | `QueueEntry=REMOVED`, `Visit=CLOSED_LWBS`                                    | Removed from all active lists; appears in the day's LWBS tally; refund task if paid                                           |

---

## Where this leaves us

Delivered so far: AUTH, TEN, USR, CAT, PAT (Part 1–2) and REC, QUE, TRI (this part) — 71 of 214 stories, with the Queue‑Entry state machine and 9 of 27 handoff rows.

**Part 4 (next):** ENC — Clinical Encounter (20 stories, including the encounter‑stays‑open rule, clerking with history/examination, working diagnosis, plan, signing and immutability, addenda, and the resume‑after‑results path), and LAB — Lab Orders & Results (18 stories: order composition, payment gating, specimen collection, worklist, result entry, verification, release, critical‑result flagging, rejection and re‑collection, and the return to the clinician). Both epics' state machines (Encounter, Lab Order) ship with them.

**Part 5:** DX, RX, PHM, INV, DSP, BIL, PAY, RCP with the Invoice, Payment, Prescription and Dispense state machines.

**Part 6:** ANC, APT, REP, AUD, BRN, OPS, then the consolidated permissions matrix, audit event catalogue, gap analysis (IMPLEMENTED / PARTIAL / NOT IMPLEMENTED / UNKNOWN against your existing foundation), priority summary, the four implementation waves, the per‑slice definition of done, and the open product decisions register.

Two decisions surfaced in this part that I have provisionally resolved and flagged for the open‑decisions register: the **triage acuity scheme** (I used a 3‑tier Emergency/Priority/Standard rather than a validated instrument like SATS, on the grounds that a small private clinic cannot sustain formal triage training — worth a clinician review), and the **allergy warning being exact‑string match only** (deliberately not a drug‑knowledge base, since that would be clinical decision support and is out of scope; the risk is false reassurance, so the UI must state that no automatic checking is performed).
