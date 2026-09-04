"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest, ApiRequestError, newIdempotencyKey } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import { Department, Patient, PatientRegisterResponse, VisitCheckInResponse } from "../../../features/clinic";
import { IconCheckCircle, IconPatients, IconSearch, IconUserPlus } from "../../../components/icons";
import {
  Button,
  Card,
  CardSkeleton,
  CardTitleBar,
  EmptyState,
  ErrorBanner,
  Field,
  LoadingSkeleton,
  PageHeader,
  Select,
  StatusBadge,
  TextInput,
} from "../../../components/ui";

const SEX_OPTIONS = [
  { value: "NOT_STATED", label: "Not stated" },
  { value: "FEMALE", label: "Female" },
  { value: "MALE", label: "Male" },
  { value: "INTERSEX", label: "Intersex" },
  { value: "UNKNOWN", label: "Unknown" },
];

const DESTINATION_CODE_BY_VISIT_TYPE: Record<string, string> = {
  OUTPATIENT_NEW: "OPD",
  OUTPATIENT_REVIEW: "OPD",
  FOLLOW_UP_RESULTS: "OPD",
  ANC: "ANC",
  LAB_ONLY: "LAB",
  PHARMACY_ONLY: "PHARMACY",
};

function sexLabel(sex: string): string {
  return SEX_OPTIONS.find((option) => option.value === sex)?.label ?? sex;
}

function errorMessage(error: unknown) {
  if (error instanceof Error && error.message.includes("permission")) {
    return "You don't have permission to perform this action.";
  }
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function post<T>(path: string, body: unknown, idempotencyKey?: string) {
  return apiRequest<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : undefined,
  });
}

function ageFromDob(dob: string | null): string | null {
  if (!dob) return null;
  const birth = new Date(dob);
  if (Number.isNaN(birth.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - birth.getFullYear();
  const monthDiff = now.getMonth() - birth.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && now.getDate() < birth.getDate())) age -= 1;
  return age >= 0 ? `${age} yrs` : null;
}

function RadioGroup({
  legend,
  name,
  value,
  options,
  onChange,
}: {
  legend: string;
  name: string;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  return (
    <fieldset className="sm:col-span-2">
      <legend className="mb-2 block text-[12px] font-semibold text-secondary">{legend}</legend>
      <div className="grid gap-2 sm:grid-cols-2" role="radiogroup" aria-label={legend}>
        {options.map((option) => (
          <label
            key={option.value}
            className="flex cursor-pointer items-center gap-2 rounded-[10px] border border-line px-3 py-2 text-[12px] font-medium text-ink has-[:checked]:border-primary has-[:checked]:bg-primary-soft"
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={(event) => onChange(event.target.value)}
              className="h-4 w-4 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function PatientsWorkspace() {
  const { session, can } = useSession();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState(searchParams.get("q") ?? "");
  const [debouncedSearch, setDebouncedSearch] = useState(search);
  const [selected, setSelected] = useState<Patient | null>(null);
  const [departmentId, setDepartmentId] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const registerRef = useRef<HTMLDivElement>(null);

  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [phone, setPhone] = useState("");
  const [sex, setSex] = useState("NOT_STATED");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [estimatedAgeYears, setEstimatedAgeYears] = useState("");
  const [village, setVillage] = useState("");
  const [parish, setParish] = useState("");
  const [subCounty, setSubCounty] = useState("");
  const [district, setDistrict] = useState("");
  const [nextOfKinName, setNextOfKinName] = useState("");
  const [nextOfKinPhone, setNextOfKinPhone] = useState("");
  const [visitType, setVisitType] = useState("OUTPATIENT_NEW");
  const [payerType, setPayerType] = useState("CASH");
  const [duplicateCandidates, setDuplicateCandidates] = useState<Patient[]>([]);
  const [duplicateReason, setDuplicateReason] = useState("");
  const registerIdempotencyKey = useRef<string | null>(null);
  const checkInIdempotencyKey = useRef<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search.trim()), 350);
    return () => clearTimeout(timer);
  }, [search]);

  const patients = useQuery({
    queryKey: ["patients", debouncedSearch],
    queryFn: () => apiRequest<Patient[]>("/api/v1/patients/?q=" + encodeURIComponent(debouncedSearch)),
    enabled: can("patient.view"),
  });
  const departments = useQuery({
    queryKey: ["departments"],
    queryFn: async () => (await apiRequest<{ departments: Department[] }>("/api/v1/tenancy/departments/")).departments,
  });
  const defaultDepartment = useMemo(() => {
    const preferredCode = DESTINATION_CODE_BY_VISIT_TYPE[visitType];
    return (
      departments.data?.find((department) => department.code.toUpperCase() === preferredCode) ??
      departments.data?.[0]
    );
  }, [departments.data, visitType]);

  const createPatient = useMutation({
    mutationFn: (resolution?: Record<string, unknown>) =>
      post<PatientRegisterResponse>(
        "/api/v1/reception/patients/register/",
        {
          first_name: firstName,
          last_name: lastName,
          phone,
          sex,
          date_of_birth: dateOfBirth || null,
          estimated_age_years: estimatedAgeYears ? Number(estimatedAgeYears) : null,
          dob_estimated: !dateOfBirth && Boolean(estimatedAgeYears),
          village,
          parish,
          sub_county: subCounty,
          district,
          next_of_kin_name: nextOfKinName,
          next_of_kin_phone: nextOfKinPhone,
          ...(resolution ? { duplicate_resolution: resolution } : {}),
        },
        registerIdempotencyKey.current ?? (registerIdempotencyKey.current = newIdempotencyKey("patient-register")),
      ),
    onSuccess: (result) => {
      if (result.duplicate_candidates?.length) {
        registerIdempotencyKey.current = null;
        setDuplicateCandidates(result.duplicate_candidates);
        setNotice("Possible duplicate patient found. Review the match before creating a new record.");
        setError("");
        return;
      }
      const patient = result.patient ?? result;
      registerIdempotencyKey.current = null;
      setSelected(patient);
      setNotice(`${patient.display_name} registered as ${patient.patient_no}.`);
      setError("");
      setDuplicateCandidates([]);
      setDuplicateReason("");
      setFirstName("");
      setLastName("");
      setPhone("");
      setDateOfBirth("");
      setEstimatedAgeYears("");
      setVillage("");
      setParish("");
      setSubCounty("");
      setDistrict("");
      setNextOfKinName("");
      setNextOfKinPhone("");
      queryClient.invalidateQueries({ queryKey: ["patients"] });
    },
    onError: (reason) => {
      if (reason instanceof ApiRequestError && reason.status >= 400 && reason.status < 500 && reason.status !== 409) {
        registerIdempotencyKey.current = null;
      }
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  const checkIn = useMutation({
    mutationFn: () =>
      post<VisitCheckInResponse>("/api/v1/reception/visits/check-in/", {
        patient_id: selected?.id,
        department_id: departmentId || defaultDepartment?.id,
        visit_type: visitType,
        payer_type: payerType,
      }, checkInIdempotencyKey.current ?? (checkInIdempotencyKey.current = newIdempotencyKey("visit-check-in"))),
    onSuccess: (result) => {
      checkInIdempotencyKey.current = null;
      const label = result.queue?.queue_label;
      setNotice(`${selected?.display_name ?? "Patient"} checked in${label ? ` as ${label}` : ""}.`);
      setError("");
      queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
    onError: (reason) => {
      if (reason instanceof ApiRequestError && reason.status >= 400 && reason.status < 500 && reason.status !== 409) {
        checkInIdempotencyKey.current = null;
      }
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  const results = useMemo(() => patients.data ?? [], [patients.data]);

  return (
    <>
      <PageHeader
        title="Patients"
        subtitle="Search the registry, register a new patient, and start the visit."
        actions={
          can("patient.create") ? (
            <Button
              onClick={() => registerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
            >
              <IconUserPlus className="h-4 w-4" />
              Register patient
            </Button>
          ) : undefined
        }
      />

      <section className="grid grid-cols-1 xl:grid-cols-[1.55fr_1fr] gap-5 items-start">
        <div className="space-y-5">
          <Card>
            <div className="px-5 pt-5 pb-4">
              <Field label="Search by name, phone, or patient number" htmlFor="patient-search">
                <div className="relative">
                  <IconSearch className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-muted" />
                  <TextInput
                    id="patient-search"
                    className="pl-11"
                    placeholder="Try a name, phone, or P-…"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    autoComplete="off"
                  />
                </div>
              </Field>
            </div>

            {notice ? (
              <div className="px-5 pb-3">
                <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">
                  <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
                  {notice}
                </p>
              </div>
            ) : null}
            {error ? (
              <div className="px-5 pb-3">
                <ErrorBanner message={error} onDismiss={() => setError("")} />
              </div>
            ) : null}

            {patients.isLoading ? (
              <div className="px-5 pb-5 space-y-4" aria-busy="true" aria-label="Loading patients">
                {Array.from({ length: 4 }).map((_, index) => (
                  <div key={index} className="flex items-center gap-3">
                    <LoadingSkeleton className="h-9 w-9 rounded-full" />
                    <div className="flex-1 space-y-2">
                      <LoadingSkeleton className="h-3 w-2/5" />
                      <LoadingSkeleton className="h-2.5 w-1/4" />
                    </div>
                    <LoadingSkeleton className="h-8 w-16 rounded-[10px]" />
                  </div>
                ))}
              </div>
            ) : patients.isError ? (
              <EmptyState
                icon={<IconPatients className="h-5 w-5" />}
                title="Patients could not be loaded."
                hint="Check your connection and try again."
                action={<Button variant="secondary" onClick={() => patients.refetch()}>Retry</Button>}
              />
            ) : results.length === 0 ? (
              <EmptyState
                icon={<IconPatients className="h-5 w-5" />}
                title={debouncedSearch ? "No patients match this search." : "No patients are registered yet."}
                hint={
                  debouncedSearch
                    ? "Try a different name, phone number, or patient number."
                    : "Register the first patient to start the registry."
                }
              />
            ) : (
              <>
                <ul className="px-5 pb-2 divide-y divide-line-soft">
                  {results.slice(0, 8).map((patient) => {
                    const active = selected?.id === patient.id;
                    return (
                      <li key={patient.id} className="flex items-center gap-3 py-3">
                        <div className="flex-1 min-w-0 leading-tight">
                          <div className="text-[13px] font-semibold text-ink">{patient.display_name}</div>
                          <div className="mt-0.5 text-[11.5px] font-medium text-muted">
                            {patient.patient_no}
                            <span className="mx-0.5">•</span>
                            {sexLabel(patient.sex)}
                            {patient.phone ? (
                              <>
                                <span className="mx-0.5">•</span>
                                {patient.phone}
                              </>
                            ) : null}
                          </div>
                        </div>
                        <Button
                          variant="small-secondary"
                          aria-pressed={active}
                          className={active ? "bg-primary-soft text-primary-text border-primary-soft" : ""}
                          onClick={() => {
                            setSelected(patient);
                            setNotice("");
                          }}
                        >
                          {active ? "Selected" : "Select"}
                        </Button>
                      </li>
                    );
                  })}
                </ul>
                {results.length > 8 ? (
                  <p className="px-5 pb-5 text-[11.5px] font-medium text-muted">
                    Showing 8 of {results.length} matches. Refine the search to narrow results.
                  </p>
                ) : null}
              </>
            )}
          </Card>

          {can("patient.create") ? (
            <Card>
              <div ref={registerRef} className="scroll-mt-24" />
              <CardTitleBar title="Register patient" />
              <form
                className="px-5 py-5 grid gap-4 sm:grid-cols-2"
                onSubmit={(event: FormEvent) => {
                  event.preventDefault();
                  setNotice("");
                  setError("");
                  createPatient.mutate(undefined);
                }}
              >
                <Field label="First name" htmlFor="first-name">
                  <TextInput id="first-name" required value={firstName} onChange={(event) => setFirstName(event.target.value)} />
                </Field>
                <Field label="Last name" htmlFor="last-name">
                  <TextInput id="last-name" required value={lastName} onChange={(event) => setLastName(event.target.value)} />
                </Field>
                <Field label="Phone" htmlFor="phone">
                  <TextInput id="phone" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="07…" />
                </Field>
                <Field label="Sex" htmlFor="sex">
                  <Select id="sex" value={sex} onChange={(event) => setSex(event.target.value)}>
                    {SEX_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Date of birth" htmlFor="date-of-birth">
                  <TextInput
                    id="date-of-birth"
                    type="date"
                    value={dateOfBirth}
                    onChange={(event) => setDateOfBirth(event.target.value)}
                    disabled={Boolean(estimatedAgeYears)}
                  />
                </Field>
                <Field label="Estimated age (years)" htmlFor="estimated-age-years">
                  <TextInput
                    id="estimated-age-years"
                    type="number"
                    min="0"
                    max="150"
                    value={estimatedAgeYears}
                    onChange={(event) => setEstimatedAgeYears(event.target.value)}
                    disabled={Boolean(dateOfBirth)}
                    placeholder="If DOB is unknown"
                  />
                </Field>
                <Field label="Village" htmlFor="village">
                  <TextInput id="village" value={village} onChange={(event) => setVillage(event.target.value)} />
                </Field>
                <Field label="Parish" htmlFor="parish">
                  <TextInput id="parish" value={parish} onChange={(event) => setParish(event.target.value)} />
                </Field>
                <Field label="Sub-county" htmlFor="sub-county">
                  <TextInput id="sub-county" value={subCounty} onChange={(event) => setSubCounty(event.target.value)} />
                </Field>
                <Field label="District" htmlFor="district">
                  <TextInput id="district" value={district} onChange={(event) => setDistrict(event.target.value)} />
                </Field>
                <Field label="Next of kin name" htmlFor="next-of-kin-name">
                  <TextInput id="next-of-kin-name" value={nextOfKinName} onChange={(event) => setNextOfKinName(event.target.value)} />
                </Field>
                <Field label="Next of kin phone" htmlFor="next-of-kin-phone">
                  <TextInput id="next-of-kin-phone" value={nextOfKinPhone} onChange={(event) => setNextOfKinPhone(event.target.value)} />
                </Field>
                {duplicateCandidates.length > 0 ? (
                  <div className="sm:col-span-2 rounded-[14px] border border-line-soft bg-surface-muted px-4 py-3" role="status">
                    <p className="text-[12px] font-semibold text-ink">Possible duplicate</p>
                    <ul className="mt-2 space-y-1 text-[11.5px] text-muted">
                      {duplicateCandidates.map((candidate) => (
                        <li key={candidate.id} className="flex items-center justify-between gap-3">
                          <span>
                            {candidate.display_name} · {candidate.patient_no}
                            {candidate.last_seen_at ? ` · last seen ${new Date(candidate.last_seen_at).toLocaleDateString()}` : ""}
                          </span>
                          <Button
                            type="button"
                            variant="small-secondary"
                            onClick={() => {
                              setSelected(candidate);
                              setDuplicateCandidates([]);
                              setDuplicateReason("");
                              setNotice(`${candidate.display_name} selected. Continue with check-in.`);
                            }}
                          >
                            Use this patient
                          </Button>
                        </li>
                      ))}
                    </ul>
                    <Field label="Reason this is not the same patient" htmlFor="duplicate-reason">
                      <TextInput
                        id="duplicate-reason"
                        value={duplicateReason}
                        onChange={(event) => setDuplicateReason(event.target.value)}
                        required
                      />
                    </Field>
                    <Button
                      type="button"
                      className="mt-3"
                      variant="secondary"
                      disabled={createPatient.isPending || duplicateReason.trim().length < 3}
                      onClick={() =>
                        createPatient.mutate({
                          decision: "NOT_THE_SAME",
                          reason: duplicateReason.trim(),
                          rejected_candidate_ids: duplicateCandidates.map((candidate) => candidate.id),
                        })
                      }
                    >
                      Not the same — create new
                    </Button>
                  </div>
                ) : null}
                <div className="sm:col-span-2">
                  <Button type="submit" disabled={createPatient.isPending}>
                    {createPatient.isPending ? "Registering…" : "Register patient"}
                  </Button>
                </div>
              </form>
            </Card>
          ) : null}
        </div>

        <Card className="xl:sticky xl:top-[92px]">
          <CardTitleBar title="Selected patient" />
          {selected ? (
            <div className="px-5 py-5 space-y-5">
              <div className="flex items-start gap-3">
                <span className="h-11 w-11 shrink-0 rounded-full bg-primary-soft grid place-items-center text-[14px] font-bold text-primary-text">
                  {selected.display_name.slice(0, 1).toUpperCase()}
                </span>
                <div className="leading-tight">
                  <p className="text-[15px] font-bold text-ink">{selected.display_name}</p>
                  <p className="mt-1 text-[12px] font-medium text-muted">
                    {selected.patient_no}
                    <span className="mx-0.5">•</span>
                    {sexLabel(selected.sex)}
                    {ageFromDob(selected.date_of_birth) ? (
                      <>
                        <span className="mx-0.5">•</span>
                        {ageFromDob(selected.date_of_birth)}
                      </>
                    ) : null}
                  </p>
                  {selected.phone ? <p className="mt-0.5 text-[12px] font-medium text-muted">{selected.phone}</p> : null}
                </div>
              </div>

              {can("visit.create") ? (
                <div className="border-t border-line-soft pt-5 grid gap-4">
                  <RadioGroup
                    legend="Visit type"
                    name="visit-type"
                    value={visitType}
                    onChange={setVisitType}
                    options={[
                      { value: "OUTPATIENT_NEW", label: "Outpatient — new" },
                      { value: "OUTPATIENT_REVIEW", label: "Outpatient — review" },
                      { value: "ANC", label: "ANC" },
                      { value: "LAB_ONLY", label: "Lab only" },
                      { value: "PHARMACY_ONLY", label: "Pharmacy only" },
                      { value: "FOLLOW_UP_RESULTS", label: "Follow-up results" },
                    ]}
                  />
                  <RadioGroup
                    legend="Payer"
                    name="payer-type"
                    value={payerType}
                    onChange={setPayerType}
                    options={[
                      { value: "CASH", label: "Cash" },
                      { value: "SELF_PAY_MOMO", label: "Self-pay mobile money" },
                    ]}
                  />
                  {departments.isLoading ? (
                    <LoadingSkeleton className="h-11 w-full" />
                  ) : departments.isError ? (
                    <ErrorBanner message="Destinations could not be loaded. Retry the page to continue." />
                  ) : departments.data?.length ? (
                    <Field label="Check-in department" htmlFor="department">
                      <Select
                        id="department"
                        value={departmentId || defaultDepartment?.id || ""}
                        onChange={(event) => setDepartmentId(event.target.value)}
                      >
                        {departments.data.map((department) => (
                          <option key={department.id} value={department.id}>
                            {department.name}
                          </option>
                        ))}
                      </Select>
                    </Field>
                  ) : (
                    <p className="rounded-[12px] bg-surface-muted px-3 py-2 text-[12px] font-medium text-muted" role="status">
                      No active destination is configured for this facility.
                    </p>
                  )}
                  <Button
                    disabled={checkIn.isPending || departments.isLoading || !departments.data?.length}
                    onClick={() => checkIn.mutate()}
                  >
                    {checkIn.isPending ? "Checking in…" : "Check in patient"}
                  </Button>
                  <p className="text-[11.5px] font-medium text-muted">
                    {visitType === "LAB_ONLY"
                      ? "Check-in starts the lab request/intake step."
                      : "Check-in adds the patient to today&apos;s queue."}{" "}
                    <Link href="/queue" className="font-semibold text-primary-text hover:text-primary-strong">
                      View queue
                    </Link>
                  </p>
                </div>
              ) : (
                <StatusBadge tone="neutral">View-only access</StatusBadge>
              )}
            </div>
          ) : (
            <EmptyState
              icon={<IconPatients className="h-5 w-5" />}
              title="No patient selected."
              hint="Search and select a patient to see their identity and start the visit."
            />
          )}
        </Card>
      </section>
    </>
  );
}

export default function PatientsPage() {
  return (
    <Suspense
      fallback={
        <CardSkeleton rows={4} />
      }
    >
      <PatientsWorkspace />
    </Suspense>
  );
}
