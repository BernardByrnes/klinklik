"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiRequestError, apiRequest, newIdempotencyKey } from "../../../lib/api";
import { protectedQueryKey, useProtectedQueryKey } from "../../../lib/authority";
import { useSession } from "../../../lib/session";
import { IconBilling, IconCheckCircle } from "../../../components/icons";
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
} from "../../../components/ui";

type StockRow = {
  product_id: string;
  code: string;
  generic_name: string;
  brand_name: string;
  dosage_form: string;
  strength: string;
  category: string;
  controlled: boolean;
  usable_quantity: string;
  expired_quantity: string;
  batch_count: number;
  earliest_expiry: string | null;
  status: string;
  reorder_level: string | null;
};

type Location = { id: string; code: string; name: string; is_default: boolean; active: boolean };
type Product = {
  id: string;
  code: string;
  generic_name: string;
  brand_name: string;
  dosage_form: string;
  strength: string;
  active: boolean;
};
type Movement = {
  id: string;
  batch_no: string;
  location_name: string;
  movement_type: string;
  quantity: string;
  occurred_at: string;
};

function errorMessage(error: unknown) {
  if (error instanceof ApiRequestError) {
    const body = error.data as { detail?: string; code?: string; row_errors?: unknown };
    if (body?.detail) return body.detail;
  }
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function statusTone(status: string) {
  if (status === "OUT" || status === "EXPIRED") return "pink" as const;
  if (status === "LOW" || status === "EXPIRING_SOON") return "amber" as const;
  return "teal" as const;
}

export default function InventoryPage() {
  const { can } = useSession();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [productId, setProductId] = useState("");
  const [locationId, setLocationId] = useState("");
  const [batchNo, setBatchNo] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [quantity, setQuantity] = useState("");
  const [supplierName, setSupplierName] = useState("");

  const stockKey = useProtectedQueryKey("inventory-stock", search);
  const locationsKey = useProtectedQueryKey("inventory-locations");
  const productsKey = useProtectedQueryKey("inventory-products");
  const movementsKey = useProtectedQueryKey("inventory-movements");

  const stock = useQuery({
    queryKey: stockKey,
    queryFn: () =>
      apiRequest<StockRow[]>(
        `/api/v1/inventory/stock/${search.trim() ? `?q=${encodeURIComponent(search.trim())}` : ""}`,
      ),
    enabled: can("inventory.read"),
  });
  const locations = useQuery({
    queryKey: locationsKey,
    queryFn: () => apiRequest<Location[]>("/api/v1/inventory/locations/"),
    enabled: can("inventory.read"),
  });
  const products = useQuery({
    queryKey: productsKey,
    queryFn: () => apiRequest<Product[]>("/api/v1/inventory/products/"),
    enabled: can("inventory.read"),
  });
  const movements = useQuery({
    queryKey: movementsKey,
    queryFn: () => apiRequest<Movement[]>("/api/v1/inventory/movements/"),
    enabled: can("inventory.read"),
  });

  const receive = useMutation({
    mutationFn: () =>
      apiRequest<{ receipt_no: string; warning_near_expiry: boolean }>(
        "/api/v1/inventory/receipts/",
        {
          method: "POST",
          headers: { "Idempotency-Key": newIdempotencyKey("inventory-receipt") },
          body: JSON.stringify({
            receipt_no: `GRN-${Date.now()}`,
            supplier_name: supplierName.trim(),
            lines: [
              {
                product_id: productId,
                location_id:
                  locationId ||
                  locations.data?.find((location) => location.is_default)?.id ||
                  locations.data?.[0]?.id,
                batch_no: batchNo.trim(),
                expiry_date: expiryDate,
                quantity,
              },
            ],
          }),
        },
      ),
    onSuccess: (result) => {
      setNotice(
        result.warning_near_expiry
          ? `Stock received on ${result.receipt_no}. Expiry is inside the 90-day warning horizon.`
          : `Stock received on ${result.receipt_no}.`,
      );
      setError("");
      setBatchNo("");
      setQuantity("");
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("inventory-stock") });
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("inventory-movements") });
    },
    onError: (reason) => {
      setNotice("");
      setError(errorMessage(reason));
    },
  });

  if (!can("inventory.read")) {
    return <UnauthorisedState capability="inventory.read" />;
  }

  const defaultLocation =
    locations.data?.find((location) => location.is_default)?.id ?? locations.data?.[0]?.id ?? "";

  return (
    <>
      <PageHeader
        title="Inventory"
        subtitle="Receive stock, inspect batch balances and read the append-only movement ledger."
      />
      {notice ? (
        <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">
          <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
          {notice}
        </p>
      ) : null}
      {error ? <ErrorBanner message={error} onDismiss={() => setError("")} /> : null}

      <section className="grid grid-cols-1 xl:grid-cols-[1.4fr_1fr] gap-5 items-start">
        <Card>
          <CardTitleBar title="Stock on hand" />
          <div className="px-5 py-4">
            <TextInput
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search product name or code…"
              aria-label="Search stock"
            />
            {stock.isLoading ? (
              <p className="mt-4 text-[12.5px] font-medium text-secondary" role="status" aria-busy="true">
                Loading stock…
              </p>
            ) : stock.isError ? (
              <p className="mt-4 text-[12.5px] font-medium text-ink" role="alert">
                Stock could not be loaded.
              </p>
            ) : stock.data?.length ? (
              <ul className="mt-4 divide-y divide-line-soft rounded-[14px] border border-line-soft">
                {stock.data.map((row) => (
                  <li key={row.product_id} className="px-3.5 py-3 text-[12.5px]">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold text-ink">
                        {row.generic_name} {row.strength}
                        <span className="ml-1 font-medium text-muted">· {row.code}</span>
                      </span>
                      <StatusBadge tone={statusTone(row.status)}>{row.status}</StatusBadge>
                    </div>
                    <p className="mt-1 text-secondary">
                      Usable {row.usable_quantity} · expired {row.expired_quantity} · {row.batch_count} batch(es)
                      {row.earliest_expiry ? ` · earliest expiry ${row.earliest_expiry}` : ""}
                      {row.reorder_level ? ` · reorder ${row.reorder_level}` : ""}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState
                icon={<IconBilling className="h-5 w-5" />}
                title="No stock yet."
                hint="Receive a non-expired batch to start the ledger."
              />
            )}
          </div>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardTitleBar title="Receive stock" />
            <div className="px-5 py-4 grid gap-3">
              <Field label="Product" htmlFor="receive-product">
                <Select
                  id="receive-product"
                  value={productId}
                  onChange={(event) => setProductId(event.target.value)}
                >
                  <option value="">Select product…</option>
                  {(products.data ?? []).map((product) => (
                    <option key={product.id} value={product.id}>
                      {product.generic_name} {product.strength} · {product.code}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Location" htmlFor="receive-location">
                <Select
                  id="receive-location"
                  value={locationId || defaultLocation}
                  onChange={(event) => setLocationId(event.target.value)}
                >
                  {(locations.data ?? []).map((location) => (
                    <option key={location.id} value={location.id}>
                      {location.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Batch number" htmlFor="receive-batch">
                <TextInput
                  id="receive-batch"
                  value={batchNo}
                  onChange={(event) => setBatchNo(event.target.value)}
                />
              </Field>
              <Field label="Expiry date" htmlFor="receive-expiry">
                <TextInput
                  id="receive-expiry"
                  type="date"
                  value={expiryDate}
                  onChange={(event) => setExpiryDate(event.target.value)}
                />
              </Field>
              <Field label="Quantity" htmlFor="receive-quantity">
                <TextInput
                  id="receive-quantity"
                  inputMode="decimal"
                  value={quantity}
                  onChange={(event) => setQuantity(event.target.value)}
                />
              </Field>
              <Field label="Supplier (free text)" htmlFor="receive-supplier">
                <TextInput
                  id="receive-supplier"
                  value={supplierName}
                  onChange={(event) => setSupplierName(event.target.value)}
                />
              </Field>
              <Button
                disabled={
                  receive.isPending ||
                  !productId ||
                  !(locationId || defaultLocation) ||
                  !batchNo.trim() ||
                  !expiryDate ||
                  !quantity.trim()
                }
                onClick={() => receive.mutate()}
              >
                {receive.isPending ? "Posting…" : "Post receipt"}
              </Button>
              <p className="text-[11.5px] font-medium text-muted">
                Expired batches are refused. Expiry inside 90 days is accepted with a warning.
              </p>
            </div>
          </Card>

          <Card>
            <CardTitleBar title="Recent movements" />
            <div className="px-5 py-4">
              {movements.isLoading ? (
                <p className="text-[12.5px] font-medium text-secondary" role="status" aria-busy="true">
                  Loading ledger…
                </p>
              ) : movements.data?.length ? (
                <ul className="divide-y divide-line-soft">
                  {movements.data.slice(0, 20).map((movement) => (
                    <li key={movement.id} className="py-2 text-[12px]">
                      <span className="font-semibold text-ink">{movement.movement_type}</span>
                      <span className="ml-2 text-secondary">
                        {movement.batch_no} · {movement.location_name} · {movement.quantity}
                      </span>
                      <span className="ml-2 text-muted">{formatDate(movement.occurred_at)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[12.5px] font-medium text-secondary">No movements recorded.</p>
              )}
            </div>
          </Card>
        </div>
      </section>
    </>
  );
}
