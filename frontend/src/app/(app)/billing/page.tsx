"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiRequestError, apiRequest, newIdempotencyKey } from "../../../lib/api";
import {
  getAuthoritySnapshot,
  isCurrentAuthority,
  protectedQueryKey,
  useProtectedQueryKey,
  type AuthoritySnapshot,
} from "../../../lib/authority";
import { useSession } from "../../../lib/session";
import { Invoice, Patient, Receipt, Service } from "../../../features/clinic";
import { IconAlertTriangle, IconBilling, IconCheckCircle, IconPrinter, IconSearch } from "../../../components/icons";
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

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type ReceiptState = {
  invoiceId: string;
  receiptId: string | null;
  exact: boolean;
  data: Receipt | null;
  error: string;
  loading: boolean;
};

type PaymentContext = {
  origin: AuthoritySnapshot;
  visitId: string | null;
  paymentCount: number;
};

type CashierShift = {
  id: string;
  status: "OPEN" | "CLOSED";
  opened_at: string;
  closed_at?: string | null;
  opening_float: string;
  declared_cash: string | null;
  expected_cash: string | null;
  variance: string | null;
  version: number;
};

type ZReport = {
  shift_id: string;
  status: string;
  tenders: Array<{ method: string; count: number; amount: string }>;
  payment_count: number;
  reversed_count: number;
  refund_count: number;
  refund_total: string;
  discount_total: string;
  opening_float: string;
  declared_cash: string | null;
  expected_cash: string | null;
  variance: string | null;
  variance_reason: string;
};

function errorMessage(error: unknown) {
  if (error instanceof Error && error.message.includes("permission")) {
    return "You don't have permission to perform this action.";
  }
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function readVisitParam(searchParams: URLSearchParams) {
  if (!searchParams.has("visit")) {
    return { focused: false, visitId: null as string | null, invalid: false };
  }
  const raw = (searchParams.get("visit") ?? "").trim();
  if (!UUID_PATTERN.test(raw)) {
    return { focused: true, visitId: null as string | null, invalid: true };
  }
  return { focused: true, visitId: raw.toLowerCase(), invalid: false };
}

function BillingWorkspace() {
  const { session, can, currentFacility } = useSession();
  const queryClient = useQueryClient();
  const searchParams = useSearchParams();
  const prefillPatient = searchParams.get("patient");
  const prefillEncounter = searchParams.get("encounter");
  const { focused, visitId: focusedVisitId, invalid: focusedVisitInvalid } =
    readVisitParam(searchParams);
  const currency = session?.organisation.default_currency ?? "";

  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [paymentAmount, setPaymentAmount] = useState("");
  const [method, setMethod] = useState("CASH");
  const [reference, setReference] = useState("");
  const [receiptState, setReceiptState] = useState<ReceiptState | null>(null);
  // The payment whose post-payment invoice refresh has not yet been confirmed.
  // No new collection may open until that refresh returns for the same Visit.
  const [postPaymentGate, setPostPaymentGate] = useState<{
    invoiceId: string;
    paidAt: number;
  } | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [openingFloat, setOpeningFloat] = useState("0.00");
  const [declaredCash, setDeclaredCash] = useState("");
  const [closeReason, setCloseReason] = useState("");
  const [closeResult, setCloseResult] = useState<CashierShift | null>(null);
  const [reversingPaymentId, setReversingPaymentId] = useState<string | null>(null);
  const [reversalReason, setReversalReason] = useState("");
  const [creditAmount, setCreditAmount] = useState("");
  const [creditReason, setCreditReason] = useState("");
  const [repriceListId, setRepriceListId] = useState("");
  const [repriceResult, setRepriceResult] = useState<{
    before_total: string;
    after_total: string;
    line_set_version: number;
  } | null>(null);
  const [zReport, setZReport] = useState<ZReport | null>(null);
  const paymentKeyRef = useRef<string | null>(null);

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
    queryFn: async () => {
      if (!focusedVisitId) {
        throw new Error("This billing link does not identify a Visit.");
      }
      const invoice = await apiRequest<Invoice>(
        `/api/v1/billing/invoices/by-visit/${encodeURIComponent(focusedVisitId)}/`,
      );
      // A response for a different Visit must never become payable here.
      if (invoice.visit !== focusedVisitId) {
        throw new Error("The invoice returned does not belong to this Visit.");
      }
      return invoice;
    },
    enabled: focused && Boolean(focusedVisitId) && can("billing.invoice.create"),
    retry: false,
  });

  const shiftKey = useProtectedQueryKey("cashier-shift");
  const shiftQuery = useQuery({
    queryKey: shiftKey,
    queryFn: () => apiRequest<{ shift: CashierShift | null }>("/api/v1/billing/shifts/current/"),
    enabled: can("billing.payment.record"),
  });
  const activeShift = shiftQuery.data?.shift ?? null;

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
  const activeInvoice = focused
    ? visitInvoice.data && visitInvoice.data.visit === focusedVisitId
      ? visitInvoice.data
      : null
    : selectedInvoice;
  const canRecordPayment = can("billing.payment.record");
  const visitInvoiceMissing =
    visitInvoice.isError &&
    visitInvoice.error instanceof ApiRequestError &&
    visitInvoice.error.status === 404;

  // A cached invoice may still identify a receipt, but it may only authorise a
  // new payment once the lookup has succeeded for this exact Visit and, after a
  // posted payment, once the refresh that follows it has actually returned.
  const lookupConfirmed =
    visitInvoice.isSuccess &&
    (!postPaymentGate || visitInvoice.dataUpdatedAt > postPaymentGate.paidAt);
  const collectionReady = !focused || lookupConfirmed;
  const payable =
    collectionReady &&
    activeInvoice !== null &&
    (activeInvoice.status === "ISSUED" || activeInvoice.status === "PARTIALLY_PAID") &&
    Number(activeInvoice.balance) > 0;
  const activeReceipt =
    receiptState && activeInvoice && receiptState.invoiceId === activeInvoice.id
      ? receiptState
      : null;

  const initializedInvoiceRef = useRef<{ id: string; balance: string } | null>(null);
  // The invoice whose posted payment is being reconciled. A receipt response is
  // only applied while this still names the same invoice and the authority that
  // submitted it is current.
  const receiptTargetRef = useRef<string | null>(null);
  // Latest focused Visit, so a mutation result can tell whether its context is
  // still the one on screen. Kept current on every render rather than in an
  // effect so a response cannot slip through between commit and effect.
  const visitContextRef = useRef<string | null>(focusedVisitId);
  visitContextRef.current = focusedVisitId;
  // Latest payable invoice, so a result for invoice A cannot render while the
  // cashier has selected invoice B in the ordinary list.
  const activeInvoiceIdRef = useRef<string | null>(activeInvoice?.id ?? null);
  activeInvoiceIdRef.current = activeInvoice?.id ?? null;

  function isCurrentPaymentContext(context: PaymentContext | undefined, invoiceId: string) {
    return (
      context !== undefined &&
      isCurrentAuthority(context.origin) &&
      visitContextRef.current === context.visitId &&
      activeInvoiceIdRef.current === invoiceId
    );
  }

  function isCurrentReceipt(invoiceId: string, origin: AuthoritySnapshot) {
    return (
      isCurrentAuthority(origin) &&
      activeInvoiceIdRef.current === invoiceId &&
      receiptTargetRef.current === invoiceId
    );
  }

  useEffect(() => {
    // A different Visit, facility, or authority must never inherit the previous
    // receipt, notice, or prefilled amount.
    receiptTargetRef.current = null;
    setReceiptState(null);
    setPostPaymentGate(null);
    setNotice("");
    setError("");
    initializedInvoiceRef.current = null;
  }, [focused, focusedVisitId, currentFacility?.id]);

  useEffect(() => {
    // Prefill only from a confirmed balance, and again whenever that confirmed
    // balance changes (a payment, then the refresh that follows it).
    if (!focused || !activeInvoice || !collectionReady) return;
    const prefilled = initializedInvoiceRef.current;
    if (prefilled?.id === activeInvoice.id && prefilled.balance === activeInvoice.balance) return;
    initializedInvoiceRef.current = { id: activeInvoice.id, balance: activeInvoice.balance };
    setPaymentAmount(activeInvoice.balance);
  }, [focused, activeInvoice, collectionReady]);

  async function loadReceipt(
    invoiceId: string,
    origin: AuthoritySnapshot,
    receiptId: string | null = null,
    exact = false,
  ) {
    setReceiptState((current) =>
      current && current.invoiceId === invoiceId
        ? { ...current, loading: true, error: "" }
        : current,
    );
    try {
      const path =
        exact && receiptId
          ? `/api/v1/billing/receipts/${encodeURIComponent(receiptId)}/`
          : `/api/v1/billing/invoices/${invoiceId}/receipt/`;
      const data = await apiRequest<Receipt>(path);
      if (!isCurrentReceipt(invoiceId, origin)) return;
      setReceiptState({
        invoiceId,
        receiptId,
        exact,
        data,
        error: "",
        loading: false,
      });
      setNotice(`Payment recorded. Receipt ${data.receipt_no}.`);
    } catch (reason) {
      if (!isCurrentReceipt(invoiceId, origin)) return;
      setReceiptState({
        invoiceId,
        receiptId,
        exact,
        data: null,
        error: errorMessage(reason),
        loading: false,
      });
      setNotice("Payment recorded.");
    }
  }

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
      setReceiptState(null);
      receiptTargetRef.current = null;
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
    mutationFn: (invoiceId: string) => {
      const key = paymentKeyRef.current ?? newIdempotencyKey("s05-payment");
      paymentKeyRef.current = key;
      const path = activeShift
        ? `/api/v1/billing/invoices/${invoiceId}/payments/`
        : `/api/v1/billing/invoices/${invoiceId}/pay/`;
      return apiRequest<{ id: string; receipt_id: string | null }>(path, {
        method: "POST",
        headers: { "Idempotency-Key": key },
        body: JSON.stringify({ amount: paymentAmount, method, ...(reference.trim() ? { reference: reference.trim() } : {}) }),
      });
    },
    onMutate: (): PaymentContext => ({
      origin: getAuthoritySnapshot(),
      visitId: visitContextRef.current,
      paymentCount: activeInvoice?.payments?.length ?? 0,
    }),
    onSuccess: (result, invoiceId, context) => {
      // The POST committed the payment. Everything below is reconciliation:
      // a failed receipt read must never read back as a failed payment.
      paymentKeyRef.current = null;
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("invoices") });
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("invoice-by-visit") });
      if (!isCurrentPaymentContext(context, invoiceId)) {
        // The cashier already moved on; the committed payment stays recorded
        // but nothing from this result may render on the new context.
        return;
      }
      if (focused) {
        // A new collection stays closed until the refresh for this payment has
        // returned, so a stale balance can never reopen the old form.
        setPostPaymentGate({ invoiceId, paidAt: Date.now() });
      }
      receiptTargetRef.current = invoiceId;
      setReceiptState({
        invoiceId,
        receiptId: result.receipt_id ?? null,
        exact: context.paymentCount > 0,
        data: null,
        error: "",
        loading: true,
      });
      setNotice("Payment recorded. Preparing the receipt.");
      setError("");
      setReference("");
      void loadReceipt(
        invoiceId,
        context.origin,
        result.receipt_id ?? null,
        context.paymentCount > 0,
      );
    },
    onError: (reason, invoiceId, context) => {
      if (!isCurrentPaymentContext(context, invoiceId)) return;
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  const openShift = useMutation({
    mutationFn: () =>
      apiRequest<CashierShift>("/api/v1/billing/shifts/open/", {
        method: "POST",
        body: JSON.stringify({ opening_float: openingFloat || "0.00" }),
      }),
    onSuccess: (shift) => {
      setNotice(`Shift opened with ${shift.opening_float} opening float.`);
      setError("");
      setCloseResult(null);
      queryClient.invalidateQueries({ queryKey: shiftKey });
    },
    onError: (reason) => {
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  const closeShift = useMutation({
    mutationFn: (shiftId: string) =>
      apiRequest<CashierShift>(`/api/v1/billing/shifts/${shiftId}/close/`, {
        method: "POST",
        headers: { "Idempotency-Key": newIdempotencyKey("s05-shift-close") },
        body: JSON.stringify({
          declared_cash: declaredCash,
          ...(closeReason.trim() ? { reason: closeReason.trim() } : {}),
        }),
      }),
    onSuccess: (shift) => {
      setCloseResult(shift);
      setNotice(
        `Shift closed. Expected ${shift.expected_cash}, counted ${shift.declared_cash}, variance ${shift.variance}.`,
      );
      setDeclaredCash("");
      setCloseReason("");
      setError("");
      queryClient.invalidateQueries({ queryKey: shiftKey });
    },
    onError: (reason) => {
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  const reversePayment = useMutation({
    mutationFn: (paymentId: string) =>
      apiRequest(`/api/v1/billing/payments/${paymentId}/reverse/`, {
        method: "POST",
        headers: { "Idempotency-Key": newIdempotencyKey("s05-reverse") },
        body: JSON.stringify({ reason: reversalReason.trim() }),
      }),
    onSuccess: () => {
      setReversingPaymentId(null);
      setReversalReason("");
      setNotice("Payment reversed. The invoice balance was restored without deleting payment evidence.");
      setError("");
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("invoices") });
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("invoice-by-visit") });
      queryClient.invalidateQueries({ queryKey: shiftKey });
    },
    onError: (reason) => {
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  const reprintReceipt = useMutation({
    mutationFn: (receiptId: string) =>
      apiRequest(`/api/v1/billing/receipts/${receiptId}/reprint/`, {
        method: "POST",
        headers: { "Idempotency-Key": newIdempotencyKey("s05-reprint") },
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      setNotice((current) => (current ? current : "Receipt reprint recorded."));
      window.print();
    },
    onError: (reason) => {
      setError(errorMessage(reason));
    },
  });

  const repriceInvoice = useMutation({
    mutationFn: (invoiceId: string) =>
      apiRequest<{
        before_total: string;
        after_total: string;
        line_set_version: number;
      }>(`/api/v1/billing/invoices/${invoiceId}/reprice/`, {
        method: "POST",
        headers: { "Idempotency-Key": newIdempotencyKey("s07-reprice") },
        body: JSON.stringify({
          expected_version: activeInvoice?.version,
          ...(repriceListId.trim() ? { price_list_id: repriceListId.trim() } : {}),
        }),
      }),
    onSuccess: (result) => {
      setRepriceResult(result);
      setNotice(
        `Invoice repriced from ${result.before_total} to ${result.after_total} (line set ${result.line_set_version}).`,
      );
      setError("");
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("invoices") });
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("invoice-by-visit") });
    },
    onError: (reason) => {
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  const issueCredit = useMutation({
    mutationFn: (invoiceId: string) =>
      apiRequest<{ credit_no: string }>(
        `/api/v1/billing/invoices/${invoiceId}/credit-notes/`,
        {
          method: "POST",
          headers: { "Idempotency-Key": newIdempotencyKey("s06-credit") },
          body: JSON.stringify({ amount: creditAmount, reason: creditReason.trim() }),
        },
      ),
    onSuccess: (credit) => {
      setNotice(`Credit note ${credit.credit_no} issued.`);
      setCreditAmount("");
      setCreditReason("");
      setError("");
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("invoices") });
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("invoice-by-visit") });
    },
    onError: (reason) => {
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  const loadZReport = useMutation({
    mutationFn: (shiftId: string) =>
      apiRequest<ZReport>(`/api/v1/billing/shifts/${shiftId}/z-report/`),
    onSuccess: (report) => {
      setZReport(report);
      setError("");
    },
    onError: (reason) => setError(errorMessage(reason)),
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

      {canRecordPayment ? (
        <Card>
          <CardTitleBar title="Cashier shift" />
          <div className="px-5 py-4 space-y-3">
            {shiftQuery.isLoading ? (
              <p className="text-[12.5px] font-medium text-secondary" role="status" aria-busy="true">
                Loading the current shift…
              </p>
            ) : shiftQuery.isError ? (
              <p className="text-[12.5px] font-medium text-ink" role="alert">
                The current shift could not be loaded. Payments remain unavailable until it is.
              </p>
            ) : activeShift ? (
              <>
                <p className="text-[12.5px] font-medium text-ink">
                  Shift open since {formatDate(activeShift.opened_at)} · opening float{" "}
                  {activeShift.opening_float}
                </p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Declared cash" htmlFor="declared-cash">
                    <TextInput
                      id="declared-cash"
                      inputMode="decimal"
                      value={declaredCash}
                      onChange={(event) => setDeclaredCash(event.target.value)}
                      placeholder="Count the drawer before closing"
                    />
                  </Field>
                  <Field label="Close reason (optional)" htmlFor="shift-close-reason">
                    <TextInput
                      id="shift-close-reason"
                      value={closeReason}
                      onChange={(event) => setCloseReason(event.target.value)}
                    />
                  </Field>
                </div>
                <Button
                  variant="secondary"
                  disabled={closeShift.isPending || !declaredCash.trim()}
                  onClick={() => closeShift.mutate(activeShift.id)}
                >
                  {closeShift.isPending ? "Closing…" : "Close shift"}
                </Button>
                <p className="text-[11.5px] font-medium text-muted">
                  Expected cash and variance are shown only after your blind count is recorded.
                </p>
                <Button
                  variant="link"
                  disabled={loadZReport.isPending}
                  onClick={() => loadZReport.mutate(activeShift.id)}
                >
                  {loadZReport.isPending ? "Loading Z-report…" : "Load Z-report"}
                </Button>
              </>
            ) : (
              <>
                <p className="text-[12.5px] font-medium text-secondary">
                  No shift is open. Shift-bound payments use exact allocations and an issued receipt.
                </p>
                <div className="flex flex-wrap items-end gap-3">
                  <Field label="Opening float" htmlFor="opening-float">
                    <TextInput
                      id="opening-float"
                      inputMode="decimal"
                      value={openingFloat}
                      onChange={(event) => setOpeningFloat(event.target.value)}
                    />
                  </Field>
                  <Button disabled={openShift.isPending} onClick={() => openShift.mutate()}>
                    {openShift.isPending ? "Opening…" : "Open shift"}
                  </Button>
                </div>
              </>
            )}
            {closeResult ? (
              <div className="space-y-2">
                <p className="rounded-[12px] bg-accent-teal-soft px-3.5 py-2.5 text-[12px] font-medium text-ink" role="status">
                  Closed shift {closeResult.id.slice(0, 8)}: expected {closeResult.expected_cash},
                  declared {closeResult.declared_cash}, variance {closeResult.variance}.
                </p>
                <Button
                  variant="link"
                  disabled={loadZReport.isPending}
                  onClick={() => loadZReport.mutate(closeResult.id)}
                >
                  {loadZReport.isPending ? "Loading Z-report…" : "Load Z-report"}
                </Button>
              </div>
            ) : null}
          </div>
        </Card>
      ) : null}

      {zReport ? (
        <Card data-z-report className="print:border-0 print:shadow-none">
          <div className="px-5 py-5">
            <div className="flex items-center justify-between">
              <h2 className="text-[15px] font-bold text-ink">Shift Z-report</h2>
              <Button variant="secondary" onClick={() => window.print()}>
                <IconPrinter className="h-4 w-4" />
                Print Z-report
              </Button>
            </div>
            <div className="mt-4 rounded-[14px] border border-line bg-white p-4 text-[12.5px]">
              <p className="font-bold text-ink">{session?.organisation.name}</p>
              <p className="text-[11.5px] font-medium text-muted">{currentFacility?.name ?? ""}</p>
              <hr className="my-3 border-line-soft" />
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5">
                <dt className="font-medium text-secondary">Shift</dt>
                <dd className="text-right font-semibold text-ink">{zReport.shift_id.slice(0, 8)} · {zReport.status}</dd>
                <dt className="font-medium text-secondary">Opening float</dt>
                <dd className="text-right font-semibold text-ink">{zReport.opening_float}</dd>
                <dt className="font-medium text-secondary">Payments</dt>
                <dd className="text-right font-semibold text-ink">{zReport.payment_count}</dd>
                <dt className="font-medium text-secondary">Reversals</dt>
                <dd className="text-right font-semibold text-ink">{zReport.reversed_count}</dd>
                <dt className="font-medium text-secondary">Refunds</dt>
                <dd className="text-right font-semibold text-ink">{zReport.refund_count} · {zReport.refund_total}</dd>
                <dt className="font-medium text-secondary">Discounts</dt>
                <dd className="text-right font-semibold text-ink">{zReport.discount_total}</dd>
                <dt className="font-medium text-secondary">Expected cash</dt>
                <dd className="text-right font-semibold text-ink">{zReport.expected_cash ?? "—"}</dd>
                <dt className="font-medium text-secondary">Declared cash</dt>
                <dd className="text-right font-semibold text-ink">{zReport.declared_cash ?? "—"}</dd>
                <dt className="font-medium text-secondary">Variance</dt>
                <dd className="text-right font-bold text-ink">{zReport.variance ?? "—"}</dd>
              </dl>
              <hr className="my-3 border-line-soft" />
              <p className="text-[11px] font-bold uppercase tracking-wide text-muted">Tenders</p>
              {zReport.tenders.length ? (
                <ul className="mt-1 divide-y divide-line-soft">
                  {zReport.tenders.map((tender) => (
                    <li key={tender.method} className="flex justify-between py-1">
                      <span>{tender.method.replaceAll("_", " ")} × {tender.count}</span>
                      <span className="font-semibold">{tender.amount}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[12px] font-medium text-secondary">No committed tenders.</p>
              )}
              {zReport.variance_reason ? (
                <p className="mt-2 text-[11.5px] font-medium text-secondary">
                  Variance reason: {zReport.variance_reason}
                </p>
              ) : null}
              <p className="mt-3 text-[10.5px] font-medium text-muted">
                Internal cashier summary. Not a fiscal receipt.
              </p>
            </div>
          </div>
        </Card>
      ) : null}

      <section className="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-5 items-start">
        <div className="space-y-5">
          {focused ? (
            <Card>
              <CardTitleBar title="Visit invoice" />
              {focusedVisitInvalid ? (
                <EmptyState
                  icon={<IconBilling className="h-5 w-5" />}
                  title="This billing link does not identify a Visit."
                  hint="Open the invoice from the signed consultation, or find it in the outstanding list."
                />
              ) : visitInvoice.isLoading ? (
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
                  hint="No invoice is payable until this lookup succeeds."
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
                  {activeInvoice.payments?.length ? (
                    <div className="space-y-2">
                      <p className="text-[12px] font-bold uppercase tracking-wide text-muted">Payments</p>
                      <ul className="rounded-[14px] border border-line-soft divide-y divide-line-soft">
                        {activeInvoice.payments.map((payment) => (
                          <li key={payment.id} className="px-3.5 py-2.5 text-[12.5px]">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-medium text-ink">
                                {payment.receipt_no} · {activeInvoice.currency} {payment.amount}
                              </span>
                              <span className="text-secondary">
                                {payment.method.replaceAll("_", " ")} · {payment.status}
                              </span>
                            </div>
                            {payment.status === "CONFIRMED" && can("billing.payment.reverse") ? (
                              reversingPaymentId === payment.id ? (
                                <div className="mt-2 flex flex-wrap items-end gap-2">
                                  <Field label="Reversal reason" htmlFor={`reverse-reason-${payment.id}`}>
                                    <TextInput
                                      id={`reverse-reason-${payment.id}`}
                                      value={reversalReason}
                                      onChange={(event) => setReversalReason(event.target.value)}
                                      placeholder="Why is the whole payment wrong?"
                                    />
                                  </Field>
                                  <Button
                                    variant="secondary"
                                    disabled={reversePayment.isPending || !reversalReason.trim()}
                                    onClick={() => reversePayment.mutate(payment.id)}
                                  >
                                    {reversePayment.isPending ? "Reversing…" : "Confirm reversal"}
                                  </Button>
                                  <Button
                                    variant="link"
                                    onClick={() => {
                                      setReversingPaymentId(null);
                                      setReversalReason("");
                                    }}
                                  >
                                    Cancel
                                  </Button>
                                </div>
                              ) : (
                                <Button
                                  variant="link"
                                  className="mt-1"
                                  onClick={() => {
                                    setReversingPaymentId(payment.id);
                                    setReversalReason("");
                                  }}
                                >
                                  Reverse whole payment
                                </Button>
                              )
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 rounded-[14px] bg-surface-muted px-3.5 py-3 text-[12px]">
                    <dt className="font-medium text-secondary">Gross total</dt>
                    <dd className="text-right font-semibold text-ink">
                      {activeInvoice.currency} {activeInvoice.total}
                    </dd>
                    <dt className="font-medium text-secondary">Applied payments</dt>
                    <dd className="text-right font-semibold text-ink">{activeInvoice.amount_paid}</dd>
                    <dt className="font-medium text-secondary">Credit notes</dt>
                    <dd className="text-right font-semibold text-ink">{activeInvoice.credit_total}</dd>
                    <dt className="font-medium text-secondary">Refundable credit</dt>
                    <dd className="text-right font-semibold text-ink">{activeInvoice.refundable_credit}</dd>
                    <dt className="font-medium text-secondary">Balance due</dt>
                    <dd className="text-right font-bold text-ink">{activeInvoice.balance}</dd>
                  </dl>
                  {can("visit.payer_reprice") &&
                  activeInvoice.status === "ISSUED" &&
                  activeInvoice.amount_paid === "0.00" ? (
                    <div className="grid gap-3 rounded-[14px] border border-line-soft p-3.5 sm:grid-cols-2">
                      <p className="text-[12px] font-bold uppercase tracking-wide text-muted sm:col-span-2">
                        Reprice invoice (ISSUED → ISSUED)
                      </p>
                      <Field label="New price list ID (optional)" htmlFor="reprice-price-list">
                        <TextInput
                          id="reprice-price-list"
                          value={repriceListId}
                          onChange={(event) => setRepriceListId(event.target.value)}
                          placeholder="Leave blank to use the current catalogue list"
                        />
                      </Field>
                      <div className="flex flex-wrap items-end gap-3">
                        <Button
                          variant="secondary"
                          disabled={repriceInvoice.isPending}
                          onClick={() => repriceInvoice.mutate(activeInvoice.id)}
                        >
                          {repriceInvoice.isPending ? "Repricing…" : "Reprice invoice"}
                        </Button>
                      </div>
                      {repriceResult ? (
                        <p className="text-[12px] font-medium text-ink sm:col-span-2" role="status">
                          Old {repriceResult.before_total} → new {repriceResult.after_total}
                          {" "}(difference{" "}
                          {(
                            Number(repriceResult.after_total) -
                            Number(repriceResult.before_total)
                          ).toFixed(2)}
                          ), line set {repriceResult.line_set_version}.
                        </p>
                      ) : null}
                      <p className="text-[11.5px] font-medium text-muted sm:col-span-2">
                        Prior line sets remain retained and immutable. Paid, partially paid or
                        corrected invoices are refused.
                      </p>
                    </div>
                  ) : null}
                  {can("billing.credit_note.issue") &&
                  activeInvoice.status !== "VOID" &&
                  activeInvoice.status !== "VOIDED" ? (
                    <div className="grid gap-3 rounded-[14px] border border-line-soft p-3.5 sm:grid-cols-2">
                      <p className="text-[12px] font-bold uppercase tracking-wide text-muted sm:col-span-2">
                        Issue credit note
                      </p>
                      <Field label={`Credit amount (${activeInvoice.currency})`} htmlFor="credit-amount">
                        <TextInput
                          id="credit-amount"
                          inputMode="decimal"
                          value={creditAmount}
                          onChange={(event) => setCreditAmount(event.target.value)}
                        />
                      </Field>
                      <Field label="Credit reason" htmlFor="credit-reason">
                        <TextInput
                          id="credit-reason"
                          value={creditReason}
                          onChange={(event) => setCreditReason(event.target.value)}
                        />
                      </Field>
                      <div className="sm:col-span-2 flex flex-wrap items-center gap-3">
                        <Button
                          variant="secondary"
                          disabled={
                            issueCredit.isPending ||
                            !creditAmount.trim() ||
                            !creditReason.trim()
                          }
                          onClick={() => issueCredit.mutate(activeInvoice.id)}
                        >
                          {issueCredit.isPending ? "Issuing…" : "Issue credit note"}
                        </Button>
                        {activeInvoice.refundable_credit !== "0.00" ? (
                          <Button
                            variant="link"
                            disabled
                            title="Refund issuance requires privileged MFA and is disabled."
                          >
                            Request refund — MFA required
                          </Button>
                        ) : null}
                      </div>
                    </div>
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
                              setReceiptState(null);
                              receiptTargetRef.current = null;
                              setNotice("");
                              setError("");
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
          {!focused || activeInvoice ? (
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

                  {/* Reconciliation first: a posted payment never sits beside the old form. */}
                  {activeReceipt?.data ? null : activeReceipt ? (
                    activeReceipt.loading ? (
                      <div
                        className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink"
                        role="status"
                        aria-busy="true"
                      >
                        <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
                        Payment recorded. Preparing the receipt…
                      </div>
                    ) : (
                      <div
                        className="rounded-[14px] border border-accent-orange/30 bg-accent-orange-soft px-4 py-3"
                        role="alert"
                      >
                        <p className="flex items-center gap-2 text-[12.5px] font-semibold text-ink">
                          <IconAlertTriangle className="h-[18px] w-[18px] text-accent-orange shrink-0" />
                          Payment recorded, but the receipt could not be loaded.
                        </p>
                        <p className="mt-1 text-[12px] font-medium text-secondary">
                          The payment is committed. Do not collect it again — retry the receipt for invoice{" "}
                          {activeInvoice.invoice_no}.
                        </p>
                        <Button
                          variant="secondary"
                          className="mt-3"
                          disabled={activeReceipt.loading}
                          onClick={() =>
                            void loadReceipt(
                              activeInvoice.id,
                              getAuthoritySnapshot(),
                              activeReceipt.receiptId,
                              activeReceipt.exact,
                            )
                          }
                        >
                          Retry receipt
                        </Button>
                      </div>
                    )
                  ) : activeInvoice.status === "PAID" ? (
                    <p
                      className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink"
                      role="status"
                    >
                      <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
                      This invoice is paid in full.
                    </p>
                  ) : !collectionReady ? (
                    <p
                      className="rounded-[14px] border border-line bg-surface-muted px-4 py-3 text-[12.5px] font-medium text-secondary"
                      role="status"
                      aria-busy={visitInvoice.isFetching}
                    >
                      {visitInvoice.isError
                        ? "The invoice balance could not be refreshed. Retry the invoice lookup above before collecting again."
                        : "Refreshing the invoice balance…"}
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
              ) : (
                <EmptyState
                  icon={<IconBilling className="h-5 w-5" />}
                  title="No invoice selected."
                  hint="Select an unpaid invoice, or create a new one, to collect payment."
                />
              )}
            </Card>
          ) : null}

          {activeReceipt?.data ? (
            <Card data-print-sheet className="print:border-0 print:shadow-none">
              <div className="px-5 py-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-[15px] font-bold text-ink">Receipt</h2>
                  <Button
                    variant="secondary"
                    disabled={reprintReceipt.isPending}
                    onClick={() => reprintReceipt.mutate(activeReceipt.data!.id)}
                  >
                    <IconPrinter className="h-4 w-4" />
                    {reprintReceipt.isPending ? "Preparing…" : "Print receipt"}
                  </Button>
                </div>
                <div className="mt-4 rounded-[14px] border border-line bg-white p-4 font-sans">
                  <p className="text-[13px] font-bold text-ink">{session?.organisation.name}</p>
                  <p className="mt-0.5 text-[11.5px] font-medium text-muted">{currentFacility?.name ?? ""}</p>
                  <hr className="my-3 border-line-soft" />
                  <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[12.5px]">
                    <dt className="font-medium text-secondary">Receipt no</dt>
                    <dd className="text-right font-semibold text-ink">{activeReceipt.data.receipt_no}</dd>
                    <dt className="font-medium text-secondary">Invoice</dt>
                    <dd className="text-right font-semibold text-ink">{activeReceipt.data.invoice_no}</dd>
                    <dt className="font-medium text-secondary">Patient</dt>
                    <dd className="text-right font-semibold text-ink">
                      {activeReceipt.data.patient_name} · {activeReceipt.data.patient_no}
                    </dd>
                    <dt className="font-medium text-secondary">Amount</dt>
                    <dd className="text-right font-bold text-ink">
                      {activeReceipt.data.currency} {activeReceipt.data.amount}
                    </dd>
                    <dt className="font-medium text-secondary">Method</dt>
                    <dd className="text-right font-semibold text-ink">{activeReceipt.data.method.replaceAll("_", " ")}</dd>
                    {activeReceipt.data.reference ? (
                      <>
                        <dt className="font-medium text-secondary">Reference</dt>
                        <dd className="text-right font-semibold text-ink">{activeReceipt.data.reference}</dd>
                      </>
                    ) : null}
                    <dt className="font-medium text-secondary">Invoice balance</dt>
                    <dd className="text-right font-semibold text-ink">
                      {activeReceipt.data.currency} {activeReceipt.data.invoice_balance}
                    </dd>
                  </dl>
                  <hr className="my-3 border-line-soft" />
                  <p className="text-[11px] font-medium text-muted">Thank you. This receipt was issued by KlinKlik.</p>
                </div>
                <Button
                  variant="link"
                  className="mt-3"
                  onClick={() => {
                    setReceiptState(null);
                    receiptTargetRef.current = null;
                    // The form only reopens once the confirmed balance is in
                    // hand; the prefill effect supplies it from that refresh.
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
