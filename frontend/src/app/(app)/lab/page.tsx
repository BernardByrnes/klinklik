"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest, newIdempotencyKey } from "../../../lib/api";
import { protectedQueryKey, useProtectedQueryKey } from "../../../lib/authority";
import { useSession } from "../../../lib/session";
import { IconBilling, IconCheckCircle } from "../../../components/icons";
import {
  Button,
  Card,
  CardTitleBar,
  EmptyState,
  ErrorBanner,
  PageHeader,
  StatusBadge,
  UnauthorisedState,
  formatDate,
} from "../../../components/ui";

type LabRow = {
  item_id: string;
  order_id: string;
  patient_name: string;
  patient_no: string;
  test_name: string;
  priority: string;
  state: string;
  ordered_by: string;
  ordered_at: string;
  clinical_notes: string;
  specimen_id: string;
  urgency: boolean;
};

type Worklist = {
  awaiting_payment: LabRow[];
  to_collect: LabRow[];
  in_bench: LabRow[];
  to_verify: LabRow[];
  rejected: LabRow[];
  released: LabRow[];
};

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "The request could not be completed.";
}

function Row({ row, action }: { row: LabRow; action?: React.ReactNode }) {
  return (
    <li className="px-3.5 py-2.5 text-[12.5px]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-ink">
          {row.test_name} · {row.patient_name}
          <span className="ml-1 font-medium text-muted">{row.patient_no}</span>
        </span>
        <span className="flex items-center gap-2">
          {row.urgency ? <StatusBadge tone="pink">URGENT</StatusBadge> : null}
          <StatusBadge tone="neutral">{row.state}</StatusBadge>
        </span>
      </div>
      <p className="mt-1 text-secondary">
        Ordered {formatDate(row.ordered_at)}
        {row.specimen_id ? ` · specimen ${row.specimen_id}` : ""}
        {row.clinical_notes ? ` · notes: ${row.clinical_notes}` : ""}
      </p>
      {action ? <div className="mt-2">{action}</div> : null}
    </li>
  );
}

export default function LabPage() {
  const { can } = useSession();
  const queryClient = useQueryClient();
  const worklistKey = useProtectedQueryKey("lab-worklist");
  const worklist = useQuery({
    queryKey: worklistKey,
    queryFn: () => apiRequest<Worklist>("/api/v1/lab/worklist/"),
    enabled: can("lab.result.entry"),
  });

  const action = useMutation({
    mutationFn: ({ itemId, action }: { itemId: string; action: "collect" | "release" }) =>
      apiRequest(`/api/v1/lab/items/${itemId}/${action}/`, {
        method: "POST",
        headers: { "Idempotency-Key": newIdempotencyKey(`lab-${action}`) },
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: protectedQueryKey("lab-worklist") });
    },
  });

  if (!can("lab.result.entry")) {
    return <UnauthorisedState capability="lab.result.entry" />;
  }

  return (
    <>
      <PageHeader
        title="Laboratory"
        subtitle="Collect samples, enter structured results and release only verified work."
      />
      {action.isError ? <ErrorBanner message={errorMessage(action.error)} /> : null}
      {action.isSuccess ? (
        <p className="flex items-center gap-2 rounded-[14px] bg-accent-teal-soft px-4 py-3 text-[12.5px] font-medium text-ink">
          <IconCheckCircle className="h-4 w-4 text-accent-teal shrink-0" />
          Laboratory state updated.
        </p>
      ) : null}

      {worklist.isLoading ? (
        <Card>
          <div className="px-5 py-6 text-[12.5px] font-medium text-secondary" role="status" aria-busy="true">
            Loading the laboratory worklist…
          </div>
        </Card>
      ) : worklist.isError ? (
        <Card>
          <div className="px-5 py-6 text-[12.5px] font-medium text-ink" role="alert">
            The laboratory worklist could not be loaded.
          </div>
        </Card>
      ) : worklist.data ? (
        <section className="grid grid-cols-1 xl:grid-cols-2 gap-5 items-start">
          <Card>
            <CardTitleBar title={`To collect (${worklist.data.to_collect.length})`} />
            {worklist.data.to_collect.length ? (
              <ul className="divide-y divide-line-soft">
                {worklist.data.to_collect.map((row) => (
                  <Row
                    key={row.item_id}
                    row={row}
                    action={
                      <Button
                        variant="secondary"
                        disabled={action.isPending}
                        onClick={() => action.mutate({ itemId: row.item_id, action: "collect" })}
                      >
                        Collect sample
                      </Button>
                    }
                  />
                ))}
              </ul>
            ) : (
              <EmptyState
                icon={<IconBilling className="h-5 w-5" />}
                title="No samples to collect."
                hint="Paid or ungated items appear here."
              />
            )}
          </Card>

          <Card>
            <CardTitleBar title={`To verify (${worklist.data.to_verify.length})`} />
            {worklist.data.to_verify.length ? (
              <ul className="divide-y divide-line-soft">
                {worklist.data.to_verify.map((row) => (
                  <Row
                    key={row.item_id}
                    row={row}
                    action={
                      <Button
                        variant="secondary"
                        disabled={action.isPending}
                        onClick={() => action.mutate({ itemId: row.item_id, action: "release" })}
                      >
                        Release result
                      </Button>
                    }
                  />
                ))}
              </ul>
            ) : (
              <EmptyState
                icon={<IconBilling className="h-5 w-5" />}
                title="No results awaiting verification."
                hint="Entered results appear here for a separate verifier."
              />
            )}
          </Card>

          <Card>
            <CardTitleBar title={`In bench (${worklist.data.in_bench.length})`} />
            {worklist.data.in_bench.length ? (
              <ul className="divide-y divide-line-soft">
                {worklist.data.in_bench.map((row) => (
                  <Row key={row.item_id} row={row} />
                ))}
              </ul>
            ) : (
              <p className="px-5 py-4 text-[12.5px] font-medium text-secondary">
                No collected samples in the bench worklist.
              </p>
            )}
          </Card>

          <Card>
            <CardTitleBar title={`Rejected / action needed (${worklist.data.rejected.length})`} />
            {worklist.data.rejected.length ? (
              <ul className="divide-y divide-line-soft">
                {worklist.data.rejected.map((row) => (
                  <Row key={row.item_id} row={row} />
                ))}
              </ul>
            ) : (
              <p className="px-5 py-4 text-[12.5px] font-medium text-secondary">
                No rejected samples.
              </p>
            )}
          </Card>

          <Card className="xl:col-span-2">
            <CardTitleBar title={`Awaiting payment (${worklist.data.awaiting_payment.length})`} />
            {worklist.data.awaiting_payment.length ? (
              <ul className="divide-y divide-line-soft">
                {worklist.data.awaiting_payment.map((row) => (
                  <Row key={row.item_id} row={row} />
                ))}
              </ul>
            ) : (
              <p className="px-5 py-4 text-[12.5px] font-medium text-secondary">
                No laboratory items are waiting for payment.
              </p>
            )}
          </Card>
        </section>
      ) : null}
    </>
  );
}
