"use client";

import Link from "next/link";
import { Suspense, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "../../../lib/api";
import { useSession } from "../../../lib/session";
import { Department, Patient, QueueEntry } from "../../../features/clinic";
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

function sexLabel(sex: string): string {
  return SEX_OPTIONS.find((option) => option.value === sex)?.label ?? sex;
}

function errorMessage(error: unknown) {
  if (error instanceof Error && error.message.includes("permission")) {
    return "You don't have permission to perform this action.";
  }
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function post<T>(path: string, body: unknown) {
  return apiRequest<T>(path, { method: "POST", body: JSON.stringify(body) });
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

  const createPatient = useMutation({
    mutationFn: () => post<Patient>("/api/v1/patients/", { first_name: firstName, last_name: lastName, phone, sex }),
    onSuccess: (patient) => {
      setSelected(patient);
      setNotice(`${patient.display_name} registered as ${patient.patient_no}.`);
      setError("");
      setFirstName("");
      setLastName("");
      setPhone("");
      queryClient.invalidateQueries({ queryKey: ["patients"] });
    },
    onError: (reason) => {
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  const checkIn = useMutation({
    mutationFn: () =>
      post<QueueEntry>("/api/v1/clinic/check-ins/", {
        patient_id: selected?.id,
        department_id: departmentId || departments.data?.[0]?.id,
      }),
    onSuccess: (entry) => {
      setNotice(`${entry.patient_name} checked in as ${entry.queue_label}.`);
      setError("");
      queryClient.invalidateQueries({ queryKey: ["queue"] });
    },
    onError: (reason) => {
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
                  createPatient.mutate();
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

              {can("queue.view") ? (
                <div className="border-t border-line-soft pt-5 grid gap-4">
                  <Field label="Check-in department" htmlFor="department">
                    <Select
                      id="department"
                      value={departmentId || departments.data?.[0]?.id || ""}
                      onChange={(event) => setDepartmentId(event.target.value)}
                    >
                      {departments.data?.map((department) => (
                        <option key={department.id} value={department.id}>
                          {department.name}
                        </option>
                      ))}
                    </Select>
                  </Field>
                  <Button disabled={checkIn.isPending} onClick={() => checkIn.mutate()}>
                    {checkIn.isPending ? "Checking in…" : "Check in patient"}
                  </Button>
                  <p className="text-[11.5px] font-medium text-muted">
                    Check-in adds the patient to today&apos;s queue.{" "}
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
