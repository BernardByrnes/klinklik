"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiRequestError, apiRequest, newIdempotencyKey } from "../../../lib/api";
import { isIntentActive, registerIntent, resolveIntent } from "../../../lib/intent-registry";
import { shouldRegisterIntent } from "../../../lib/recovery";
import {
  getAuthoritySnapshot,
  isCurrentAuthority,
  protectedQueryKey,
  useAuthoritySnapshot,
  useProtectedQueryKey,
  type AuthoritySnapshot,
} from "../../../lib/authority";
import { useSession } from "../../../lib/session";
import { Invoice, Patient, Receipt, Service } from "../../../features/clinic";
import type {
  CreateShiftCloseResponse,
  CreateShiftOpenResponse,
  CreateVisitCloseResponse,
  ListVisitClosureReadinessesResponse,
  RetrieveCurrentShiftResponse,
  RetrieveShiftZReportResponse,
} from "../../../generated/api-client";
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
type PaymentRequest = { invoiceId: string; path: string; key: string; body: Record<string, unknown> };

type CashierShift = CreateShiftOpenResponse;
type ClosedShiftSummary = NonNullable<RetrieveCurrentShiftResponse["last_closed_shift"]>;
type ShiftZReport = Omit<RetrieveShiftZReportResponse, "tenders"> & {
  tenders: Array<{ method: string; count: number; amount: string }>;
};

type ShiftCommand = "open" | "close";
type ShiftIntent = Readonly<{
  command: ShiftCommand;
  key: string;
  endpoint: string;
  target: string;
  body: Record<string, unknown>;
  authority: AuthoritySnapshot;
  registryId?: string;
}>;
type ShiftReconciliation = Readonly<{
  command: ShiftCommand;
  title: string;
  detail: string;
  intent: ShiftIntent;
}>;

type ClosureBlocker = ListVisitClosureReadinessesResponse["blockers"][number];
type CloseVisitRequest = {
  visitId: string;
  version: number;
  key: string;
  origin: AuthoritySnapshot;
};

function errorMessage(error: unknown) {
  if (error instanceof Error && error.message.includes("permission")) {
    return "You don't have permission to perform this action.";
  }
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function closureBlockerLabel(code: string) {
  switch (code) {
    case "ACTIVE_QUEUE_STAGE":
      return "Active queue stage";
    case "UNSIGNED_ENCOUNTER":
      return "Encounter not signed";
    case "OUTSTANDING_BALANCE":
      return "Outstanding balance";
    case "EMERGENCY_FINANCIAL_SETUP_PENDING":
      return "Emergency financial setup pending";
    default:
      return "Unresolved closure requirement";
  }
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
  const authority = useAuthoritySnapshot();
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
  // The close result is kept only when the server confirms this exact shift; a
  // failed refresh never turns it back into an unknown outcome.
  const [closeResult, setCloseResult] = useState<CashierShift | null>(null);
  const [closeConfirmation, setCloseConfirmation] = useState<ShiftIntent | null>(null);
  const [shiftReconciliation, setShiftReconciliation] = useState<ShiftReconciliation | null>(null);
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
  const [zReport, setZReport] = useState<ShiftZReport | null>(null);
  const [closureBlockers, setClosureBlockers] = useState<ClosureBlocker[]>([]);
  const [closureResult, setClosureResult] = useState<CreateVisitCloseResponse | null>(null);
  const visitCloseIntentRef = useRef<string | null>(null);
  const shiftOpenIntentRef = useRef<ShiftIntent | null>(null);
  const shiftCloseIntentRef = useRef<ShiftIntent | null>(null);
  const openPromiseRef = useRef<Promise<void> | null>(null);
  const closePromiseRef = useRef<Promise<void> | null>(null);
  const paymentKeyRef = useRef<string | null>(null);
  const paymentRequestRef = useRef<PaymentRequest | null>(null);
  const reprintIntentRef = useRef<{ receiptId: string; key: string; registryId: string } | null>(null);

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
    queryFn: () => apiRequest<RetrieveCurrentShiftResponse>("/api/v1/billing/shifts/current/"),
    enabled: can("billing.payment.record"),
  });
  const activeShift = shiftQuery.data?.shift ?? null;
  const lastClosedShift: ClosedShiftSummary | null = shiftQuery.data?.last_closed_shift ?? null;

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
  const visitClosureKey = useProtectedQueryKey(
    "visit-closure",
    activeInvoice?.visit ?? "none",
  );
  const visitClosure = useQuery({
    queryKey: visitClosureKey,
    queryFn: () =>
      apiRequest<ListVisitClosureReadinessesResponse>(
        `/api/v1/reception/visits/${activeInvoice?.visit}/closure-readiness/`,
      ),
    enabled: focused && Boolean(activeInvoice?.visit) && can("visit.close"),
    retry: false,
  });
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
  const closureTargetValid = focused && Boolean(activeInvoice?.visit) && activeInvoice?.visit === focusedVisitId;
  const readiness = visitClosure.data;
  const displayBlockers =
    closureBlockers.length > 0 ? closureBlockers : (readiness?.blockers ?? []);
  const closureState = readiness?.state;
  const closedResult = closureResult?.visit_id === activeInvoice?.visit ? closureResult : null;
  const closureTerminal =
    Boolean(closedResult) || closureState === "CLOSED" || closureState === "CANCELLED_ERROR";
  const closureBlocked =
    displayBlockers.length > 0 || Boolean(readiness && !readiness.ready && readiness.blockers.length > 0);
  const closureClear =
    readiness?.ready === true && displayBlockers.length === 0 && closureState === "OPEN";

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
    setClosureBlockers([]);
    setClosureResult(null);
    visitCloseIntentRef.current = null;
    setCloseConfirmation(null);
    setShiftReconciliation(null);
    setZReport(null);
    shiftOpenIntentRef.current = null;
    shiftCloseIntentRef.current = null;
    initializedInvoiceRef.current = null;
  }, [
    focused,
    focusedVisitId,
    currentFacility?.id,
    authority.epoch,
    authority.organisationId,
  ]);

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
    mutationFn: (request: PaymentRequest) =>
      apiRequest<{ id: string; receipt_id: string | null }>(request.path, {
        method: "POST",
        headers: { "Idempotency-Key": request.key },
        body: JSON.stringify(request.body),
      }),
    onMutate: (): PaymentContext => ({
      origin: getAuthoritySnapshot(),
      visitId: visitContextRef.current,
      paymentCount: activeInvoice?.payments?.length ?? 0,
    }),
    onSuccess: (result, request, context) => {
      // The POST committed the payment. Everything below is reconciliation:
      // a failed receipt read must never read back as a failed payment.
      paymentKeyRef.current = null;
      paymentRequestRef.current = null;
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("invoices") });
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("invoice-by-visit") });
      if (!isCurrentPaymentContext(context, request.invoiceId)) {
        // The cashier already moved on; the committed payment stays recorded
        // but nothing from this result may render on the new context.
        return;
      }
      if (context.visitId) {
        queryClient.invalidateQueries({
          queryKey: protectedQueryKey("visit-closure", context.visitId),
        });
      }
      if (focused) {
        // A new collection stays closed until the refresh for this payment has
        // returned, so a stale balance can never reopen the old form.
        setPostPaymentGate({ invoiceId: request.invoiceId, paidAt: Date.now() });
      }
      receiptTargetRef.current = request.invoiceId;
      setReceiptState({
        invoiceId: request.invoiceId,
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
        request.invoiceId,
        context.origin,
        result.receipt_id ?? null,
        context.paymentCount > 0,
      );
    },
    onError: (reason, request, context) => {
      if (!isCurrentPaymentContext(context, request.invoiceId)) return;
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  function parseShiftAmount(value: string): string | null {
    const trimmed = value.trim();
    if (!/^\d+(\.\d{1,2})?$/.test(trimmed)) return null;
    return trimmed.includes(".") ? trimmed : `${trimmed}.00`;
  }

  function reconciliationFor(
    command: ShiftCommand,
    intent: ShiftIntent,
    detail: string,
  ): ShiftReconciliation {
    return {
      command,
      title:
        command === "open"
          ? "The open command is not confirmed."
          : "The close command is not confirmed.",
      detail,
      intent,
    };
  }

  function resolveShiftIntent(intent: ShiftIntent) {
    resolveIntent(intent.registryId);
    if (intent.command === "open") shiftOpenIntentRef.current = null;
    else shiftCloseIntentRef.current = null;
  }

  function keepShiftIntent(intent: ShiftIntent): ShiftIntent {
    if (isIntentActive(intent.registryId)) return intent;
    const registryId = registerIntent({
      operation: `cashier-shift-${intent.command}`,
      target: intent.target,
      authority: intent.authority,
      retry: async () => {
        if (!isCurrentAuthority(intent.authority)) return;
        if (intent.command === "open") await runShiftOpen(intent);
        else await runShiftClose(intent);
      },
    });
    return { ...intent, registryId };
  }

  function isShiftAlreadyClosed(reason: unknown): boolean {
    return (
      reason instanceof ApiRequestError &&
      reason.status === 409 &&
      (reason.data as { code?: unknown } | null)?.code === "SHIFT_ALREADY_CLOSED"
    );
  }

  async function runShiftOpen(intent: ShiftIntent) {
    if (openPromiseRef.current) return openPromiseRef.current;
    const promise = openShift
      .mutateAsync(intent)
      .then(() => undefined)
      .catch(() => undefined)
      .finally(() => {
        if (openPromiseRef.current === promise) openPromiseRef.current = null;
      });
    openPromiseRef.current = promise;
    return promise;
  }

  async function runShiftClose(intent: ShiftIntent) {
    if (closePromiseRef.current) return closePromiseRef.current;
    const promise = closeShift
      .mutateAsync(intent)
      .then(() => undefined)
      .catch(() => undefined)
      .finally(() => {
        if (closePromiseRef.current === promise) closePromiseRef.current = null;
      });
    closePromiseRef.current = promise;
    return promise;
  }

  const openShift = useMutation({
    mutationFn: (intent: ShiftIntent) =>
      apiRequest<CreateShiftOpenResponse>(intent.endpoint, {
        method: "POST",
        headers: { "Idempotency-Key": intent.key },
        body: JSON.stringify(intent.body),
      }),
    onMutate: (intent) => ({ origin: intent.authority }),
    onSuccess: (shift, intent, context) => {
      if (!context || !isCurrentAuthority(context.origin)) {
        setShiftReconciliation(
          reconciliationFor(
            "open",
            intent,
            "The authority changed before the open was confirmed. Refresh the current shift; do not open another.",
          ),
        );
        return;
      }
      resolveShiftIntent(intent);
      setShiftReconciliation(null);
      setCloseResult(null);
      setNotice(`Shift opened with ${shift.opening_float} opening float.`);
      setError("");
      void shiftQuery.refetch();
    },
    onError: (reason, intent, context) => {
      if (!context || !isCurrentAuthority(context.origin)) {
        setShiftReconciliation(
          reconciliationFor(
            "open",
            intent,
            "The authority changed during the open. Refresh the current shift; do not open another.",
          ),
        );
      } else {
        const alreadyOpen =
          reason instanceof ApiRequestError &&
          reason.status === 409 &&
          (reason.data as { code?: unknown } | null)?.code === "SHIFT_ALREADY_OPEN";
        const kept = shouldRegisterIntent(reason) || alreadyOpen ? keepShiftIntent(intent) : intent;
        shiftOpenIntentRef.current = kept;
        setShiftReconciliation(
          reconciliationFor(
            "open",
            kept,
            alreadyOpen
              ? "The server reports an open shift. Refresh to confirm it before trying again."
              : "The open response was not confirmed. Retry this exact key or refresh the current shift; do not open another shift.",
          ),
        );
      }
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  const closeShift = useMutation({
    mutationFn: (intent: ShiftIntent) =>
      apiRequest<CreateShiftCloseResponse>(intent.endpoint, {
        method: "POST",
        headers: { "Idempotency-Key": intent.key },
        body: JSON.stringify(intent.body),
      }),
    onMutate: (intent) => ({ origin: intent.authority }),
    onSuccess: (shift, intent, context) => {
      if (!context || !isCurrentAuthority(context.origin) || shift.id !== intent.target) {
        setShiftReconciliation(
          reconciliationFor(
            "close",
            intent,
            "The returned shift does not match the confirmed close target. Refresh and reconcile before counting again.",
          ),
        );
        return;
      }
      resolveShiftIntent(intent);
      setShiftReconciliation(null);
      setCloseResult(shift);
      setNotice(
        `Shift closed. Expected ${shift.expected_cash}, counted ${shift.declared_cash}, variance ${shift.variance}.`,
      );
      setDeclaredCash("");
      setCloseReason("");
      setError("");
      void shiftQuery.refetch();
    },
    onError: (reason, intent, context) => {
      if (!context || !isCurrentAuthority(context.origin)) {
        setShiftReconciliation(
          reconciliationFor(
            "close",
            intent,
            "The authority changed during the close. Refresh the current and last closed shifts before counting again.",
          ),
        );
      } else if (isShiftAlreadyClosed(reason)) {
        setShiftReconciliation(
          reconciliationFor(
            "close",
            intent,
            "The server reports this exact shift is already closed. Refresh to confirm; no second close was sent.",
          ),
        );
      } else {
        const kept = shouldRegisterIntent(reason) ? keepShiftIntent(intent) : intent;
        shiftCloseIntentRef.current = kept;
        setShiftReconciliation(
          reconciliationFor(
            "close",
            kept,
            shouldRegisterIntent(reason)
              ? "The close response was not confirmed. Retry this exact key or refresh; the declared amount is retained."
              : `The close was refused: ${errorMessage(reason)}`,
          ),
        );
      }
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  function startOpen(amountOverride?: string) {
    if (!currentFacility?.id) {
      setError("Select a facility before opening a shift.");
      return;
    }
    const amount = parseShiftAmount(amountOverride ?? openingFloat ?? "0.00");
    if (!amount) {
      setError("Enter a non-negative opening float with at most two decimals.");
      return;
    }
    if (openPromiseRef.current || shiftOpenIntentRef.current || activeShift) return;
    const intent: ShiftIntent = {
      command: "open",
      key: newIdempotencyKey("s40-shift-open"),
      endpoint: "/api/v1/billing/shifts/open/",
      target: currentFacility.id,
      body: { opening_float: amount },
      authority: getAuthoritySnapshot(),
    };
    shiftOpenIntentRef.current = intent;
    setNotice("");
    setError("");
    setShiftReconciliation(null);
    void runShiftOpen(intent);
  }

  function reviewClose() {
    if (!activeShift || closePromiseRef.current || shiftCloseIntentRef.current) return;
    const amount = parseShiftAmount(declaredCash);
    if (!amount) {
      setError("Enter the counted cash before reviewing the close.");
      return;
    }
    const intent: ShiftIntent = {
      command: "close",
      key: newIdempotencyKey("s40-shift-close"),
      endpoint: `/api/v1/billing/shifts/${activeShift.id}/close/`,
      target: activeShift.id,
      body: {
        declared_cash: amount,
        ...(closeReason.trim() ? { reason: closeReason.trim() } : {}),
      },
      authority: getAuthoritySnapshot(),
    };
    setNotice("");
    setError("");
    setCloseConfirmation(intent);
  }

  function confirmClose() {
    if (!closeConfirmation || closePromiseRef.current || shiftCloseIntentRef.current) return;
    const intent = closeConfirmation;
    shiftCloseIntentRef.current = intent;
    setCloseConfirmation(null);
    void runShiftClose(intent);
  }

  async function reconcileShiftFromRead() {
    const intent =
      shiftReconciliation?.intent ??
      shiftCloseIntentRef.current ??
      shiftOpenIntentRef.current;
    if (!intent) {
      void shiftQuery.refetch();
      return;
    }
    const result = await shiftQuery.refetch();
    const data = result.data;
    if (!data) return;
    if (intent.command === "open" && data.shift) {
      resolveShiftIntent(intent);
      setShiftReconciliation(null);
      setNotice("The server confirmed the open shift. No second open was sent.");
      setError("");
      return;
    }
    if (
      intent.command === "close" &&
      data.shift === null &&
      data.last_closed_shift?.id === intent.target
    ) {
      resolveShiftIntent(intent);
      setShiftReconciliation(null);
      setNotice("The server confirmed this exact closed shift. No second close was sent.");
      setError("");
      return;
    }
    setShiftReconciliation(
      reconciliationFor(
        intent.command,
        intent,
        "The exact command is still unconfirmed. Retry it with the same key or refresh again.",
      ),
    );
  }

  function retryShiftIntent() {
    const intent = shiftReconciliation?.intent;
    if (!intent || !isCurrentAuthority(intent.authority)) return;
    if (intent.command === "open") void runShiftOpen(intent);
    else void runShiftClose(intent);
  }

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
    mutationFn: (input: { receiptId: string; key: string }) =>
      apiRequest(`/api/v1/billing/receipts/${input.receiptId}/reprint/`, {
        method: "POST",
        headers: { "Idempotency-Key": input.key },
        body: JSON.stringify({}),
      }),
    onMutate: () => getAuthoritySnapshot(),
    onSuccess: () => {
      resolveIntent(reprintIntentRef.current?.registryId);
      reprintIntentRef.current = null;
      setNotice((current) => current ? current : "Receipt reprint recorded.");
      window.print();
    },
    onError: (reason, input, authority) => {
      if (!shouldRegisterIntent(reason)) {
        resolveIntent(reprintIntentRef.current?.registryId);
        reprintIntentRef.current = null;
      } else {
        if (!isIntentActive(reprintIntentRef.current?.registryId)) reprintIntentRef.current = null;
        const registryId = registerIntent({
          operation: "receipt-reprint",
          target: "receipt",
          authority,
          retry: async () => {
            if (!authority || !isCurrentAuthority(authority)) return;
            await reprintReceipt.mutateAsync(input).catch(() => undefined);
          },
        });
        reprintIntentRef.current = { ...input, registryId };
      }
      setError(errorMessage(reason));
    },
  });

  const startReprint = (receiptId: string) => {
    const input = { receiptId, key: newIdempotencyKey("s05-reprint") };
    setError("");
    reprintReceipt.mutate(input);
  };

  const submitPayment = () => {
    if (!activeInvoice) return;
    const key = paymentKeyRef.current ?? newIdempotencyKey("s05-payment");
    paymentKeyRef.current = key;
    const request: PaymentRequest = {
      invoiceId: activeInvoice.id,
      key,
      path: activeShift
        ? `/api/v1/billing/invoices/${activeInvoice.id}/payments/`
        : `/api/v1/billing/invoices/${activeInvoice.id}/pay/`,
      body: {
        amount: paymentAmount,
        method,
        ...(reference.trim() ? { reference: reference.trim() } : {}),
      },
    };
    paymentRequestRef.current = request;
    setError("");
    pay.mutate(request);
  };

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
      apiRequest<ShiftZReport>(`/api/v1/billing/shifts/${shiftId}/z-report/`),
    onSuccess: (report) => {
      setZReport(report);
      setError("");
    },
    onError: (reason) => setError(errorMessage(reason)),
  });

  function buildCloseRequest(): CloseVisitRequest | null {
    const visitId = activeInvoice?.visit;
    const version = visitClosure.data?.version;
    if (!visitId || visitId !== focusedVisitId || !version) return null;
    return {
      visitId,
      version,
      key: newIdempotencyKey("s08-close"),
      origin: getAuthoritySnapshot(),
    };
  }

  const closeVisit = useMutation({
    mutationFn: (request: CloseVisitRequest) =>
      apiRequest<CreateVisitCloseResponse>(
        `/api/v1/reception/visits/${request.visitId}/close/`,
        {
          method: "POST",
          headers: { "Idempotency-Key": request.key },
          body: JSON.stringify({ expected_version: request.version }),
        },
      ),
    onSuccess: (result, request) => {
      if (!isCurrentAuthority(request.origin) || visitContextRef.current !== request.visitId) {
        return;
      }
      setClosureResult(result);
      setClosureBlockers([]);
      setNotice(`Visit closed (${result.closure_reason}).`);
      setError("");
      resolveIntent(visitCloseIntentRef.current);
      visitCloseIntentRef.current = null;
      queryClient.invalidateQueries({
        queryKey: protectedQueryKey("visit-closure", request.visitId),
      });
    },
    onError: (reason, request) => {
      if (!isCurrentAuthority(request.origin) || visitContextRef.current !== request.visitId) {
        return;
      }
      setNotice("");
      if (reason instanceof ApiRequestError) {
        const body = reason.data as { blockers?: ClosureBlocker[] };
        setClosureBlockers(body.blockers ?? []);
        queryClient.invalidateQueries({
          queryKey: protectedQueryKey("visit-closure", request.visitId),
        });
      } else {
        setClosureBlockers([]);
      }
      if (!isIntentActive(visitCloseIntentRef.current)) visitCloseIntentRef.current = null;
      if (!shouldRegisterIntent(reason)) {
        resolveIntent(visitCloseIntentRef.current);
        visitCloseIntentRef.current = null;
      } else if (!visitCloseIntentRef.current) {
        visitCloseIntentRef.current = registerIntent({
          operation: "visit-close",
          target: request.visitId,
          authority: request.origin,
          retry: async () => {
            if (!isCurrentAuthority(request.origin)) return;
            await closeVisit.mutateAsync(request).catch(() => undefined);
          },
        });
      }
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

      {canRecordPayment ? (
        <Card>
          <CardTitleBar title="Cashier shift" />
          <div className="px-5 py-4 space-y-3">
            {shiftQuery.isLoading ? (
              <p className="text-[12.5px] font-medium text-secondary" role="status" aria-busy="true">
                Loading the current and last closed shifts…
              </p>
            ) : shiftQuery.isError ? (
              <div className="rounded-[12px] border border-accent-orange/30 bg-accent-orange-soft px-3.5 py-3" role="alert">
                <p className="text-[12.5px] font-semibold text-ink">
                  The current and last closed shifts could not be loaded.
                </p>
                <p className="mt-1 text-[12px] font-medium text-secondary">
                  No new shift command has been sent. Payments stay unavailable until this read succeeds.
                </p>
                <Button
                  variant="secondary"
                  className="mt-2"
                  disabled={shiftQuery.isFetching}
                  onClick={() => void shiftQuery.refetch()}
                >
                  {shiftQuery.isFetching ? "Refreshing…" : "Retry shift read"}
                </Button>
              </div>
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
                  disabled={closeShift.isPending || Boolean(closePromiseRef.current) || !declaredCash.trim()}
                  onClick={reviewClose}
                >
                  Review close
                </Button>
                <p className="text-[11.5px] font-medium text-muted">
                  Expected cash and variance are shown only after your blind count is committed.
                </p>
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
                  <Button
                    disabled={openShift.isPending || Boolean(openPromiseRef.current)}
                    onClick={() => startOpen()}
                  >
                    {openShift.isPending ? "Opening…" : "Open shift"}
                  </Button>
                </div>
              </>
            )}

            {closeConfirmation && activeShift?.id === closeConfirmation.target ? (
              <div className="rounded-[12px] border border-line bg-surface-muted px-3.5 py-3" data-confirm-close>
                <p className="text-[12.5px] font-bold text-ink">Confirm blind close</p>
                <p className="mt-1 text-[12.5px] font-medium text-secondary">
                  You are closing shift {closeConfirmation.target.slice(0, 8)}. Declared cash{" "}
                  <span className="font-bold text-ink">{String(closeConfirmation.body.declared_cash)}</span>.
                  Expected cash is not shown until the close is committed.
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    disabled={closeShift.isPending || Boolean(closePromiseRef.current)}
                    onClick={confirmClose}
                  >
                    {closeShift.isPending ? "Closing…" : "Confirm close"}
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={closeShift.isPending}
                    onClick={() => {
                      setCloseConfirmation(null);
                      shiftCloseIntentRef.current = null;
                      setError("");
                    }}
                  >
                    Cancel close
                  </Button>
                </div>
              </div>
            ) : null}

            {shiftReconciliation ? (
              <div
                className="rounded-[12px] border border-accent-orange/30 bg-accent-orange-soft px-3.5 py-3"
                role="alert"
                data-shift-reconciliation
              >
                <p className="text-[12.5px] font-bold text-ink">{shiftReconciliation.title}</p>
                <p className="mt-1 text-[12px] font-medium text-secondary">
                  {shiftReconciliation.detail}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    disabled={shiftQuery.isFetching}
                    onClick={() => void reconcileShiftFromRead()}
                  >
                    {shiftQuery.isFetching ? "Refreshing…" : "Refresh shift state"}
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={
                      !isCurrentAuthority(shiftReconciliation.intent.authority) ||
                      (shiftReconciliation.command === "open"
                        ? openShift.isPending || Boolean(openPromiseRef.current)
                        : closeShift.isPending || Boolean(closePromiseRef.current))
                    }
                    onClick={retryShiftIntent}
                  >
                    Retry exact {shiftReconciliation.command}
                  </Button>
                </div>
              </div>
            ) : null}

            {!closeConfirmation && !shiftReconciliation && lastClosedShift ? (
              <div
                className="rounded-[12px] border border-line-soft bg-surface-muted px-3.5 py-3"
                data-last-closed-shift
              >
                <p className="text-[12px] font-bold uppercase tracking-wide text-muted">
                  Previous shift (closed) — not the active drawer
                </p>
                <p className="mt-1 text-[12.5px] font-semibold text-ink">
                  Shift {lastClosedShift.id.slice(0, 8)} · closed{" "}
                  {lastClosedShift.closed_at ? formatDate(lastClosedShift.closed_at) : "—"}
                </p>
                <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[12px]">
                  <dt className="font-medium text-secondary">Declared cash</dt>
                  <dd className="text-right font-semibold text-ink">
                    {lastClosedShift.declared_cash ?? "—"}
                  </dd>
                  <dt className="font-medium text-secondary">Expected cash</dt>
                  <dd className="text-right font-semibold text-ink">
                    {lastClosedShift.expected_cash ?? "—"}
                  </dd>
                  <dt className="font-medium text-secondary">Variance</dt>
                  <dd className="text-right font-semibold text-ink">
                    {lastClosedShift.variance ?? "—"}
                  </dd>
                  {lastClosedShift.close_reason ? (
                    <>
                      <dt className="font-medium text-secondary">Reason</dt>
                      <dd className="text-right font-medium text-ink">
                        {lastClosedShift.close_reason}
                      </dd>
                    </>
                  ) : null}
                </dl>
                <Button
                  variant="link"
                  className="mt-2"
                  disabled={loadZReport.isPending}
                  onClick={() => loadZReport.mutate(lastClosedShift.id)}
                >
                  {loadZReport.isPending ? "Loading Z-report…" : "Load Z-report"}
                </Button>
              </div>
            ) : null}

            {closeResult ? (
              <div className="space-y-2">
                <p className="rounded-[12px] bg-accent-teal-soft px-3.5 py-2.5 text-[12px] font-medium text-ink" role="status">
                  Closed shift {closeResult.id.slice(0, 8)}: expected {closeResult.expected_cash},
                  declared {closeResult.declared_cash}, variance {closeResult.variance}.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="link"
                    disabled={loadZReport.isPending}
                    onClick={() => loadZReport.mutate(closeResult.id)}
                  >
                    {loadZReport.isPending ? "Loading Z-report…" : "Load Z-report"}
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={shiftQuery.isFetching || openShift.isPending || Boolean(openPromiseRef.current)}
                    onClick={() => startOpen("0.00")}
                  >
                    Open next shift
                  </Button>
                </div>
                {shiftQuery.isError ? (
                  <p className="text-[11.5px] font-medium text-secondary" role="status">
                    The committed close above is still shown; the refresh failed and no close POST was retried.
                  </p>
                ) : null}
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
                        <Button disabled={pay.isPending} onClick={submitPayment}>
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
                    onClick={() => startReprint(activeReceipt.data!.id)}
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

      {closureTargetValid && can("visit.close") ? (
        <Card>
          <CardTitleBar title="Visit closure" />
          <div className="px-5 py-4 space-y-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[12.5px] font-medium text-secondary">
                Checklist for Visit {focusedVisitId?.slice(0, 8)}
              </p>
              <Button
                variant="small-secondary"
                disabled={visitClosure.isFetching}
                onClick={() => void visitClosure.refetch()}
              >
                {visitClosure.isFetching ? "Refreshing…" : "Refresh checklist"}
              </Button>
            </div>
            {visitClosure.isLoading ? (
              <p className="text-[12.5px] font-medium text-secondary" role="status" aria-busy="true">
                Loading the closure checklist…
              </p>
            ) : visitClosure.isError || !readiness ? (
              <p className="text-[12.5px] font-medium text-ink" role="alert">
                The Visit checklist could not be loaded. Refresh to try again.
              </p>
            ) : closureTerminal ? (
              <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink" role="status">
                <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
                {closureState === "CANCELLED_ERROR"
                  ? "Visit CANCELLED_ERROR — this Visit cannot be closed. Its history remains readable."
                  : `Visit CLOSED — ${closedResult?.closure_reason ?? readiness.closure_reason}. History remains readable; new ordinary records are refused.`}
              </p>
            ) : !closureClear && !closureBlocked ? (
              <p className="rounded-[14px] border border-line-soft px-4 py-3 text-[12.5px] font-medium text-ink" role="alert">
                The Visit closure state could not be confirmed. Refresh before trying again.
              </p>
            ) : (
              <>
                <p className="text-[12.5px] font-medium text-secondary">
                  {closureBlocked
                    ? "Closure is refused until every item below is resolved."
                    : "All known closure blockers are clear. The server rechecks on confirmation."}
                </p>
                <Button
                  disabled={closeVisit.isPending || closureBlocked}
                  onClick={() => {
                    const request = buildCloseRequest();
                    if (!request) {
                      setError("Refresh the Visit closure checklist before confirming.");
                      return;
                    }
                    closeVisit.mutate(request);
                  }}
                >
                  {closeVisit.isPending ? "Checking…" : "Close visit"}
                </Button>
                {displayBlockers.length ? (
                  <ul className="space-y-1.5 rounded-[14px] border border-line-soft p-3.5" role="alert">
                    {displayBlockers.map((blocker, index) => (
                      <li key={`${blocker.code}-${index}`} className="text-[12.5px] font-medium text-ink">
                        <span className="font-bold">{closureBlockerLabel(blocker.code)}</span>
                        {blocker.queue_type ? ` · queue ${blocker.queue_type} ${blocker.state ?? ""}` : ""}
                        {blocker.invoice_no ? ` · invoice ${blocker.invoice_no} ${blocker.amount ?? ""}` : ""}
                        {blocker.clinician_id ? ` · clinician ${blocker.clinician_id.slice(0, 8)}` : ""}
                        {blocker.action ? ` · ${blocker.action}` : ""}
                        {blocker.code === "OUTSTANDING_BALANCE" && focusedVisitId ? (
                          <Link
                            href={`/billing?visit=${focusedVisitId}`}
                            className="ml-2 font-semibold text-primary-text underline"
                          >
                            Review balance
                          </Link>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </>
            )}
          </div>
        </Card>
      ) : null}
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
