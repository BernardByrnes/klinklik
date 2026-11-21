"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiRequestError, apiRequest, newIdempotencyKey } from "../../../lib/api";
import {
  getAuthoritySnapshot,
  isCurrentAuthority,
  protectedQueryKey,
  useProtectedQueryKey,
} from "../../../lib/authority";
import { useConnectivity } from "../../../lib/connectivity";
import { isIntentActive, registerIntent, resolveIntent } from "../../../lib/intent-registry";
import { shouldRegisterIntent } from "../../../lib/recovery";
import { useSession } from "../../../lib/session";
import { IconBilling, IconCheckCircle } from "../../../components/icons";
import CatalogueImportPanel from "../../../features/inventory/CatalogueImportPanel";
import {
  Button,
  Card,
  CardTitleBar,
  EmptyState,
  ErrorBanner,
  PageHeader,
  Select,
  StatusBadge,
  TextInput,
  UnauthorisedState,
  formatDate,
} from "../../../components/ui";

type CountOpenRequest = { key: string; locationId: string };
type CountSubmitRequest = {
  key: string;
  sheetId: string;
  expectedVersion: number;
  lines: Array<{ line_id: string; counted_qty: string }>;
};
type CountApproveRequest = { key: string; sheetId: string; expectedVersion: number };
type Location = { id: string; code: string; name: string; is_default: boolean; active: boolean };
type Product = { id: string; code: string; generic_name: string; brand_name: string; strength: string };

type StockRow = {
  product_id: string;
  code: string;
  generic_name: string;
  strength: string;
  usable_quantity: string;
  expired_quantity: string;
  quarantined_quantity: string;
  total_quantity: string;
  batch_count: number;
  earliest_expiry: string | null;
  status: string;
  by_location_name: Record<string, string>;
  reorder_level: string | null;
};

type BatchRow = {
  id: string;
  batch_no: string;
  expiry_date: string;
  status: string;
  locations: Array<{ location_id: string; location_name: string; quantity: string }>;
};

type MovementRow = {
  id: string;
  batch_no: string;
  movement_type: string;
  quantity: string;
  location_name: string;
  occurred_at: string;
};

type ReceiptRow = { batchNo: string; expiryDate: string; quantity: string };
type ReceiptIntent = {
  key: string;
  body: {
    receipt_no: string;
    supplier_name: string;
    lines: Array<{
      product_id: string;
      location_id: string;
      batch_no: string;
      expiry_date: string;
      quantity: string;
    }>;
  };
};

type CountLine = {
  id: string;
  product_name: string;
  strength: string;
  batch_no: string;
  expiry_date: string;
  counted_qty: string | null;
  expected_qty?: string;
  variance_qty?: string | null;
};

type CountSheet = {
  id: string;
  state: string;
  version: number;
  blind: boolean;
  location_name?: string;
  submitted_by_name?: string;
  lines: CountLine[];
  movements_during_count: Array<{
    id: string;
    movement_type: string;
    quantity: string;
    occurred_at: string;
  }>;
};

type CountListRow = {
  id: string;
  location_id: string;
  location_name: string;
  state: string;
  version: number;
  submitted_by_name: string | null;
  submitted_at: string | null;
  line_count: number;
};

function errorMessage(error: unknown) {
  if (error instanceof ApiRequestError) {
    const body = error.data as { detail?: string };
    if (body?.detail) return body.detail;
  }
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function statusTone(status: string) {
  if (status === "OUT" || status === "EXPIRED") return "pink" as const;
  if (status === "LOW" || status === "EXPIRING_SOON") return "amber" as const;
  return "teal" as const;
}

const emptyReceiptRow = (): ReceiptRow => ({ batchNo: "", expiryDate: "", quantity: "" });

export default function InventoryPage() {
  const online = useConnectivity().online;
  const { can } = useSession();
  const queryClient = useQueryClient();
  const inventoryIntentRefs = useRef<Record<string, string>>({});
  const [search, setSearch] = useState("");
  const [locationId, setLocationId] = useState("");
  const [productId, setProductId] = useState("");
  const [expandedProduct, setExpandedProduct] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [receiptRows, setReceiptRows] = useState<ReceiptRow[]>([emptyReceiptRow()]);
  const [supplierName, setSupplierName] = useState("");
  const [pendingReceipt, setPendingReceipt] = useState<ReceiptIntent | null>(null);
  const [countSheet, setCountSheet] = useState<CountSheet | null>(null);
  const [countValues, setCountValues] = useState<Record<string, string>>({});
  const [countValidationFailed, setCountValidationFailed] = useState(false);
  const [reviewCountId, setReviewCountId] = useState<string | null>(null);
  const [countRefreshFailed, setCountRefreshFailed] = useState(false);
  const openedCountIdRef = useRef<string | null>(null);
  const approvedCountIdRef = useRef<string | null>(null);

  const stockKey = useProtectedQueryKey("inventory-stock", search, locationId);
  const stock = useQuery({
    queryKey: stockKey,
    queryFn: () =>
      apiRequest<StockRow[]>(
        `/api/v1/inventory/stock/?q=${encodeURIComponent(search)}${locationId ? `&location_id=${locationId}` : ""}`,
      ),
    enabled: can("inventory.read"),
  });
  const locations = useQuery({
    queryKey: useProtectedQueryKey("inventory-locations"),
    queryFn: () => apiRequest<Location[]>("/api/v1/inventory/locations/"),
    enabled: can("inventory.read"),
  });
  const products = useQuery({
    queryKey: useProtectedQueryKey("inventory-products"),
    queryFn: () => apiRequest<Product[]>("/api/v1/inventory/products/"),
    enabled: can("inventory.read"),
  });
  const movementsKey = useProtectedQueryKey("inventory-movements", dateFrom, dateTo, locationId);
  const movements = useQuery({
    queryKey: movementsKey,
    queryFn: () => {
      const params = new URLSearchParams();
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      if (locationId) params.set("location_id", locationId);
      const suffix = params.toString();
      return apiRequest<MovementRow[]>(`/api/v1/inventory/movements/${suffix ? `?${suffix}` : ""}`);
    },
    enabled: can("inventory.read"),
  });
  const batches = useQuery({
    queryKey: useProtectedQueryKey("inventory-batches", expandedProduct ?? "", locationId),
    queryFn: () => {
      const params = new URLSearchParams();
      if (expandedProduct) params.set("product_id", expandedProduct);
      if (locationId) params.set("location_id", locationId);
      return apiRequest<BatchRow[]>(`/api/v1/inventory/batches/?${params.toString()}`);
    },
    enabled: can("inventory.read") && Boolean(expandedProduct),
  });
  const countList = useQuery({
    queryKey: useProtectedQueryKey("inventory-count-list"),
    queryFn: async () => {
      const payload = await apiRequest<{ counts: CountListRow[] }>("/api/v1/inventory/counts/");
      return payload.counts;
    },
    enabled: can("inventory.read") && can("inventory.approve"),
  });
  const reviewDetail = useQuery({
    queryKey: useProtectedQueryKey("inventory-count-review", reviewCountId ?? ""),
    queryFn: () =>
      apiRequest<CountSheet>(
        `/api/v1/inventory/counts/${reviewCountId}/?reveal=1`,
      ),
    enabled: Boolean(reviewCountId) && can("inventory.approve"),
  });

  const refreshInventory = () => {
    void queryClient.invalidateQueries({ queryKey: protectedQueryKey("inventory-stock") });
    void queryClient.invalidateQueries({ queryKey: protectedQueryKey("inventory-movements") });
    void queryClient.invalidateQueries({ queryKey: protectedQueryKey("inventory-batches") });
    void queryClient.invalidateQueries({ queryKey: protectedQueryKey("inventory-count-list") });
  };

  const defaultLocation =
    locations.data?.find((item) => item.is_default)?.id ?? locations.data?.[0]?.id ?? "";

  const registerInventoryIntent = (
    operation: string,
    authority: ReturnType<typeof getAuthoritySnapshot> | undefined,
    retry: () => Promise<void>,
  ) => {
    if (!isIntentActive(inventoryIntentRefs.current[operation])) {
      delete inventoryIntentRefs.current[operation];
    }
    inventoryIntentRefs.current[operation] = registerIntent({
      operation,
      target: "inventory-workbench",
      authority,
      retry,
    });
  };
  const resolveInventoryIntent = (operation: string) => {
    resolveIntent(inventoryIntentRefs.current[operation]);
    delete inventoryIntentRefs.current[operation];
  };

  const receive = useMutation({
    mutationFn: (intent: ReceiptIntent) =>
      apiRequest<{ receipt_no: string; warning_near_expiry: boolean }>(
        "/api/v1/inventory/receipts/",
        {
          method: "POST",
          headers: { "Idempotency-Key": intent.key },
          body: JSON.stringify(intent.body),
        },
      ),
    onMutate: () => getAuthoritySnapshot(),
    onSuccess: (result) => {
      resolveInventoryIntent("inventory-receipt");
      setNotice(
        result.warning_near_expiry
          ? `Stock received on ${result.receipt_no}. Expiry is inside the 90-day warning horizon.`
          : `Stock received on ${result.receipt_no}.`,
      );
      setError("");
      setPendingReceipt(null);
      setReceiptRows([emptyReceiptRow()]);
      refreshInventory();
    },
    onError: (reason, intent, authority) => {
      setNotice("");
      if (!shouldRegisterIntent(reason)) {
        resolveInventoryIntent("inventory-receipt");
        setPendingReceipt(null);
        setError(errorMessage(reason));
        refreshInventory();
        return;
      }
      registerInventoryIntent("inventory-receipt", authority, async () => {
        if (!authority || !isCurrentAuthority(authority)) return;
        await receive.mutateAsync(intent).catch(() => undefined);
      });
      setError("The receipt outcome is uncertain. Retry the same receipt; do not post a new one.");
    },
  });

  const confirmReceipt = () => {
    const resolvedLocation = locationId || defaultLocation;
    if (!productId || !resolvedLocation || receiptRows.some((row) => !row.batchNo.trim() || !row.expiryDate || !row.quantity.trim())) {
      setError("Complete every reviewed receipt line before posting.");
      return;
    }
    const intent: ReceiptIntent = {
      key: newIdempotencyKey("inventory-receipt"),
      body: {
        receipt_no: `GRN-${Date.now()}`,
        supplier_name: supplierName.trim(),
        lines: receiptRows.map((row) => ({
          product_id: productId,
          location_id: resolvedLocation,
          batch_no: row.batchNo.trim(),
          expiry_date: row.expiryDate,
          quantity: row.quantity.trim(),
        })),
      },
    };
    setPendingReceipt(intent);
    setError("");
    receive.mutate(intent);
  };

  const startCountOpen = () => {
    const request: CountOpenRequest = {
      key: newIdempotencyKey("inventory-count-open"),
      locationId: locationId || defaultLocation,
    };
    setError("");
    openCount.mutate(request);
  };

  const submitCountSheet = () => {
    if (!countSheet) {
      setError("Open a count first.");
      return;
    }
    const lines = countSheet.lines.map((line) => ({
      line_id: line.id,
      counted_qty: (countValues[line.id] ?? "").trim(),
    }));
    if (lines.some((line) => !/^\d+(\.\d{1,2})?$/.test(line.counted_qty))) {
      setCountValidationFailed(true);
      setError("Enter a counted quantity for every line before submitting.");
      return;
    }
    setCountValidationFailed(false);
    setError("");
    submitCount.mutate({
      key: newIdempotencyKey("inventory-count-submit"),
      sheetId: countSheet.id,
      expectedVersion: countSheet.version,
      lines,
    });
  };

  const approveCountSheet = () => {
    if (!countSheet) {
      setError("Submit a count first.");
      return;
    }
    setError("");
    approveCount.mutate({
      key: newIdempotencyKey("inventory-count-approve"),
      sheetId: countSheet.id,
      expectedVersion: countSheet.version,
    });
  };

  const openCount = useMutation({
    mutationFn: async (request: CountOpenRequest) => {
      const opened = await apiRequest<{ id: string }>("/api/v1/inventory/counts/open/", {
        method: "POST",
        headers: { "Idempotency-Key": request.key },
        body: JSON.stringify({ location_id: request.locationId }),
      });
      openedCountIdRef.current = opened.id;
      return apiRequest<CountSheet>(`/api/v1/inventory/counts/${opened.id}/`);
    },
    onMutate: () => getAuthoritySnapshot(),
    onSuccess: (sheet) => {
      resolveInventoryIntent("inventory-count-open");
      openedCountIdRef.current = null;
      setCountRefreshFailed(false);
      setCountSheet(sheet);
      setCountValues(Object.fromEntries(sheet.lines.map((line) => [line.id, line.counted_qty ?? ""])));
      setCountValidationFailed(false);
      setNotice("Blind count opened. Enter the observed quantities.");
      setError("");
      refreshInventory();
    },
    onError: (reason, request, authority) => {
      setNotice("");
      if (openedCountIdRef.current) {
        resolveInventoryIntent("inventory-count-open");
        setCountRefreshFailed(true);
        setError("The count opened but its sheet could not be refreshed. Retry the refresh only.");
        return;
      }
      if (!shouldRegisterIntent(reason)) resolveInventoryIntent("inventory-count-open");
      else {
        registerInventoryIntent("inventory-count-open", authority, async () => {
          if (!authority || !isCurrentAuthority(authority)) return;
          await openCount.mutateAsync(request).catch(() => undefined);
        });
      }
      setError(errorMessage(reason));
    },
  });

  const submitCount = useMutation({
    mutationFn: (request: CountSubmitRequest) =>
      apiRequest<{ id: string; state: string; version: number }>(
        `/api/v1/inventory/counts/${request.sheetId}/submit/`,
        {
          method: "POST",
          headers: { "Idempotency-Key": request.key },
          body: JSON.stringify({
            expected_version: request.expectedVersion,
            lines: request.lines,
          }),
        },
      ),
    onMutate: () => getAuthoritySnapshot(),
    onSuccess: (result) => {
      resolveInventoryIntent("inventory-count-submit");
      setCountSheet((current) =>
        current ? { ...current, state: result.state, version: result.version } : current,
      );
      setCountValidationFailed(false);
      setNotice("Count submitted. A separate approver posts the exact variances.");
      setError("");
      refreshInventory();
    },
    onError: (reason, request, authority) => {
      setNotice("");
      if (!shouldRegisterIntent(reason)) resolveInventoryIntent("inventory-count-submit");
      else {
        registerInventoryIntent("inventory-count-submit", authority, async () => {
          if (!authority || !isCurrentAuthority(authority)) return;
          await submitCount.mutateAsync(request).catch(() => undefined);
        });
      }
      setError(errorMessage(reason));
    },
  });

  const approveCount = useMutation({
    mutationFn: async (request: CountApproveRequest) => {
      const approved = await apiRequest<{ id: string; state: string; version: number }>(
        `/api/v1/inventory/counts/${request.sheetId}/approve/`,
        {
          method: "POST",
          headers: { "Idempotency-Key": request.key },
          body: JSON.stringify({ expected_version: request.expectedVersion }),
        },
      );
      approvedCountIdRef.current = approved.id;
      return apiRequest<CountSheet>(`/api/v1/inventory/counts/${approved.id}/?reveal=1`);
    },
    onMutate: () => getAuthoritySnapshot(),
    onSuccess: (sheet) => {
      resolveInventoryIntent("inventory-count-approve");
      approvedCountIdRef.current = null;
      setCountRefreshFailed(false);
      setCountSheet(sheet);
      setNotice("Stock count approved. Counter-movements were posted.");
      setError("");
      refreshInventory();
    },
    onError: (reason, request, authority) => {
      setNotice("");
      if (approvedCountIdRef.current) {
        resolveInventoryIntent("inventory-count-approve");
        setCountRefreshFailed(true);
        setError("The count was approved but its sheet could not be refreshed. Retry the refresh only.");
        return;
      }
      if (!shouldRegisterIntent(reason)) resolveInventoryIntent("inventory-count-approve");
      else {
        registerInventoryIntent("inventory-count-approve", authority, async () => {
          if (!authority || !isCurrentAuthority(authority)) return;
          await approveCount.mutateAsync(request).catch(() => undefined);
        });
      }
      setError(errorMessage(reason));
    },
  });

  const refreshCountSheet = useMutation({
    mutationFn: (id: string) =>
      apiRequest<CountSheet>(
        `/api/v1/inventory/counts/${id}/${approvedCountIdRef.current === id ? "?reveal=1" : ""}`,
      ),
    onSuccess: (sheet) => {
      setCountSheet(sheet);
      setCountValues(
        Object.fromEntries(sheet.lines.map((line) => [line.id, line.counted_qty ?? ""])),
      );
      setCountRefreshFailed(false);
      setError("");
      setNotice("Count sheet refreshed.");
    },
    onError: (reason) => setError(errorMessage(reason)),
  });

  if (!can("inventory.read")) {
    return <UnauthorisedState capability="inventory.read" />;
  }

  return (
    <>
      <PageHeader
        title="Inventory"
        subtitle="Receive, inspect, count and independently review stock in one workbench."
      />
      {notice ? (
        <p role="status" className="rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">
          {notice}
        </p>
      ) : null}
      {error ? <ErrorBanner message={error} onDismiss={() => setError("")} /> : null}

      <div className="grid gap-5">
        <Card>
          <CardTitleBar title="Stock on hand" />
          <div className="grid gap-3 px-5 py-4 md:grid-cols-3">
            <TextInput value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search product or code…" aria-label="Search stock" />
            <Select aria-label="Stock location" value={locationId} onChange={(event) => setLocationId(event.target.value)}>
              <option value="">All locations</option>
              {(locations.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </Select>
            <div className="flex gap-2">
              <TextInput type="date" aria-label="Movement from" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
              <TextInput type="date" aria-label="Movement to" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
            </div>
          </div>
          {stock.isLoading ? (
            <p className="px-5 pb-4 text-[12.5px] text-secondary" role="status" aria-busy="true">Loading stock…</p>
          ) : stock.isError ? (
            <p className="px-5 pb-4 text-[12.5px] text-ink" role="alert">Stock could not be loaded.</p>
          ) : !stock.data?.length ? (
            <p className="px-5 pb-4 text-[12.5px] text-secondary">No stock matches this filter.</p>
          ) : (
            <ul className="divide-y divide-line-soft px-5 pb-4">
              {stock.data.map((row) => (
                <li key={row.product_id} className="py-3 text-[12.5px]">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-ink">{row.generic_name} {row.strength} · {row.code}</span>
                    <StatusBadge tone={statusTone(row.status)}>{row.status}</StatusBadge>
                  </div>
                  <p className="mt-1 text-secondary">
                    Usable {row.usable_quantity} · expired {row.expired_quantity} · quarantined {row.quarantined_quantity} · total {row.total_quantity} · {row.batch_count} batch(es)
                  </p>
                  <Button variant="link" onClick={() => setExpandedProduct(expandedProduct === row.product_id ? null : row.product_id)}>
                    {expandedProduct === row.product_id ? "Hide batches" : "View batches"}
                  </Button>
                  {expandedProduct === row.product_id ? (
                    batches.isLoading ? (
                      <p className="text-secondary">Loading batches…</p>
                    ) : batches.data?.length ? (
                      <ul className="mt-2 space-y-1 text-secondary">
                        {batches.data.flatMap((batch) =>
                          batch.locations.map((entry) => (
                            <li key={`${batch.id}-${entry.location_id}`}>
                              {batch.batch_no} · exp {batch.expiry_date} · {entry.location_name} · {entry.quantity}
                            </li>
                          )),
                        )}
                      </ul>
                    ) : (
                      <p className="text-secondary">No batch balances.</p>
                    )
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <CatalogueImportPanel />

        <div className="grid gap-5 xl:grid-cols-2">
          <Card>
            <CardTitleBar title="Receive stock" />
            <div className="grid gap-3 px-5 py-4">
              <Select aria-label="Product" value={productId} onChange={(event) => setProductId(event.target.value)}>
                <option value="">Select product…</option>
                {(products.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.generic_name} {item.strength}</option>)}
              </Select>
              <Select aria-label="Receipt location" value={locationId || defaultLocation} onChange={(event) => setLocationId(event.target.value)}>
                {(locations.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </Select>
              <TextInput aria-label="Supplier" value={supplierName} onChange={(event) => setSupplierName(event.target.value)} placeholder="Supplier (optional)" />
              {receiptRows.map((row, index) => {
                const suffix = index === 0 ? "" : ` ${index + 1}`;
                return (
                  <div key={index} className="grid gap-2 rounded-[12px] border border-line-soft p-3">
                    <p className="text-[12px] font-semibold text-ink">Receipt line {index + 1}</p>
                    <TextInput aria-label={`Batch number${suffix}`} value={row.batchNo} onChange={(event) => setReceiptRows((current) => current.map((item, rowIndex) => rowIndex === index ? { ...item, batchNo: event.target.value } : item))} placeholder="Batch number" />
                    <TextInput type="date" aria-label={`Expiry date${suffix}`} value={row.expiryDate} onChange={(event) => setReceiptRows((current) => current.map((item, rowIndex) => rowIndex === index ? { ...item, expiryDate: event.target.value } : item))} />
                    <TextInput inputMode="decimal" aria-label={`Quantity${suffix}`} value={row.quantity} onChange={(event) => setReceiptRows((current) => current.map((item, rowIndex) => rowIndex === index ? { ...item, quantity: event.target.value } : item))} placeholder="Quantity" />
                  </div>
                );
              })}
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => setReceiptRows((current) => [...current, emptyReceiptRow()])}>Add receipt line</Button>
                <Button disabled={receive.isPending || Boolean(pendingReceipt) || !online} onClick={confirmReceipt}>
                  {receive.isPending ? "Posting…" : "Post receipt"}
                </Button>
              </div>
              {pendingReceipt && receive.isError ? (
                <Button variant="secondary" onClick={() => receive.mutate(pendingReceipt)}>Retry uncertain receipt</Button>
              ) : null}
            </div>
          </Card>

          <Card>
            <CardTitleBar title="Counting" />
            <div className="grid gap-3 px-5 py-4">
              <p className="text-[12.5px] font-medium text-ink">Blind stock count</p>
              <Select aria-label="Location" value={locationId || defaultLocation} onChange={(event) => setLocationId(event.target.value)}>
                {(locations.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </Select>
              <Button variant="secondary" disabled={openCount.isPending || !online} onClick={startCountOpen}>
                {openCount.isPending ? "Opening…" : "Open count"}
              </Button>
              {countRefreshFailed ? (
                <Button
                  variant="secondary"
                  disabled={refreshCountSheet.isPending || !online}
                  onClick={() => {
                    const id = openedCountIdRef.current ?? approvedCountIdRef.current;
                    if (id) refreshCountSheet.mutate(id);
                  }}
                >
                  {refreshCountSheet.isPending ? "Refreshing…" : "Retry sheet refresh"}
                </Button>
              ) : null}
              {countSheet ? (
                <>
                  <p className="text-[12.5px] text-secondary">Count {countSheet.id} · {countSheet.state} · version {countSheet.version}</p>
                  {countSheet.blind ? <p className="text-[12.5px] text-secondary">blind sheet (expected quantities hidden)</p> : null}
                  <ul className="divide-y divide-line-soft">
                    {countSheet.lines.map((line) => {
                      const invalid = countValidationFailed && !/^\d+(\.\d{1,2})?$/.test((countValues[line.id] ?? "").trim());
                      return (
                        <li key={line.id} className="py-2 text-[12.5px]">
                          <label htmlFor={`count-${line.id}`} className="font-medium text-ink">
                            {line.product_name} · {line.batch_no}
                            {line.variance_qty !== undefined ? ` · variance ${line.variance_qty}` : ""}
                          </label>
                          <TextInput
                            id={`count-${line.id}`}
                            aria-label={`Counted quantity ${line.batch_no}`}
                            value={countValues[line.id] ?? ""}
                            aria-invalid={invalid || undefined}
                            onChange={(event) => setCountValues((current) => ({ ...current, [line.id]: event.target.value }))}
                          />
                          {invalid ? <p className="text-[12px] text-rose-700">Enter an observed decimal quantity.</p> : null}
                        </li>
                      );
                    })}
                  </ul>
                  <Button disabled={submitCount.isPending || !online} onClick={submitCountSheet}>Submit count</Button>
                  {countSheet.state === "SUBMITTED" && can("inventory.approve") ? (
                    <Button disabled={approveCount.isPending || !online} onClick={approveCountSheet}>
                      Approve count
                    </Button>
                  ) : null}
                </>
              ) : (
                <EmptyState icon={<IconBilling className="h-5 w-5" />} title="No count sheet loaded." hint="Open a blind count for the selected location." />
              )}
            </div>
          </Card>
        </div>

        <Card>
          <CardTitleBar title="Count review" />
          {countList.isLoading ? (
            <p className="px-5 pb-4 text-[12.5px] text-secondary">Loading counts…</p>
          ) : countList.isError ? (
            <p className="px-5 pb-4 text-[12.5px] text-ink" role="alert">Counts could not be loaded.</p>
          ) : !countList.data?.length ? (
            <p className="px-5 pb-4 text-[12.5px] text-secondary">No submitted counts.</p>
          ) : (
            <ul className="divide-y divide-line-soft px-5 pb-4">
              {countList.data.map((row) => (
                <li key={row.id} className="py-2.5 text-[12.5px]">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-ink">{row.location_name} · {row.state}</span>
                    <Button variant="secondary" onClick={() => setReviewCountId(row.id)}>Review count</Button>
                  </div>
                  <p className="text-secondary">
                    Submitted by {row.submitted_by_name ?? "—"} · {row.line_count} lines · version {row.version}
                  </p>
                </li>
              ))}
            </ul>
          )}
          {reviewCountId && reviewDetail.data ? (
            <div className="mx-5 mb-5 rounded-[14px] border border-line-soft p-4">
              <h3 className="text-[13px] font-bold text-ink">Count detail</h3>
              <ul className="mt-2 divide-y divide-line-soft text-[12.5px]">
                {reviewDetail.data.lines.map((line) => (
                  <li key={line.id} className="py-2">
                    {line.product_name} · {line.batch_no} · counted {line.counted_qty ?? "—"} · expected {line.expected_qty ?? "—"} · variance {line.variance_qty ?? "—"}
                  </li>
                ))}
              </ul>
              <h4 className="mt-4 text-[12.5px] font-bold text-ink">Movements during count</h4>
              {reviewDetail.data.movements_during_count.length ? (
                <ul className="mt-2 divide-y divide-line-soft text-[12.5px]">
                  {reviewDetail.data.movements_during_count.map((item) => (
                    <li key={item.id} className="py-2">{item.movement_type} · {item.quantity} · {formatDate(item.occurred_at)}</li>
                  ))}
                </ul>
              ) : (
                <p className="mt-2 text-[12.5px] text-secondary">No movements during the count window.</p>
              )}
            </div>
          ) : null}
        </Card>

        <Card>
          <CardTitleBar title="Movement ledger" />
          {movements.isLoading ? (
            <p className="px-5 pb-4 text-[12.5px] text-secondary">Loading movements…</p>
          ) : movements.data?.length ? (
            <ul className="divide-y divide-line-soft px-5 pb-4 text-[12.5px]">
              {movements.data.map((item) => (
                <li key={item.id} className="py-2">
                  {item.movement_type} · {item.batch_no} · {item.quantity} · {item.location_name} · {formatDate(item.occurred_at)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-5 pb-4 text-[12.5px] text-secondary">No movements in this window.</p>
          )}
        </Card>
      </div>
    </>
  );
}
