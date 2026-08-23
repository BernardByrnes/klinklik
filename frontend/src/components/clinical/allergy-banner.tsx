"use client";

import { useEffect, useState, type FormEvent } from "react";

import { ActiveAllergy, AllergyStatus, Encounter } from "../../features/clinic";
import { Button, Field, Select, StatusBadge, TextInput, Textarea, formatTime } from "../ui";
import { IconAlertTriangle, IconCheckCircle, IconPlus } from "../icons";

export type AllergyFormValues = {
  substance: string;
  reaction: string;
  severity: ActiveAllergy["severity"] | "";
};

type EditableAllergyStatus = Extract<AllergyStatus, "NKA" | "UNKNOWN">;

type AllergyBannerProps = {
  encounter: Encounter;
  canManage: boolean;
  canReview: boolean;
  mutationPending: boolean;
  mutationError: string;
  onSetStatus: (status: EditableAllergyStatus) => Promise<void>;
  onAddAllergy: (values: AllergyFormValues) => Promise<void>;
  onEnterInError: (allergyId: string, reason: string) => Promise<void>;
  onReview: () => Promise<void>;
  onFormDirtyChange: (dirty: boolean) => void;
};

const EMPTY_FORM: AllergyFormValues = { substance: "", reaction: "", severity: "" };

function severityLabel(severity: ActiveAllergy["severity"]) {
  return severity.charAt(0) + severity.slice(1).toLowerCase();
}

function statusTone(status: AllergyStatus) {
  if (status === "NOT_RECORDED") return "border-accent-orange/40 bg-accent-orange-soft";
  if (status === "RECORDED") return "border-accent-pink/30 bg-accent-pink-soft";
  return "border-accent-teal/30 bg-accent-teal-soft";
}

export function AllergyBanner({
  encounter,
  canManage,
  canReview,
  mutationPending,
  mutationError,
  onSetStatus,
  onAddAllergy,
  onEnterInError,
  onReview,
  onFormDirtyChange,
}: AllergyBannerProps) {
  const [addOpen, setAddOpen] = useState(false);
  const [form, setForm] = useState<AllergyFormValues>(EMPTY_FORM);
  const [formError, setFormError] = useState("");
  const [enteredInErrorId, setEnteredInErrorId] = useState<string | null>(null);
  const [enteredInErrorReason, setEnteredInErrorReason] = useState("");
  const [enteredInErrorError, setEnteredInErrorError] = useState("");

  const readOnly = ["SIGNED", "CLOSED", "CANCELLED"].includes(encounter.status);
  const activeAllergies = encounter.active_allergies ?? [];
  const hasActiveAllergies = activeAllergies.length > 0;
  const allergyStatus = encounter.allergy_status ?? "NOT_RECORDED";

  useEffect(() => {
    onFormDirtyChange(
      (addOpen && (form.substance.length > 0 || form.reaction.length > 0 || form.severity.length > 0)) ||
        enteredInErrorReason.length > 0,
    );
  }, [addOpen, enteredInErrorReason, form, onFormDirtyChange]);

  function resetAddForm() {
    setAddOpen(false);
    setForm(EMPTY_FORM);
    setFormError("");
  }

  function closeEnteredInErrorForm() {
    setEnteredInErrorId(null);
    setEnteredInErrorReason("");
    setEnteredInErrorError("");
  }

  async function submitAddAllergy(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (form.substance.trim().length === 0) {
      setFormError("Enter the allergy substance.");
      return;
    }
    if (!form.severity) {
      setFormError("Choose a severity.");
      return;
    }
    setFormError("");
    try {
      await onAddAllergy(form);
      resetAddForm();
    } catch {
      // The parent owns the authoritative error message and keeps this draft intact.
    }
  }

  async function submitEnteredInError(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!enteredInErrorId) return;
    if (enteredInErrorReason.trim().length === 0) {
      setEnteredInErrorError("Enter a reason before confirming.");
      return;
    }
    setEnteredInErrorError("");
    try {
      await onEnterInError(enteredInErrorId, enteredInErrorReason);
      closeEnteredInErrorForm();
    } catch {
      // The parent owns the authoritative error message and keeps this draft intact.
    }
  }

  function statusHeading() {
    if (allergyStatus === "NOT_RECORDED") return "Allergies: Not recorded";
    if (allergyStatus === "NKA") return "No known allergies";
    if (allergyStatus === "UNKNOWN") return "Allergy status: Unknown";
    return "Recorded allergies";
  }

  return (
    <section
      id="allergy-banner"
      data-testid="allergy-banner"
      aria-label="Allergy status"
      className={`rounded-[16px] border px-4 py-4 ${statusTone(allergyStatus)}`}
    >
      <div className="flex flex-wrap items-start gap-3">
        <span className="mt-0.5 shrink-0 text-accent-orange">
          {allergyStatus === "NOT_RECORDED" ? (
            <IconAlertTriangle className="h-5 w-5" />
          ) : (
            <IconCheckCircle className="h-5 w-5 text-accent-teal" />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-[14px] font-bold text-ink">{statusHeading()}</h2>
            {allergyStatus === "RECORDED" ? <StatusBadge tone="pink">Active record</StatusBadge> : null}
          </div>

          {allergyStatus === "NOT_RECORDED" ? (
            <p className="mt-1 text-[12px] font-medium text-ink">Record the patient&apos;s allergy status before signing.</p>
          ) : null}

          {allergyStatus === "RECORDED" ? (
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {activeAllergies.map((allergy) => (
                <article
                  key={allergy.id}
                  data-testid={`active-allergy-${allergy.id}`}
                  className="rounded-[12px] border border-white/80 bg-white/75 px-3 py-2.5"
                >
                  <p className="text-[13px] font-bold text-ink">{allergy.substance}</p>
                  {allergy.reaction ? <p className="mt-1 text-[11.5px] font-medium text-secondary">Reaction: {allergy.reaction}</p> : null}
                  <p className="mt-1 text-[11.5px] font-medium text-secondary">Severity: {severityLabel(allergy.severity)}</p>
                  {canManage && !readOnly ? (
                    enteredInErrorId === allergy.id ? (
                      <form className="mt-3 grid gap-2" noValidate onSubmit={submitEnteredInError}>
                        <Field label="Reason for entering in error" htmlFor={`entered-in-error-reason-${allergy.id}`}>
                          <Textarea
                            id={`entered-in-error-reason-${allergy.id}`}
                            className="min-h-[84px] bg-white"
                            maxLength={1000}
                            required
                            value={enteredInErrorReason}
                            onChange={(event) => setEnteredInErrorReason(event.target.value)}
                          />
                        </Field>
                        {enteredInErrorError ? <p role="alert" className="text-[11.5px] font-medium text-accent-pink">{enteredInErrorError}</p> : null}
                        <div className="flex flex-wrap gap-2">
                          <Button variant="danger" disabled={mutationPending} type="submit">
                            Confirm entered in error
                          </Button>
                          <Button variant="small-secondary" onClick={closeEnteredInErrorForm}>
                            Cancel
                          </Button>
                        </div>
                      </form>
                    ) : (
                      <Button
                        variant="small-secondary"
                        className="mt-3"
                        disabled={mutationPending}
                        onClick={() => {
                          setEnteredInErrorId(allergy.id);
                          setEnteredInErrorReason("");
                          setEnteredInErrorError("");
                        }}
                      >
                        Mark entered in error
                      </Button>
                    )
                  ) : null}
                </article>
              ))}
            </div>
          ) : null}

          {encounter.allergies_review_is_current ? (
            <p className="mt-3 flex items-center gap-1.5 text-[11.5px] font-semibold text-accent-teal-text">
              <IconCheckCircle className="h-4 w-4" />
              Reviewed for this encounter{encounter.allergies_reviewed_at ? ` at ${formatTime(encounter.allergies_reviewed_at)}` : ""}
            </p>
          ) : allergyStatus !== "NOT_RECORDED" ? (
            <p className="mt-3 text-[11.5px] font-semibold text-accent-orange-text">
              {encounter.allergies_reviewed_revision !== null && encounter.allergies_reviewed_revision !== encounter.allergy_revision
                ? "Allergy information changed — review again before signing."
                : "Allergy status not yet reviewed for this encounter."}
            </p>
          ) : null}

          {canReview && !readOnly && allergyStatus !== "NOT_RECORDED" && !encounter.allergies_review_is_current ? (
            <Button
              variant="small-secondary"
              className="mt-3"
              disabled={mutationPending}
              onClick={() => void onReview().catch(() => undefined)}
            >
              {mutationPending ? "Reviewing…" : "Review allergies"}
            </Button>
          ) : null}

          {mutationError ? <p role="alert" className="mt-3 text-[11.5px] font-semibold text-accent-pink">{mutationError}</p> : null}

          {canManage && !readOnly ? (
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                variant="small-secondary"
                disabled={mutationPending}
                onClick={() => {
                  setAddOpen((open) => !open);
                  setFormError("");
                }}
              >
                <IconPlus className="h-3.5 w-3.5" />
                {addOpen ? "Close add allergy" : "Add allergy"}
              </Button>
              {!hasActiveAllergies ? (
                <>
                  <Button
                    variant="small-secondary"
                    disabled={mutationPending || allergyStatus === "NKA"}
                    onClick={() => void onSetStatus("NKA").catch(() => undefined)}
                  >
                    No known allergies
                  </Button>
                  <Button
                    variant="small-secondary"
                    disabled={mutationPending || allergyStatus === "UNKNOWN"}
                    onClick={() => void onSetStatus("UNKNOWN").catch(() => undefined)}
                  >
                    Unknown
                  </Button>
                </>
              ) : null}
            </div>
          ) : null}

          {addOpen && canManage && !readOnly ? (
            <form className="mt-4 grid gap-3 rounded-[14px] border border-line-soft bg-white/75 p-3" noValidate onSubmit={submitAddAllergy}>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Substance" htmlFor="allergy-substance">
                  <TextInput
                    id="allergy-substance"
                    maxLength={150}
                    required
                    value={form.substance}
                    onChange={(event) => setForm((current) => ({ ...current, substance: event.target.value }))}
                  />
                </Field>
                <Field label="Severity" htmlFor="allergy-severity">
                  <Select
                    id="allergy-severity"
                    required
                    value={form.severity}
                    onChange={(event) => setForm((current) => ({ ...current, severity: event.target.value as AllergyFormValues["severity"] }))}
                  >
                    <option value="">Choose severity</option>
                    <option value="MILD">Mild</option>
                    <option value="MODERATE">Moderate</option>
                    <option value="SEVERE">Severe</option>
                  </Select>
                </Field>
              </div>
              <Field label="Reaction (optional)" htmlFor="allergy-reaction">
                <Textarea
                  id="allergy-reaction"
                  className="min-h-[84px]"
                  maxLength={200}
                  value={form.reaction}
                  onChange={(event) => setForm((current) => ({ ...current, reaction: event.target.value }))}
                />
              </Field>
              {formError ? <p role="alert" className="text-[11.5px] font-medium text-accent-pink">{formError}</p> : null}
              <div className="flex flex-wrap gap-2">
                <Button type="submit" disabled={mutationPending}>Save allergy</Button>
                <Button variant="small-secondary" onClick={resetAddForm}>Cancel</Button>
              </div>
            </form>
          ) : null}
        </div>
      </div>
    </section>
  );
}
