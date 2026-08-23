"use client";

import { useEffect, useState, type FormEvent } from "react";

import { Diagnosis, DiagnosisType } from "../../features/clinic";
import { Button, Field, StatusBadge, TextInput, Textarea } from "../ui";

export type DiagnosisWritePayload = {
  diagnosis_type: DiagnosisType;
  label?: string;
  code?: string;
  certainty_note?: string;
  is_primary?: boolean;
  no_diagnosis_reason?: string;
};

export type DiagnosisDraftForm = {
  label: string;
  code: string;
  certainty_note: string;
  is_primary: boolean;
};

export type DiagnosisEditorForm = DiagnosisDraftForm & {
  id: string;
  diagnosis_type: DiagnosisType;
  no_diagnosis_reason: string;
  mode: "edit" | "promote";
  initial: DiagnosisDraftForm & {
    diagnosis_type: DiagnosisType;
    no_diagnosis_reason: string;
  };
};

export type DiagnosisFormState = {
  workingOpen: boolean;
  working: DiagnosisDraftForm;
  finalOpen: boolean;
  final: DiagnosisDraftForm;
  noDiagnosisOpen: boolean;
  noDiagnosisReason: string;
  editor: DiagnosisEditorForm | null;
};

export function emptyDiagnosisFormState(): DiagnosisFormState {
  return {
    workingOpen: false,
    working: { label: "", code: "", certainty_note: "", is_primary: false },
    finalOpen: false,
    final: { label: "", code: "", certainty_note: "", is_primary: false },
    noDiagnosisOpen: false,
    noDiagnosisReason: "",
    editor: null,
  };
}

type DiagnosisSectionProps = {
  status: string;
  diagnoses: Diagnosis[];
  canManage: boolean;
  mutationPending: boolean;
  mutationError: string;
  formState: DiagnosisFormState;
  onFormStateChange: (state: DiagnosisFormState) => void;
  onCreate: (payload: DiagnosisWritePayload) => Promise<void>;
  onSaveEdit: (diagnosisId: string, payload: DiagnosisWritePayload) => Promise<void>;
  onSetPrimary: (diagnosisId: string) => Promise<void>;
  onRemove: (diagnosisId: string) => Promise<void>;
  onFormDirtyChange: (dirty: boolean) => void;
};

const TERMINAL_STATUSES = ["SIGNED", "CLOSED", "CANCELLED"];

function isDraftDirty(form: DiagnosisDraftForm) {
  return form.label.length > 0 || form.code.length > 0 || form.certainty_note.length > 0 || form.is_primary;
}

function isEditorDirty(editor: DiagnosisEditorForm) {
  if (editor.mode === "promote") return true;
  if (editor.diagnosis_type === "NO_DIAGNOSIS") {
    return editor.no_diagnosis_reason !== editor.initial.no_diagnosis_reason;
  }
  return editor.label !== editor.initial.label ||
    editor.code !== editor.initial.code ||
    editor.certainty_note !== editor.initial.certainty_note ||
    editor.is_primary !== editor.initial.is_primary;
}

function diagnosisTypeLabel(type: DiagnosisType) {
  if (type === "WORKING") return "Working diagnosis";
  if (type === "FINAL") return "Final diagnosis";
  return "No final diagnosis";
}

function diagnosisBadgeTone(type: DiagnosisType): "purple" | "teal" | "neutral" {
  if (type === "WORKING") return "purple";
  if (type === "FINAL") return "teal";
  return "neutral";
}

export function DiagnosisSection({
  status,
  diagnoses,
  canManage,
  mutationPending,
  mutationError,
  formState,
  onFormStateChange,
  onCreate,
  onSaveEdit,
  onSetPrimary,
  onRemove,
  onFormDirtyChange,
}: DiagnosisSectionProps) {
  const [formError, setFormError] = useState("");
  const readOnly = TERMINAL_STATUSES.includes(status);
  const workingDiagnoses = diagnoses.filter((diagnosis) => diagnosis.diagnosis_type === "WORKING");
  const finalDiagnoses = diagnoses.filter((diagnosis) => diagnosis.diagnosis_type === "FINAL");
  const noDiagnoses = diagnoses.filter((diagnosis) => diagnosis.diagnosis_type === "NO_DIAGNOSIS");
  const hasFinal = finalDiagnoses.length > 0;
  const hasNoDiagnosis = noDiagnoses.length > 0;

  function formStateHasUnsavedChanges(state: DiagnosisFormState) {
    return (state.workingOpen && isDraftDirty(state.working)) ||
      (state.finalOpen && isDraftDirty(state.final)) ||
      (state.noDiagnosisOpen && state.noDiagnosisReason.length > 0) ||
      Boolean(state.editor && isEditorDirty(state.editor));
  }

  useEffect(() => {
    onFormDirtyChange(formStateHasUnsavedChanges(formState));
  }, [formState, onFormDirtyChange]);

  function updateFormState(next: DiagnosisFormState) {
    setFormError("");
    onFormStateChange(next);
    onFormDirtyChange(formStateHasUnsavedChanges(next));
  }

  function toggleWorkingForm() {
    updateFormState({ ...formState, workingOpen: !formState.workingOpen });
  }

  function toggleFinalForm() {
    updateFormState({ ...formState, finalOpen: !formState.finalOpen });
  }

  function toggleNoDiagnosisForm() {
    updateFormState({ ...formState, noDiagnosisOpen: !formState.noDiagnosisOpen });
  }

  function cancelWorkingForm() {
    updateFormState({
      ...formState,
      workingOpen: false,
      working: { label: "", code: "", certainty_note: "", is_primary: false },
    });
  }

  function cancelFinalForm() {
    updateFormState({
      ...formState,
      finalOpen: false,
      final: { label: "", code: "", certainty_note: "", is_primary: false },
    });
  }

  function cancelNoDiagnosisForm() {
    updateFormState({ ...formState, noDiagnosisOpen: false, noDiagnosisReason: "" });
  }

  async function submitWorking(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!formState.working.label.trim()) {
      setFormError("Enter the diagnosis.");
      return;
    }
    try {
      await onCreate({
        diagnosis_type: "WORKING",
        label: formState.working.label,
        code: formState.working.code,
        certainty_note: formState.working.certainty_note,
        is_primary: false,
      });
      cancelWorkingForm();
    } catch {
      // The parent owns the authoritative error message and keeps this draft intact.
    }
  }

  async function submitFinal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!formState.final.label.trim()) {
      setFormError("Enter the diagnosis.");
      return;
    }
    try {
      await onCreate({
        diagnosis_type: "FINAL",
        label: formState.final.label,
        code: formState.final.code,
        is_primary: formState.final.is_primary,
      });
      cancelFinalForm();
    } catch {
      // The parent owns the authoritative error message and keeps this draft intact.
    }
  }

  async function submitNoDiagnosis(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!formState.noDiagnosisReason.trim()) {
      setFormError("Enter a reason for recording no final diagnosis.");
      return;
    }
    try {
      await onCreate({
        diagnosis_type: "NO_DIAGNOSIS",
        no_diagnosis_reason: formState.noDiagnosisReason,
      });
      cancelNoDiagnosisForm();
    } catch {
      // The parent owns the authoritative error message and keeps this draft intact.
    }
  }

  function beginEdit(diagnosis: Diagnosis, mode: "edit" | "promote" = "edit") {
    const initial = {
      diagnosis_type: diagnosis.diagnosis_type,
      label: diagnosis.label,
      code: diagnosis.code,
      certainty_note: diagnosis.certainty_note,
      is_primary: diagnosis.is_primary,
      no_diagnosis_reason: diagnosis.no_diagnosis_reason,
    };
    updateFormState({
      ...formState,
      editor: {
        id: diagnosis.id,
        diagnosis_type: mode === "promote" ? "FINAL" : diagnosis.diagnosis_type,
        label: diagnosis.label,
        code: diagnosis.code,
        certainty_note: diagnosis.certainty_note,
        is_primary: mode === "promote" ? false : diagnosis.is_primary,
        no_diagnosis_reason: diagnosis.no_diagnosis_reason,
        mode,
        initial,
      },
    });
  }

  function cancelEditor() {
    updateFormState({ ...formState, editor: null });
  }

  async function submitEditor(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const editor = formState.editor;
    if (!editor) return;
    if (editor.diagnosis_type === "NO_DIAGNOSIS") {
      if (!editor.no_diagnosis_reason.trim()) {
        setFormError("Enter a reason for recording no final diagnosis.");
        return;
      }
    } else if (!editor.label.trim()) {
      setFormError("Enter the diagnosis.");
      return;
    }
    const payload: DiagnosisWritePayload = editor.diagnosis_type === "NO_DIAGNOSIS"
      ? { diagnosis_type: "NO_DIAGNOSIS", no_diagnosis_reason: editor.no_diagnosis_reason }
      : editor.diagnosis_type === "WORKING"
        ? {
            diagnosis_type: "WORKING",
            label: editor.label,
            code: editor.code,
            certainty_note: editor.certainty_note,
            is_primary: false,
          }
        : {
            diagnosis_type: "FINAL",
            label: editor.label,
            code: editor.code,
            is_primary: editor.is_primary,
          };
    try {
      await onSaveEdit(editor.id, payload);
      cancelEditor();
    } catch {
      // The parent owns the authoritative error message and keeps this draft intact.
    }
  }

  async function removeDiagnosis(diagnosis: Diagnosis) {
    if (!window.confirm("Remove this diagnosis from the active encounter record?")) return;
    try {
      await onRemove(diagnosis.id);
      if (formState.editor?.id === diagnosis.id) cancelEditor();
    } catch {
      // The parent owns the authoritative error message.
    }
  }

  function updateWorkingForm(patch: Partial<DiagnosisDraftForm>) {
    updateFormState({ ...formState, working: { ...formState.working, ...patch } });
  }

  function updateFinalForm(patch: Partial<DiagnosisDraftForm>) {
    updateFormState({ ...formState, final: { ...formState.final, ...patch } });
  }

  function updateEditor(patch: Partial<DiagnosisEditorForm>) {
    if (!formState.editor) return;
    updateFormState({ ...formState, editor: { ...formState.editor, ...patch } });
  }

  function renderDiagnosisCard(diagnosis: Diagnosis) {
    const isWorking = diagnosis.diagnosis_type === "WORKING";
    const isFinal = diagnosis.diagnosis_type === "FINAL";
    return (
      <article
        key={diagnosis.id}
        data-testid={`diagnosis-${diagnosis.id}`}
        className="rounded-[14px] border border-line-soft bg-white/80 px-3.5 py-3"
      >
        <div className="flex flex-wrap items-start gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <StatusBadge tone={diagnosisBadgeTone(diagnosis.diagnosis_type)}>
                {diagnosisTypeLabel(diagnosis.diagnosis_type)}
              </StatusBadge>
              {isFinal ? (
                <StatusBadge tone={diagnosis.is_primary ? "teal" : "neutral"}>
                  {diagnosis.is_primary ? "Primary" : "Secondary"}
                </StatusBadge>
              ) : null}
            </div>
            {isWorking || isFinal ? <p className="mt-2 text-[13px] font-bold text-ink">{diagnosis.label}</p> : null}
            {isWorking && diagnosis.certainty_note ? (
              <p className="mt-1 text-[11.5px] font-medium text-secondary">Certainty note: {diagnosis.certainty_note}</p>
            ) : null}
            {diagnosis.code ? <p className="mt-1 text-[11.5px] font-medium text-secondary">Code: {diagnosis.code}</p> : null}
            {diagnosis.diagnosis_type === "NO_DIAGNOSIS" ? (
              <div data-testid="no-diagnosis-state" className="mt-2 rounded-[10px] bg-surface-muted px-3 py-2">
                <p className="text-[12px] font-semibold text-ink">No final diagnosis recorded</p>
                <p className="mt-1 text-[11.5px] font-medium text-secondary">Reason: {diagnosis.no_diagnosis_reason}</p>
              </div>
            ) : null}
          </div>
          {canManage && !readOnly ? (
            <div className="flex flex-wrap justify-end gap-2">
              <Button variant="small-secondary" disabled={mutationPending} onClick={() => beginEdit(diagnosis)}>
                Edit
              </Button>
              {isWorking && !hasNoDiagnosis ? (
                <Button variant="small-secondary" disabled={mutationPending} onClick={() => beginEdit(diagnosis, "promote")}>
                  Promote to final
                </Button>
              ) : null}
              {isFinal && !diagnosis.is_primary ? (
                <Button variant="small-secondary" disabled={mutationPending} onClick={() => void onSetPrimary(diagnosis.id).catch(() => undefined)}>
                  Make primary
                </Button>
              ) : null}
              <Button variant="danger" disabled={mutationPending} onClick={() => void removeDiagnosis(diagnosis)}>
                Remove
              </Button>
            </div>
          ) : null}
        </div>
        {isWorking && hasNoDiagnosis && canManage && !readOnly ? (
          <p className="mt-2 text-[11.5px] font-medium text-muted">Remove the no-final-diagnosis entry before promoting this working diagnosis.</p>
        ) : null}
      </article>
    );
  }

  return (
    <section data-testid="diagnosis-section" aria-label="Diagnosis section" className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-[17px] font-bold text-ink">Diagnosis</h2>
          <p className="mt-1 max-w-2xl text-[12px] font-medium text-secondary">
            Record clinician-authored working and final diagnoses. Codes are optional until the diagnosis catalogue is connected.
          </p>
        </div>
        {readOnly ? <StatusBadge tone="neutral">Read only</StatusBadge> : null}
      </div>

      {readOnly ? (
        <p data-testid="diagnosis-read-only" className="rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">
          This encounter is signed and diagnoses can no longer be changed.
        </p>
      ) : null}
      {mutationPending ? <p role="status" className="text-[11.5px] font-semibold text-accent-orange-text">Saving diagnosis…</p> : null}
      {mutationError ? <p role="alert" className="rounded-[12px] bg-accent-pink-soft px-3 py-2 text-[11.5px] font-semibold text-accent-pink">{mutationError}</p> : null}
      {formError ? <p role="alert" className="rounded-[12px] bg-accent-orange-soft px-3 py-2 text-[11.5px] font-semibold text-accent-orange-text">{formError}</p> : null}

      <section aria-labelledby="working-diagnoses-heading" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 id="working-diagnoses-heading" className="text-[12px] font-bold uppercase tracking-[0.08em] text-secondary">Working diagnoses</h3>
          {canManage && !readOnly ? (
            <Button variant="small-secondary" disabled={mutationPending} onClick={toggleWorkingForm}>
              {formState.workingOpen ? "Close working diagnosis" : "Add working diagnosis"}
            </Button>
          ) : null}
        </div>
        {workingDiagnoses.length === 0 ? <p className="text-[12px] font-medium text-muted">No working diagnoses recorded.</p> : null}
        <div className="grid gap-2">{workingDiagnoses.map((diagnosis) => renderDiagnosisCard(diagnosis))}</div>
        {formState.workingOpen && canManage && !readOnly ? (
          <form data-testid="working-diagnosis-form" className="grid gap-3 rounded-[14px] border border-primary/20 bg-primary-soft/30 p-3" noValidate onSubmit={submitWorking}>
            <Field label="Diagnosis / clinical impression" htmlFor="working-diagnosis-label">
              <TextInput
                id="working-diagnosis-label"
                maxLength={200}
                required
                value={formState.working.label}
                onChange={(event) => updateWorkingForm({ label: event.target.value })}
              />
            </Field>
            <Field label="Code (optional)" htmlFor="working-diagnosis-code" hint="Enter a manual snapshot only; it is not catalogue-validated here.">
              <TextInput
                id="working-diagnosis-code"
                maxLength={40}
                value={formState.working.code}
                onChange={(event) => updateWorkingForm({ code: event.target.value })}
              />
            </Field>
            <Field label="Certainty note (optional)" htmlFor="working-diagnosis-certainty">
              <Textarea
                id="working-diagnosis-certainty"
                className="min-h-[100px]"
                maxLength={4000}
                value={formState.working.certainty_note}
                onChange={(event) => updateWorkingForm({ certainty_note: event.target.value })}
              />
            </Field>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={mutationPending}>Save working diagnosis</Button>
              <Button variant="small-secondary" onClick={cancelWorkingForm}>Cancel</Button>
            </div>
          </form>
        ) : null}
      </section>

      <section aria-labelledby="final-diagnoses-heading" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 id="final-diagnoses-heading" className="text-[12px] font-bold uppercase tracking-[0.08em] text-secondary">Final diagnoses</h3>
          {canManage && !readOnly && !hasNoDiagnosis ? (
            <Button variant="small-secondary" disabled={mutationPending} onClick={toggleFinalForm}>
              {formState.finalOpen ? "Close final diagnosis" : "Add final diagnosis"}
            </Button>
          ) : null}
        </div>
        {finalDiagnoses.length === 0 ? <p className="text-[12px] font-medium text-muted">No final diagnoses recorded.</p> : null}
        <div className="grid gap-2">{finalDiagnoses.map((diagnosis) => renderDiagnosisCard(diagnosis))}</div>
        {hasNoDiagnosis && canManage && !readOnly ? (
          <p className="text-[11.5px] font-medium text-muted">Remove the no-final-diagnosis entry before adding or promoting a final diagnosis.</p>
        ) : null}
        {formState.finalOpen && canManage && !readOnly && !hasNoDiagnosis ? (
          <form data-testid="final-diagnosis-form" className="grid gap-3 rounded-[14px] border border-accent-teal/25 bg-accent-teal-soft/30 p-3" noValidate onSubmit={submitFinal}>
            <Field label="Diagnosis" htmlFor="final-diagnosis-label">
              <TextInput
                id="final-diagnosis-label"
                maxLength={200}
                required
                value={formState.final.label}
                onChange={(event) => updateFinalForm({ label: event.target.value })}
              />
            </Field>
            <Field label="Code (optional)" htmlFor="final-diagnosis-code" hint="Enter a manual snapshot only; it is not catalogue-validated here.">
              <TextInput
                id="final-diagnosis-code"
                maxLength={40}
                value={formState.final.code}
                onChange={(event) => updateFinalForm({ code: event.target.value })}
              />
            </Field>
            <label className="flex items-center gap-2 text-[12px] font-semibold text-secondary">
              <input
                type="checkbox"
                checked={formState.final.is_primary}
                onChange={(event) => updateFinalForm({ is_primary: event.target.checked })}
              />
              Primary diagnosis
            </label>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={mutationPending}>Save final diagnosis</Button>
              <Button variant="small-secondary" onClick={cancelFinalForm}>Cancel</Button>
            </div>
          </form>
        ) : null}
      </section>

      <section aria-labelledby="no-final-diagnosis-heading" className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 id="no-final-diagnosis-heading" className="text-[12px] font-bold uppercase tracking-[0.08em] text-secondary">No final diagnosis</h3>
          {canManage && !readOnly && !hasFinal && !hasNoDiagnosis ? (
            <Button variant="small-secondary" disabled={mutationPending} onClick={toggleNoDiagnosisForm}>
              {formState.noDiagnosisOpen ? "Close no-diagnosis form" : "Record no final diagnosis"}
            </Button>
          ) : null}
        </div>
        {noDiagnoses.length === 0 ? <p className="text-[12px] font-medium text-muted">No explicit no-diagnosis disposition recorded.</p> : null}
        <div className="grid gap-2">{noDiagnoses.map((diagnosis) => renderDiagnosisCard(diagnosis))}</div>
        {hasFinal && canManage && !readOnly ? (
          <p className="text-[11.5px] font-medium text-muted">Remove active final diagnoses before recording no final diagnosis.</p>
        ) : null}
        {formState.noDiagnosisOpen && canManage && !readOnly && !hasFinal && !hasNoDiagnosis ? (
          <form data-testid="no-diagnosis-form" className="grid gap-3 rounded-[14px] border border-line-soft bg-surface-muted p-3" noValidate onSubmit={submitNoDiagnosis}>
            <Field label="Reason" htmlFor="no-diagnosis-reason" hint="Explain why no final diagnosis was reached. Do not leave this blank.">
              <Textarea
                id="no-diagnosis-reason"
                className="min-h-[120px]"
                maxLength={4000}
                required
                value={formState.noDiagnosisReason}
                onChange={(event) => updateFormState({ ...formState, noDiagnosisReason: event.target.value })}
              />
            </Field>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={mutationPending}>Save no final diagnosis</Button>
              <Button variant="small-secondary" onClick={cancelNoDiagnosisForm}>Cancel</Button>
            </div>
          </form>
        ) : null}
      </section>

      {formState.editor && canManage && !readOnly ? (
        <form data-testid="diagnosis-editor" className="grid gap-3 rounded-[14px] border border-primary/30 bg-white p-3 shadow-card" noValidate onSubmit={submitEditor}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-[13px] font-bold text-ink">
              {formState.editor.mode === "promote" ? "Promote working diagnosis to final" : `Edit ${diagnosisTypeLabel(formState.editor.diagnosis_type).toLowerCase()}`}
            </h3>
            <Button variant="small-secondary" onClick={cancelEditor}>Cancel</Button>
          </div>
          {formState.editor.diagnosis_type === "NO_DIAGNOSIS" ? (
            <Field label="Reason" htmlFor="edit-no-diagnosis-reason">
              <Textarea
                id="edit-no-diagnosis-reason"
                className="min-h-[120px]"
                maxLength={4000}
                required
                value={formState.editor.no_diagnosis_reason}
                onChange={(event) => updateEditor({ no_diagnosis_reason: event.target.value })}
              />
            </Field>
          ) : (
            <>
              <Field label={formState.editor.diagnosis_type === "WORKING" ? "Diagnosis / clinical impression" : "Diagnosis"} htmlFor="edit-diagnosis-label">
                <TextInput
                  id="edit-diagnosis-label"
                  maxLength={200}
                  required
                  value={formState.editor.label}
                  onChange={(event) => updateEditor({ label: event.target.value })}
                />
              </Field>
              <Field label="Code (optional)" htmlFor="edit-diagnosis-code" hint="Enter a manual snapshot only; it is not catalogue-validated here.">
                <TextInput
                  id="edit-diagnosis-code"
                  maxLength={40}
                  value={formState.editor.code}
                  onChange={(event) => updateEditor({ code: event.target.value })}
                />
              </Field>
              {formState.editor.diagnosis_type === "WORKING" ? (
                <Field label="Certainty note (optional)" htmlFor="edit-working-certainty">
                  <Textarea
                    id="edit-working-certainty"
                    className="min-h-[100px]"
                    maxLength={4000}
                    value={formState.editor.certainty_note}
                    onChange={(event) => updateEditor({ certainty_note: event.target.value })}
                  />
                </Field>
              ) : (
                <label className="flex items-center gap-2 text-[12px] font-semibold text-secondary">
                  <input
                    type="checkbox"
                    checked={formState.editor.is_primary}
                    onChange={(event) => updateEditor({ is_primary: event.target.checked })}
                  />
                  Primary diagnosis
                </label>
              )}
            </>
          )}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={mutationPending}>
              {formState.editor.mode === "promote" ? "Promote to final" : "Save diagnosis changes"}
            </Button>
          </div>
        </form>
      ) : null}
    </section>
  );
}