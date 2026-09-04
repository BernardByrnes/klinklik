"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest, ApiRequestError, newIdempotencyKey } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import {
  ArrivalEnquiryResponse,
  Department,
  DepartmentEnvelope,
  Patient,
  PatientCheckInSummary,
  PatientDuplicateCandidate,
  PatientRegisterResponse,
  VisitCancelErrorResponse,
  VisitCheckInResponse,
  VisitContextResponse,
} from "../../../features/clinic";
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
  Textarea,
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

function sexLabel(sex: string | null | undefined): string {
  return SEX_OPTIONS.find((option) => option.value === sex)?.label ?? sex ?? "Not stated";
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

function ageFromDob(dob: string | null | undefined): string | null {
  if (!dob) return null;
  const birth = new Date(dob);
  if (Number.isNaN(birth.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - birth.getFullYear();
  const monthDiff = now.getMonth() - birth.getMonth();
  if (monthDiff < 0 || (monthDiff === 0 && now.getDate() < birth.getDate())) age -= 1;
  return age >= 0 ? `${age} yrs` : null;
}

function formatMoney(value: string | number | null | undefined, currency: string): string {
  const amount = Number(value ?? 0);
  if (!Number.isFinite(amount)) return `${currency} —`;
  return `${currency} ${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

const ENQUIRY_REASON_OPTIONS = [
  { value: "NO_CLINICIAN", label: "No clinician available" },
  { value: "SERVICE_UNAVAILABLE", label: "Service unavailable" },
  { value: "PRICE", label: "Price" },
  { value: "REFERRED_OUT", label: "Referred out" },
  { value: "OTHER", label: "Other" },
];

type FailedAction = "register" | "check-in" | "enquiry" | "cancel" | null;

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
  const [duplicateCandidates, setDuplicateCandidates] = useState<PatientDuplicateCandidate[]>([]);
  const [duplicateReason, setDuplicateReason] = useState("");
  const [arrivalEnquiryId, setArrivalEnquiryId] = useState<string | null>(null);
  const [arrivalEnquiryVersion, setArrivalEnquiryVersion] = useState<number | null>(null);
  const [enquiryReason, setEnquiryReason] = useState("NO_CLINICIAN");
  const [enquiryNotes, setEnquiryNotes] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [lastCheckIn, setLastCheckIn] = useState<VisitCheckInResponse | null>(null);
  const [cancelledVisit, setCancelledVisit] = useState<VisitCancelErrorResponse["visit"] | null>(null);
  const [contextVisitId, setContextVisitId] = useState<string | null>(null);
  const [failedAction, setFailedAction] = useState<FailedAction>(null);
  const [candidateLoadingId, setCandidateLoadingId] = useState<string | null>(null);
  const [clockMs, setClockMs] = useState<number | null>(null);
  const registerIdempotencyKey = useRef<string | null>(null);
  const checkInIdempotencyKey = useRef<string | null>(null);
  const enquiryIdempotencyKey = useRef<string | null>(null);
  const enquirySourceEventId = useRef<string | null>(null);
  const cancelIdempotencyKey = useRef<string | null>(null);
  const retryActions = useRef<Partial<Record<Exclude<FailedAction, null>, () => void>>>({});

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
    queryFn: async () => (await apiRequest<DepartmentEnvelope>("/api/v1/tenancy/departments/")).departments,
  });
  const defaultDepartment = useMemo(() => {
    const preferredCode = DESTINATION_CODE_BY_VISIT_TYPE[visitType];
    return (
      departments.data?.find((department) => department.code.toUpperCase() === preferredCode) ??
      departments.data?.[0]
    );
  }, [departments.data, visitType]);

  const patientSummary = useQuery<PatientCheckInSummary>({
    queryKey: ["patient-check-in-summary", selected?.id],
    queryFn: () => apiRequest<PatientCheckInSummary>(`/api/v1/reception/patients/${selected?.id}/check-in-summary/`),
    enabled: Boolean(selected) && can("visit.read"),
  });
  const visitContext = useQuery<VisitContextResponse>({
    queryKey: ["visit-context", contextVisitId],
    queryFn: () => apiRequest<VisitContextResponse>(`/api/v1/reception/visits/${contextVisitId}/context/`),
    enabled: Boolean(contextVisitId) && can("visit.read"),
  });

  const activeVisit = lastCheckIn?.visit ?? patientSummary.data?.active_visit ?? null;
  const openVisit = activeVisit && activeVisit.id !== cancelledVisit?.id ? activeVisit : null;
  useEffect(() => {
    if (!openVisit) {
      setClockMs(null);
      return;
    }
    const tick = () => setClockMs(Date.now());
    tick();
    const timer = setInterval(tick, 1000);
    return () => clearInterval(timer);
  }, [openVisit?.id, openVisit?.opened_at]);
  const openedAtMs = openVisit ? new Date(openVisit.opened_at).getTime() : Number.NaN;
  const remainingGraceSeconds =
    openVisit && clockMs !== null && Number.isFinite(openedAtMs)
      ? Math.max(0, 15 * 60 - Math.floor((clockMs - openedAtMs) / 1000))
      : null;
  const graceExpired = remainingGraceSeconds !== null && remainingGraceSeconds <= 0;
  const currency = session?.organisation.default_currency ?? "UGX";

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
        setFailedAction(null);
        setDuplicateCandidates(result.duplicate_candidates);
        setNotice("Possible duplicate patient found. Review the match before creating a new record.");
        setError("");
        return;
      }
      const patient = result.patient ?? result;
      registerIdempotencyKey.current = null;
      setFailedAction(null);
      setSelected(patient);
      setLastCheckIn(null);
      setCancelledVisit(null);
      setContextVisitId(null);
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
      setFailedAction("register");
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
        ...(arrivalEnquiryId
          ? {
              arrival_enquiry_id: arrivalEnquiryId,
              ...(arrivalEnquiryVersion ? { arrival_enquiry_version: arrivalEnquiryVersion } : {}),
            }
          : {}),
      }, checkInIdempotencyKey.current ?? (checkInIdempotencyKey.current = newIdempotencyKey("visit-check-in"))),
    onSuccess: (result) => {
      checkInIdempotencyKey.current = null;
      setFailedAction(null);
      setLastCheckIn(result);
      setCancelledVisit(null);
      setContextVisitId(result.visit_id);
      setArrivalEnquiryId(null);
      setArrivalEnquiryVersion(null);
      const label = result.queue?.queue_label;
      const invoice = result.invoice?.invoice_no ? ` · invoice ${result.invoice.invoice_no}` : "";
      setNotice(`${selected?.display_name ?? "Patient"} checked in${label ? ` as ${label}` : ""}${invoice}.`);
      setError("");
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["patient-check-in-summary", selected?.id] });
      queryClient.invalidateQueries({ queryKey: ["visit-context", result.visit_id] });
    },
    onError: (reason) => {
      if (reason instanceof ApiRequestError && reason.status >= 400 && reason.status < 500 && reason.status !== 409) {
        checkInIdempotencyKey.current = null;
      }
      setNotice("");
      setFailedAction("check-in");
      if (reason instanceof ApiRequestError && reason.status === 409) {
        const data = reason.data;
        if (data && typeof data === "object" && "visit_id" in data && typeof data.visit_id === "string") {
          setContextVisitId(data.visit_id);
        }
      }
      setError(errorMessage(reason));
    },
  });

  const recordEnquiry = useMutation({
    mutationFn: () =>
      post<ArrivalEnquiryResponse>(
        "/api/v1/reception/arrival-enquiries/",
        {
          reason_code: enquiryReason,
          source_event_id:
            enquirySourceEventId.current ??
            (enquirySourceEventId.current = newIdempotencyKey("arrival-enquiry-event")),
          safe_notes: enquiryNotes.trim(),
        },
        enquiryIdempotencyKey.current ??
          (enquiryIdempotencyKey.current = newIdempotencyKey("arrival-enquiry")),
      ),
    onSuccess: (result) => {
      enquiryIdempotencyKey.current = null;
      enquirySourceEventId.current = null;
      setArrivalEnquiryId(result.enquiry_id);
      setArrivalEnquiryVersion(result.enquiry?.version ?? null);
      setFailedAction(null);
      setNotice("Arrival enquiry recorded. It will be linked atomically to the next check-in.");
      setError("");
      setEnquiryNotes("");
    },
    onError: (reason) => {
      if (reason instanceof ApiRequestError && reason.status >= 400 && reason.status < 500 && reason.status !== 409) {
        enquiryIdempotencyKey.current = null;
        enquirySourceEventId.current = null;
      }
      setNotice("");
      setFailedAction("enquiry");
      setError(errorMessage(reason));
    },
  });

  const cancelVisit = useMutation({
    mutationFn: () => {
      if (!openVisit) throw new Error("There is no open Visit to cancel.");
      return post<VisitCancelErrorResponse>(
        `/api/v1/reception/visits/${openVisit.id}/cancel-error/`,
        { reason: cancelReason.trim(), expected_version: openVisit.version },
        cancelIdempotencyKey.current ??
          (cancelIdempotencyKey.current = newIdempotencyKey("visit-cancel-error")),
      );
    },
    onSuccess: (result) => {
      cancelIdempotencyKey.current = null;
      setFailedAction(null);
      setCancelledVisit(result.visit);
      setLastCheckIn(null);
      setContextVisitId(result.visit_id);
      setCancelReason("");
      setNotice("Erroneous check-in cancelled. The Visit and any invoice history were retained.");
      setError("");
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["patient-check-in-summary", selected?.id] });
      queryClient.invalidateQueries({ queryKey: ["visit-context", result.visit_id] });
    },
    onError: (reason) => {
      if (reason instanceof ApiRequestError && reason.status >= 400 && reason.status < 500 && reason.status !== 409) {
        cancelIdempotencyKey.current = null;
      }
      setNotice("");
      setFailedAction("cancel");
      setError(errorMessage(reason));
    },
  });

  const submitRegistration = (resolution?: Record<string, unknown>) => {
    setFailedAction(null);
    retryActions.current.register = () => createPatient.mutate(resolution);
    createPatient.mutate(resolution);
  };
  const submitCheckIn = () => {
    setFailedAction(null);
    retryActions.current["check-in"] = () => checkIn.mutate();
    checkIn.mutate();
  };
  const submitEnquiry = () => {
    setFailedAction(null);
    retryActions.current.enquiry = () => recordEnquiry.mutate();
    recordEnquiry.mutate();
  };
  const submitCancellation = () => {
    setFailedAction(null);
    retryActions.current.cancel = () => cancelVisit.mutate();
    cancelVisit.mutate();
  };
  const retryFailedAction = () => {
    setError("");
    if (failedAction) retryActions.current[failedAction]?.();
  };

  const selectDuplicateCandidate = async (candidate: PatientDuplicateCandidate) => {
    setCandidateLoadingId(candidate.id);
    setError("");
    try {
      const patient = await apiRequest<Patient>(`/api/v1/patients/${candidate.id}/`);
      setSelected(patient);
      setLastCheckIn(null);
      setCancelledVisit(null);
      setContextVisitId(null);
      setDuplicateCandidates([]);
      setDuplicateReason("");
      setNotice(`${patient.display_name} selected. Continue with check-in.`);
    } catch (reason) {
      setError(errorMessage(reason));
    } finally {
      setCandidateLoadingId(null);
    }
  };

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
                <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink" role="status" aria-live="polite">
                  <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
                  {notice}
                </p>
              </div>
            ) : null}
            {error ? (
              <div className="px-5 pb-3 space-y-2">
                <ErrorBanner
                  message={error}
                  onDismiss={() => {
                    setError("");
                    setFailedAction(null);
                  }}
                />
                {failedAction ? (
                  <Button variant="link" onClick={retryFailedAction}>
                    Retry the last action
                  </Button>
                ) : null}
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
                            setLastCheckIn(null);
                            setCancelledVisit(null);
                            setContextVisitId(null);
                            setNotice("");
                            setError("");
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
                  submitRegistration();
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
                            disabled={candidateLoadingId === candidate.id}
                            onClick={() => void selectDuplicateCandidate(candidate)}
                          >
                            {candidateLoadingId === candidate.id ? "Loading…" : "Use this patient"}
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
                        submitRegistration({
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

          {can("visit.create") ? (
            <Card>
              <CardTitleBar title="Record an arrival enquiry" />
              <form
                className="px-5 py-5 grid gap-4"
                onSubmit={(event: FormEvent) => {
                  event.preventDefault();
                  setNotice("");
                  setError("");
                  submitEnquiry();
                }}
              >
                <p className="text-[12px] font-medium leading-relaxed text-muted">
                  Record a walk-in who was not checked in. The enquiry carries only an operational reason and safe notes.
                </p>
                <Field label="Reason" htmlFor="enquiry-reason">
                  <Select id="enquiry-reason" value={enquiryReason} onChange={(event) => setEnquiryReason(event.target.value)}>
                    {ENQUIRY_REASON_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label="Safe notes (optional)" htmlFor="enquiry-notes" hint="Do not enter diagnoses or other clinical details.">
                  <Textarea
                    id="enquiry-notes"
                    value={enquiryNotes}
                    maxLength={1000}
                    onChange={(event) => setEnquiryNotes(event.target.value)}
                    placeholder="Operational context only"
                  />
                </Field>
                {arrivalEnquiryId ? (
                  <div className="rounded-[12px] bg-accent-teal-soft px-3 py-2 text-[12px] font-medium text-ink" role="status">
                    Enquiry recorded and ready to link to the next check-in.
                    <button
                      type="button"
                      className="ml-2 font-semibold text-primary-text underline underline-offset-2"
                      onClick={() => {
                        setArrivalEnquiryId(null);
                        setArrivalEnquiryVersion(null);
                      }}
                    >
                      Clear link
                    </button>
                  </div>
                ) : null}
                <Button type="submit" disabled={recordEnquiry.isPending}>
                  {recordEnquiry.isPending ? "Recording…" : "Record enquiry"}
                </Button>
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

              {patientSummary.isLoading ? (
                <div className="rounded-[12px] bg-surface-muted px-3 py-3" aria-busy="true" aria-label="Loading check-in summary">
                  <LoadingSkeleton className="h-3 w-2/3" />
                  <LoadingSkeleton className="mt-2 h-3 w-1/2" />
                </div>
              ) : patientSummary.isError ? (
                <div className="space-y-2">
                  <ErrorBanner message="The patient's visit and balance summary could not be loaded." />
                  <Button variant="link" onClick={() => patientSummary.refetch()}>
                    Retry patient summary
                  </Button>
                </div>
              ) : null}

              {patientSummary.data && Number(patientSummary.data.outstanding_balance) > 0 ? (
                <div className="rounded-[14px] border border-accent-orange/30 bg-accent-orange-soft px-4 py-3" role="status">
                  <p className="text-[12px] font-semibold text-accent-orange-text">Outstanding balance warning</p>
                  <p className="mt-1 text-[12px] font-medium leading-relaxed text-ink">
                    {formatMoney(patientSummary.data.outstanding_balance, currency)} remains from a prior visit. Care may proceed.
                    {patientSummary.data.outstanding_invoice_no ? ` Invoice ${patientSummary.data.outstanding_invoice_no}.` : ""}
                  </p>
                  {patientSummary.data.outstanding_visit_id ? (
                    <Button
                      variant="link"
                      className="mt-2"
                      onClick={() => setContextVisitId(patientSummary.data?.outstanding_visit_id ?? null)}
                    >
                      View prior visit
                    </Button>
                  ) : null}
                </div>
              ) : null}

              {openVisit ? (
                <div className="rounded-[14px] border border-primary-soft bg-primary-soft px-4 py-3" role="status">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-[12px] font-semibold text-primary-text">Open visit already exists today</p>
                    <StatusBadge tone="purple">{openVisit.state}</StatusBadge>
                  </div>
                  <p className="mt-1 text-[12px] font-medium leading-relaxed text-ink">
                    {openVisit.visit_type.replaceAll("_", " ")} · {openVisit.local_service_date}
                    {patientSummary.data?.active_queue_label ? ` · queue ${patientSummary.data.active_queue_label}` : ""}
                  </p>
                  <Button variant="link" className="mt-2" onClick={() => setContextVisitId(openVisit.id)}>
                    View existing visit
                  </Button>
                </div>
              ) : null}

              {cancelledVisit ? (
                <div className="rounded-[14px] border border-line-soft bg-surface-muted px-4 py-3" role="status">
                  <p className="text-[12px] font-semibold text-ink">Check-in cancelled in error</p>
                  <p className="mt-1 text-[12px] font-medium text-muted">
                    The cancelled Visit remains retained as {cancelledVisit.id}. You may check in again if needed.
                  </p>
                  <Button variant="link" className="mt-2" onClick={() => setContextVisitId(cancelledVisit.id)}>
                    View cancelled visit context
                  </Button>
                </div>
              ) : null}

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
                    <div className="space-y-2">
                      <ErrorBanner message="Destinations could not be loaded. Retry to continue." />
                      <Button variant="link" onClick={() => departments.refetch()}>
                        Retry destinations
                      </Button>
                    </div>
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
                    disabled={
                      checkIn.isPending ||
                      departments.isLoading ||
                      !departments.data?.length ||
                      Boolean(openVisit)
                    }
                    onClick={submitCheckIn}
                  >
                    {checkIn.isPending ? "Checking in…" : "Check in patient"}
                  </Button>
                  <p className="text-[11.5px] font-medium text-muted">
                    {visitType === "LAB_ONLY"
                      ? "Check-in starts the lab request/intake step."
                      : "Check-in adds the patient to today's queue."}{" "}
                    <Link href="/queue" className="font-semibold text-primary-text hover:text-primary-strong">
                      View queue
                    </Link>
                  </p>
                  {arrivalEnquiryId ? (
                    <p className="rounded-[12px] bg-accent-teal-soft px-3 py-2 text-[11.5px] font-medium text-ink" role="status">
                      This check-in will convert the recorded arrival enquiry atomically.
                    </p>
                  ) : null}
                </div>
              ) : (
                <StatusBadge tone="neutral">View-only access</StatusBadge>
              )}

              {openVisit && can("visit.cancel_error") ? (
                <div className="border-t border-line-soft pt-5 grid gap-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-[12.5px] font-semibold text-ink">Cancel an erroneous check-in</p>
                    <StatusBadge tone={graceExpired ? "neutral" : "amber"}>
                      {remainingGraceSeconds === null
                        ? "Calculating grace time…"
                        : graceExpired
                          ? "Grace window expired"
                          : `${Math.ceil(remainingGraceSeconds / 60)} min remaining`}
                    </StatusBadge>
                  </div>
                  <div>
                    <p className="mt-1 text-[11.5px] font-medium leading-relaxed text-muted">
                      Available only before service starts and within the server-enforced 15-minute grace window. This retains the Visit and voids only its unpaid invoice.
                    </p>
                  </div>
                  <Field label="Cancellation reason" htmlFor="cancel-reason">
                    <Textarea
                      id="cancel-reason"
                      value={cancelReason}
                      minLength={3}
                      maxLength={120}
                      required
                      onChange={(event) => setCancelReason(event.target.value)}
                      placeholder="For example: wrong patient selected"
                    />
                  </Field>
                  <Button
                    variant="danger"
                    disabled={
                      cancelVisit.isPending ||
                      cancelReason.trim().length < 3 ||
                      remainingGraceSeconds === null ||
                      graceExpired
                    }
                    onClick={submitCancellation}
                  >
                    {cancelVisit.isPending ? "Cancelling…" : "Cancel erroneous check-in"}
                  </Button>
                </div>
              ) : null}

              {contextVisitId ? (
                <div className="border-t border-line-soft pt-5" aria-live="polite">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-[12.5px] font-semibold text-ink">Visit context</p>
                    <Button variant="link" onClick={() => setContextVisitId(null)} aria-label="Close visit context">
                      Close
                    </Button>
                  </div>
                  {visitContext.isLoading ? (
                    <div className="mt-3 space-y-2" aria-busy="true" aria-label="Loading visit context">
                      <LoadingSkeleton className="h-3 w-3/4" />
                      <LoadingSkeleton className="h-3 w-1/2" />
                    </div>
                  ) : visitContext.isError ? (
                    <div className="mt-3 space-y-2">
                      <ErrorBanner message="Visit context could not be loaded." />
                      <Button variant="link" onClick={() => visitContext.refetch()}>
                        Retry visit context
                      </Button>
                    </div>
                  ) : visitContext.data ? (
                    <div className="mt-3 space-y-3 text-[11.5px] font-medium text-muted">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge tone={visitContext.data.visit.state === "CANCELLED_ERROR" ? "neutral" : "purple"}>
                          {visitContext.data.visit.state}
                        </StatusBadge>
                        <span>{visitContext.data.visit.visit_type.replaceAll("_", " ")}</span>
                        <span>· {visitContext.data.visit.local_service_date}</span>
                      </div>
                      <p>
                        Queue history: {visitContext.data.queue_history.length} record{visitContext.data.queue_history.length === 1 ? "" : "s"}.
                        {visitContext.data.invoice ? ` Invoice ${visitContext.data.invoice.invoice_no}, balance ${formatMoney(visitContext.data.invoice.balance, currency)}.` : " No invoice."}
                      </p>
                      {can("encounter.read") ? (
                        visitContext.data.clinical === null ? (
                          <p className="rounded-[10px] bg-surface-muted px-3 py-2">No clinical records are attached to this Visit.</p>
                        ) : (
                          <p className="rounded-[10px] bg-surface-muted px-3 py-2">
                            Clinical context: {visitContext.data.clinical?.length ?? 0} encounter record{visitContext.data.clinical?.length === 1 ? "" : "s"}.
                          </p>
                        )
                      ) : (
                        <div className="rounded-[10px] bg-surface-muted px-3 py-2">
                          <p className="flex items-center gap-1.5">
                            <span aria-hidden="true">🔒</span>
                            <span>Clinical details are locked — requires clinical role.</span>
                          </p>
                          {visitContext.data.clinical_summary.length ? (
                            <ul className="mt-2 space-y-1" aria-label="Locked clinical summaries">
                              {visitContext.data.clinical_summary.map((summary) => (
                                <li key={summary.encounter_id}>
                                  {summary.status} · {summary.clinician_name} · {new Date(summary.started_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                </li>
                              ))}
                            </ul>
                          ) : null}
                        </div>
                      )}
                    </div>
                  ) : null}
                </div>
              ) : null}
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
