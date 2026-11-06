"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiRequestError, apiRequest } from "../../../lib/api";
import { protectedQueryKey, useProtectedQueryKey } from "../../../lib/authority";
import { useSession } from "../../../lib/session";
import { Invoice, Patient, Receipt, Service } from "../../../features/clinic";
import { IconBilling, IconCheckCircle, IconPrinter, IconSearch } from "../../../components/icons";
import {
  Button,
  Card,
  CardTitleBar,
  EmptyState,
  ErrorBanner,
  Field,
  PageHeader,
  Select,
  StatusBadge,
  TextInput,
  UnauthorisedState,
  formatDate,
  invoiceStatusBadge,
} from "../../../components/ui";

const METHOD_OPTIONS = [
  { value: "CASH", label: "Cash" },
  { value: "MOBILE_MONEY", label: "Mobile money" },
  { value: "CARD", label: "Card" },
  { value: "BANK", label: "Bank" },
];

function errorMessage(error: unknown) {
  if (error instanceof Error && error.message.includes("permission")) {
    return "You don't have permission to perform this action.";
  }
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function BillingWorkspace() {
  const { session, can, currentFacility } = useSession();
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const prefillPatient = searchParams.get("patient");
  const prefillEncounter = searchParams.get("encounter");
  const focusedVisitId = searchParams.get("visit");
  const focused = Boolean(focusedVisitId);
  const currency = session?.organisation.default_currency ?? "";

  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [method, setMethod] = useState("CASH");
  const [reference, setReference] = useState("");
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  const [patientSearch, setPatientSearch] = useState("");
  const [debouncedPatientSearch, setDebouncedPatientSearch] = useState("");
  const [patientId, setPatientId] = useState(prefillPatient ?? "");
  const [serviceId, setServiceId] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search.trim()), 350);
    return () => clearTimeout(timer);
  }, [search]);
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedPatientSearch(patientSearch.trim()), 350);
    return () => clearTimeout(timer);
  }, [patientSearch]);

  const invoicesKey = useProtectedQueryKey("invoices", "outstanding", debouncedSearch);
  const patientsKey = useProtectedQueryKey("patients", debouncedPatientSearch);
  const servicesKey = useProtectedQueryKey("services");
  const visitInvoiceKey = useProtectedQueryKey("invoice-by-visit", focusedVisitId);

  const invoices = useQuery({
    queryKey: invoicesKey,
    queryFn: () =>
      apiRequest<Invoice[]>(
        "/api/v1/billing/invoices/?status=ISSUED,PARTIALLY_PAID" +
          (debouncedSearch ? `&q=${encodeURIComponent(debouncedSearch)}` : ""),
      ),
    enabled: can("billing.invoice.create") && !focused,
  });

  const visitInvoice = useQuery({
    queryKey: visitInvoiceKey,
    queryFn: () => apiRequest<Invoice>(`/api/v1/billing/invoices/by-visit/${focusedVisitId}/`),
    enabled: focused && can("billing.invoice.create"),
    retry: false,
  });

  const patientResults = useQuery({
    queryKey: patientsKey,
    queryFn: () => apiRequest<Patient[]>("/api/v1/patients/?q=" + encodeURIComponent(debouncedPatientSearch)),
    enabled: can("patient.view"),
  });
  const services = useQuery({
    queryKey: servicesKey,
    queryFn: () => apiRequest<Service[]>("/api/v1/billing/services/"),
  });

  const selectedPatient = useMemo(
    () => (patientResults.data ?? []).find((patient) => patient.id === patientId) ?? null,
    [patientResults.data, patientId],
  );
  const activeService = useMemo(
    () => services.data?.find((service) => service.id === serviceId) ?? services.data?.[0],
    [services.data, serviceId],
  );

  // The focused view can only ever pay the invoice returned for this Visit.
  const activeInvoice = focused ? visitInvoice.data ?? null : selectedInvoice;
  const payable =
    activeInvoice !== null &&
    (activeInvoice.status === "ISSUED" || activeInvoice.status === "PARTIALLY_PAID") &&
    Number(activeInvoice.balance) > 0;
  const canRecordPayment = can("billing.payment.record");
  const visitInvoiceMissing =
    visitInvoice.isError &&
    visitInvoice.error instanceof ApiRequestError &&
    visitInvoice.error.status === 404;

  const initializedInvoiceRef = useRef<string | null>(null);
  useEffect(() => {
    // A different Visit, facility, or authority must never inherit the previous
    // receipt, notice, or prefilled amount.
    setReceipt(null);
    setNotice("");
    setError("");
    initializedInvoiceRef.current = null;
  }, [focusedVisitId, currentFacility?.id]);

  useEffect(() => {
    if (!focused || !activeInvoice) return;
    if (initializedInvoiceRef.current === activeInvoice.id) return;
    initializedInvoiceRef.current = activeInvoice.id;
    setPaymentAmount(activeInvoice.balance);
  }, [focused, activeInvoice]);

  const createInvoice = useMutation({
    mutationFn: () =>
      apiRequest<Invoice>("/api/v1/billing/invoices/", {
        method: "POST",
        body: JSON.stringify({
          patient_id: patientId || prefillPatient,
          ...(prefillEncounter ? { encounter_id: prefillEncounter } : {}),
          items: [{ service_id: serviceId || activeService?.id, quantity: "1" }],
        }),
      }),
    onSuccess: (invoice) => {
      setSelectedInvoice(invoice);
      setPaymentAmount(invoice.balance);
      setNotice(`Invoice ${invoice.invoice_no} created for ${invoice.patient_name}.`);
      setError("");
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("invoices") });
    },
    onError: (reason) => {
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  const pay = useMutation({
    mutationFn: (invoiceId: string) =>
      apiRequest(`/api/v1/billing/invoices/${invoiceId}/pay/`, {
        method: "POST",
        body: JSON.stringify({ amount: paymentAmount, method, ...(reference.trim() ? { reference: reference.trim() } : {}) }),
      }),
    onSuccess: async (_payment, invoiceId) => {
      const data = await apiRequest<Receipt>(`/api/v1/billing/invoices/${invoiceId}/receipt/`);
      setReceipt(data);
      setNotice(`Payment recorded. Receipt ${data.receipt_no}.`);
      setError("");
      setReference("");
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("invoices") });
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("invoice-by-visit") });
    },
    onError: (reason) => {
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  if (!can("billing.invoice.create")) {
    return <UnauthorisedState capability="billing.invoice.create" />;
  }

  return (
    <>
      <PageHeader
        title="Billing & Payments"
        subtitle={
          focused
            ? "Collect payment for the invoice issued when this patient checked in."
            : "Find unpaid invoices, collect payments, and issue receipts."
        }
      />

      {notice ? (
        <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">
          <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
          {notice}
        </p>
      ) : null}
      {error ? <ErrorBanner message={error} onDismiss={() => setError("")} /> : null}

      <section className="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-5 items-start">
        <div className="space-y-5">
          {focused ? (
            <Card>
              <CardTitleBar title="Visit invoice" />
              {visitInvoice.isLoading ? (
                <div className="px-5 py-6 space-y-4" aria-busy="true" aria-label="Loading the Visit invoice">
                  <div className="h-12 animate-pulse rounded-[10px] bg-line-soft" />
                  <div className="h-12 animate-pulse rounded-[10px] bg-line-soft" />
                </div>
              ) : visitInvoiceMissing ? (
                <EmptyState
                  icon={<IconBilling className="h-5 w-5" />}
                  title="No payable invoice exists for this Visit."
                  hint="Check-in issues the consultation invoice. A voided invoice needs a new check-in or an authorised financial correction."
                />
              ) : visitInvoice.isError ? (
                <EmptyState
                  icon={<IconBilling className="h-5 w-5" />}
                  title="The Visit invoice could not be loaded."
                  action={<Button variant="secondary" onClick={() => visitInvoice.refetch()}>Retry</Button>}
                />
              ) : activeInvoice ? (
                <div className="px-5 py-5 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3 leading-tight">
                    <div>
                      <p className="text-[15px] font-bold text-ink">
                        {activeInvoice.invoice_no}
                        <span className="ml-1 font-medium text-secondary">· {activeInvoice.patient_name}</span>
                      </p>
                      <p className="mt-1 text-[12px] font-medium text-muted">
                        Issued {formatDate(activeInvoice.issued_at)}
                      </p>
                    </div>
                    <StatusBadge tone={invoiceStatusBadge(activeInvoice.status).tone}>
                      {invoiceStatusBadge(activeInvoice.status).label}
                    </StatusBadge>
                  </div>
                  {activeInvoice.items?.length ? (
                    <ul className="rounded-[14px] border border-line-soft divide-y divide-line-soft">
                      {activeInvoice.items.map((item) => (
                        <li key={item.id} className="flex items-center justify-between px-3.5 py-2.5 text-[12.5px]">
                          <span className="font-medium text-ink">{item.description}</span>
                          <span className="text-secondary">
                            ×{item.quantity} · {activeInvoice.currency} {item.amount}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </Card>
          ) : (
            <>
              <Card>
              <div className="px-5 pt-5 pb-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h2 className="text-[15px] font-bold text-ink">Awaiting payment ({invoices.data?.length ?? 0})</h2>
                </div>
                <div className="relative mt-3">
                  <IconSearch className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-muted" />
                  <TextInput
                    className="pl-11"
                    placeholder="Find by invoice number, patient name, or patient number…"
                    value={search}
                    onChange={(event) => setSearch(event.target.value)}
                    aria-label="Search invoices"
                  />
                </div>
              </div>

              {invoices.isLoading ? (
                <div className="px-5 pb-5 space-y-4" aria-busy="true" aria-label="Loading invoices">
                  {Array.from({ length: 4 }).map((_, index) => (
                    <div key={index} className="h-12 animate-pulse rounded-[10px] bg-line-soft" />
                  ))}
                </div>
              ) : invoices.isError ? (
                <EmptyState
                  icon={<IconBilling className="h-5 w-5" />}
                  title="Invoices could not be loaded."
                  action={<Button variant="secondary" onClick={() => invoices.refetch()}>Retry</Button>}
                />
              ) : (invoices.data ?? []).length === 0 ? (
                <EmptyState
                  icon={<IconBilling className="h-5 w-5" />}
                  title="No unpaid invoices found."
                  hint={debouncedSearch ? "Try a different invoice number or patient name." : "Invoices appear here once they are issued."}
                />
              ) : (
                <ul className="px-5 pb-2 divide-y divide-line-soft">
                  {(invoices.data ?? []).map((invoice) => {
                    const badge = invoiceStatusBadge(invoice.status);
                    const active = selectedInvoice?.id === invoice.id;
                    return (
                      <li key={invoice.id} className="flex flex-wrap items-center gap-3 py-3">
                        <div className="flex-1 min-w-0 leading-tight">
                          <div className="text-[13px] font-semibold text-ink">
                            {invoice.invoice_no}
                            <span className="mx-1 text-muted">·</span>
                            <span className="font-medium">{invoice.patient_name}</span>
                          </div>
                          <div className="mt-0.5 text-[11.5px] font-medium text-muted">
                            Issued {formatDate(invoice.issued_at)}
                            <span className="mx-0.5">•</span>
                            Total {invoice.currency} {invoice.total}
                          </div>
                        </div>
                        <div className="text-right leading-tight">
                          <StatusBadge tone={badge.tone}>{badge.label}</StatusBadge>
                          <div className="mt-1 text-[11px] font-semibold text-ink">
                            Balance {invoice.currency} {invoice.balance}
                          </div>
                        </div>
                        <Button
                          variant="small-secondary"
                          aria-pressed={active}
                          className={active ? "bg-primary-soft text-primary-text border-primary-soft" : ""}
                          onClick={() => {
                            setSelectedInvoice(invoice);
                            setPaymentAmount(invoice.balance);
                            setReceipt(null);
                            setNotice("");
                          }}
                        >
                          {active ? "Selected" : "Collect"}
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Card>

            <Card>
              <CardTitleBar title="New invoice" />
              <div className="px-5 py-5 grid gap-4 sm:grid-cols-2">
                {can("patient.view") ? (
                  <div className="sm:col-span-2 space-y-3">
                    <Field label="Patient" htmlFor="invoice-patient-search">
                      <div className="relative">
                        <IconSearch className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 h-[18px] w-[18px] text-muted" />
                        <TextInput
                          id="invoice-patient-search"
                          className="pl-11"
                          placeholder="Search patients…"
                          value={patientSearch}
                          onChange={(event) => setPatientSearch(event.target.value)}
                        />
                      </div>
                    </Field>
                    {debouncedPatientSearch && (patientResults.data ?? []).length > 0 && !selectedPatient ? (
                      <ul className="border border-line rounded-[12px] divide-y divide-line-soft overflow-hidden" role="listbox" aria-label="Patient results">
                        {(patientResults.data ?? []).slice(0, 5).map((patient) => (
                          <li key={patient.id}>
                            <button
                              type="button"
                              role="option"
                              aria-selected={patient.id === patientId}
                              onClick={() => setPatientId(patient.id)}
                              className="w-full text-left px-3.5 py-2.5 text-[12.5px] font-medium text-ink hover:bg-primary-hover transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-inset"
                            >
                              {patient.display_name}
                              <span className="ml-1 text-muted">· {patient.patient_no}</span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {selectedPatient ? (
                      <p className="flex items-center gap-2 text-[12.5px] font-medium text-secondary">
                        <IconCheckCircle className="h-4 w-4 text-accent-teal" />
                        {selectedPatient.display_name} · {selectedPatient.patient_no}
                        <button
                          type="button"
                          onClick={() => setPatientId("")}
                          className="font-semibold text-primary-text hover:text-primary-strong focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded"
                        >
                          Change
                        </button>
                      </p>
                    ) : null}
                  </div>
                ) : null}

                <Field label="Service" htmlFor="service">
                  <Select id="service" value={serviceId || activeService?.id || ""} onChange={(event) => setServiceId(event.target.value)}>
                    {services.data?.map((service) => (
                      <option key={service.id} value={service.id}>
                        {service.name} · {service.prices?.[0]?.amount || "No price"}
                      </option>
                    ))}
                  </Select>
                </Field>
                <div className="flex items-end">
                  <Button
                    disabled={!patientId || createInvoice.isPending}
                    onClick={() => createInvoice.mutate()}
                  >
                    {createInvoice.isPending ? "Creating…" : "Create invoice"}
                  </Button>
                </div>
                {prefillEncounter ? (
                  <p className="sm:col-span-2 text-[11.5px] font-medium text-muted">
                    Linked to encounter {prefillEncounter.slice(0, 8)}…
                  </p>
                ) : null}
              </div>
              </Card>
            </>
          )}
        </div>

        <div className="space-y-5 xl:sticky xl:top-[92px]">
          <Card>
            <CardTitleBar title="Collect payment" />
            {activeInvoice ? (
              <div className="px-5 py-5 space-y-5">
                <div className="leading-tight">
                  <p className="text-[15px] font-bold text-ink">
                    {activeInvoice.invoice_no}
                    <span className="ml-1 font-medium text-secondary">· {activeInvoice.patient_name}</span>
                  </p>
                  <p className="mt-1 text-[12px] font-medium text-muted">
                    Total {activeInvoice.currency} {activeInvoice.total}
                    <span className="mx-0.5">•</span>
                    Paid {activeInvoice.currency} {activeInvoice.amount_paid}
                    <span className="mx-0.5">•</span>
                    Balance {activeInvoice.currency} {activeInvoice.balance}
                  </p>
                </div>

                {!focused && activeInvoice.items?.length ? (
                  <ul className="rounded-[14px] border border-line-soft divide-y divide-line-soft">
                    {activeInvoice.items.map((item) => (
                      <li key={item.id} className="flex items-center justify-between px-3.5 py-2.5 text-[12.5px]">
                        <span className="font-medium text-ink">{item.description}</span>
                        <span className="text-secondary">
                          ×{item.quantity} · {activeInvoice.currency} {item.amount}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : null}

                {receipt ? null : activeInvoice.status === "PAID" ? (
                  <p
                    className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink"
                    role="status"
                  >
                    <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
                    This invoice is paid in full.
                  </p>
                ) : payable && canRecordPayment ? (
                  <div className="grid gap-4 sm:grid-cols-2">
                    <Field label={`Amount (${activeInvoice.currency})`} htmlFor="payment-amount">
                      <TextInput
                        id="payment-amount"
                        inputMode="decimal"
                        value={paymentAmount}
                        onChange={(event) => setPaymentAmount(event.target.value)}
                      />
                    </Field>
                    <Field label="Method" htmlFor="payment-method">
                      <Select id="payment-method" value={method} onChange={(event) => setMethod(event.target.value)}>
                        {METHOD_OPTIONS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </Select>
                    </Field>
                    <div className="sm:col-span-2">
                      <Field label="Reference (optional)" htmlFor="payment-reference">
                        <TextInput
                          id="payment-reference"
                          value={reference}
                          onChange={(event) => setReference(event.target.value)}
                          placeholder="Transaction reference for non-cash payments"
                        />
                      </Field>
                    </div>
                    <div className="sm:col-span-2">
                      <Button disabled={pay.isPending} onClick={() => pay.mutate(activeInvoice.id)}>
                        {pay.isPending ? "Posting…" : "Post payment"}
                      </Button>
                    </div>
                  </div>
                ) : payable ? (
                  <p className="rounded-[14px] border border-line bg-surface-muted px-4 py-3 text-[12.5px] font-medium text-secondary" role="status">
                    You do not have permission to record payments for this invoice.
                  </p>
                ) : (
                  <p className="rounded-[14px] border border-line bg-surface-muted px-4 py-3 text-[12.5px] font-medium text-secondary" role="status">
                    This invoice cannot accept a payment in its current state.
                  </p>
                )}
              </div>
            ) : focused && visitInvoice.isLoading ? (
              <div className="px-5 py-6" aria-busy="true" aria-label="Loading the Visit invoice">
                <div className="h-12 animate-pulse rounded-[10px] bg-line-soft" />
              </div>
            ) : (
              <EmptyState
                icon={<IconBilling className="h-5 w-5" />}
                title={focused ? "No payable invoice." : "No invoice selected."}
                hint={
                  focused
                    ? "This Visit has no invoice the cashier can collect right now."
                    : "Select an unpaid invoice, or create a new one, to collect payment."
                }
              />
            )}
          </Card>

          {receipt ? (
            <Card data-print-sheet className="print:border-0 print:shadow-none">
              <div className="px-5 py-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-[15px] font-bold text-ink">Receipt</h2>
                  <Button variant="secondary" onClick={() => window.print()}>
                    <IconPrinter className="h-4 w-4" />
                    Print receipt
                  </Button>
                </div>
                <div className="mt-4 rounded-[14px] border border-line bg-white p-4 font-sans">
                  <p className="text-[13px] font-bold text-ink">{session?.organisation.name}</p>
                  <p className="mt-0.5 text-[11.5px] font-medium text-muted">{currentFacility?.name ?? ""}</p>
                  <hr className="my-3 border-line-soft" />
                  <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[12.5px]">
                    <dt className="font-medium text-secondary">Receipt no</dt>
                    <dd className="text-right font-semibold text-ink">{receipt.receipt_no}</dd>
                    <dt className="font-medium text-secondary">Invoice</dt>
                    <dd className="text-right font-semibold text-ink">{receipt.invoice_no}</dd>
                    <dt className="font-medium text-secondary">Patient</dt>
                    <dd className="text-right font-semibold text-ink">
                      {receipt.patient_name} · {receipt.patient_no}
                    </dd>
                    <dt className="font-medium text-secondary">Amount</dt>
                    <dd className="text-right font-bold text-ink">
                      {receipt.currency} {receipt.amount}
                    </dd>
                    <dt className="font-medium text-secondary">Method</dt>
                    <dd className="text-right font-semibold text-ink">{receipt.method.replaceAll("_", " ")}</dd>
                    {receipt.reference ? (
                      <>
                        <dt className="font-medium text-secondary">Reference</dt>
                        <dd className="text-right font-semibold text-ink">{receipt.reference}</dd>
                      </>
                    ) : null}
                    <dt className="font-medium text-secondary">Invoice balance</dt>
                    <dd className="text-right font-semibold text-ink">
                      {receipt.currency} {receipt.invoice_balance}
                    </dd>
                  </dl>
                  <hr className="my-3 border-line-soft" />
                  <p className="text-[11px] font-medium text-muted">Thank you. This receipt was issued by KlinKlik.</p>
                </div>
                <Button
                  variant="link"
                  className="mt-3"
                  onClick={() => {
                    setReceipt(null);
                    if (!focused) setSelectedInvoice(null);
                  }}
                >
                  {focused ? "Done" : "Done — collect another payment"}
                </Button>
              </div>
            </Card>
          ) : null}
        </div>
      </section>
    </>
  );
}

export default function BillingPage() {
  return (
    <Suspense fallback={<Card />}>
      <BillingWorkspace />
    </Suspense>
  );
}
