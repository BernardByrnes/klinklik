"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiRequest } from "../../../lib/api";
import { useProtectedQueryKey } from "../../../lib/authority";
import { useSession } from "../../../lib/session";
import { uiRole } from "../../../lib/roles";
import { Invoice, QueueEntry } from "../../../features/clinic";
import {
  IconArrowRight,
  IconBilling,
  IconConsultation,
  IconNote,
  IconPatients,
  IconQueue,
  IconTriage,
  IconUserPlus,
} from "../../../components/icons";
import {
  Button,
  Card,
  CardSkeleton,
  CardTitleBar,
  EmptyState,
  MetricCard,
  MetricSkeleton,
  PageHeader,
  SequenceCircle,
  StatusBadge,
  formatTime,
  queueStatusBadge,
} from "../../../components/ui";

function greeting(now: Date): string {
  const hour = now.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

type QuickAction = { label: string; href: string; icon: React.ReactNode; tile: string };

function quickActions(role: ReturnType<typeof uiRole>): QuickAction[] {
  const actions: QuickAction[] = [];
  if (role === "admin" || role === "reception") {
    actions.push(
      { label: "Register Patient", href: "/patients", icon: <IconUserPlus className="h-5 w-5" />, tile: "bg-primary-soft text-primary" },
      { label: "Check-in Patient", href: "/patients", icon: <IconPatients className="h-5 w-5" />, tile: "bg-accent-blue-soft text-accent-blue" },
    );
  }
  if (role === "nurse") {
    actions.push({ label: "Triage Queue", href: "/triage", icon: <IconTriage className="h-5 w-5" />, tile: "bg-accent-blue-soft text-accent-blue" });
  }
  if (role === "clinician" || role === "admin") {
    actions.push({ label: "New Consultation", href: "/consultations", icon: <IconConsultation className="h-5 w-5" />, tile: "bg-accent-pink-soft text-accent-pink" });
  }
  if (role === "cashier" || role === "admin" || role === "reception") {
    actions.push({ label: "Collect Payment", href: "/billing", icon: <IconBilling className="h-5 w-5" />, tile: "bg-accent-orange-soft text-accent-orange" });
  }
  actions.push({ label: "View Queue", href: "/queue", icon: <IconQueue className="h-5 w-5" />, tile: "bg-accent-teal-soft text-accent-teal" });
  return actions;
}

function headerCta(role: ReturnType<typeof uiRole>): { label: string; href: string } | null {
  switch (role) {
    case "reception":
      return { label: "Register patient", href: "/patients" };
    case "nurse":
      return { label: "Go to triage", href: "/triage" };
    case "clinician":
      return { label: "Go to consultations", href: "/consultations" };
    case "cashier":
      return { label: "Collect payment", href: "/billing" };
    default:
      return { label: "Register patient", href: "/patients" };
  }
}

export default function OverviewPage() {
  const { session, can, currentFacility } = useSession();
  const queueKey = useProtectedQueryKey("queue");
  const outstandingInvoicesKey = useProtectedQueryKey("invoices", "outstanding");
  const role = uiRole(session!);
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), []);

  const queue = useQuery({
    queryKey: queueKey,
    queryFn: () => apiRequest<QueueEntry[]>("/api/v1/clinic/queue/"),
    enabled: can("queue.view"),
  });
  const unpaidInvoices = useQuery({
    queryKey: outstandingInvoicesKey,
    queryFn: () => apiRequest<Invoice[]>("/api/v1/billing/invoices/?status=ISSUED,PARTIALLY_PAID"),
    enabled: can("billing.invoice.create"),
  });

  const entries = queue.data ?? [];
  const awaitingTriage = entries.filter((entry) => entry.status === "WAITING" || entry.status === "CALLED").length;
  const withClinician = entries.filter((entry) => entry.status === "IN_CONSULTATION").length;
  const readyForClinician = entries.filter((entry) => entry.status === "TRIAGED").length;
  const awaitingPayment = unpaidInvoices.data?.length;
  const firstName = (session?.user.full_name || session?.user.username || "there").split(" ")[0];
  const cta = headerCta(role);
  const dateChip = now
    ? now.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric", year: "numeric" })
    : "";

  return (
    <>
      <PageHeader
        title={
          <>
            {now ? greeting(now) : "Hello"}, {firstName}
          </>
        }
        subtitle={`Here's what's happening at ${currentFacility?.name ?? session?.organisation.name} today.`}
        actions={
          <>
            {dateChip ? (
              <span className="hidden sm:inline-flex items-center h-11 rounded-[12px] border border-line bg-white px-4 text-[13px] font-semibold text-ink shadow-card">
                {dateChip}
              </span>
            ) : null}
            {cta ? (
              <Link href={cta.href}>
                <Button>{cta.label}</Button>
              </Link>
            ) : null}
          </>
        }
      />

      <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5" aria-label="Key metrics">
        {queue.isLoading ? (
          Array.from({ length: 4 }).map((_, index) => <MetricSkeleton key={index} />)
        ) : (
          <>
            <MetricCard label="Active queue" value={entries.length} icon={<IconQueue className="h-5 w-5" />} tone="purple" hint="Patients in the clinic right now" />
            <MetricCard label="Awaiting triage" value={awaitingTriage} icon={<IconTriage className="h-5 w-5" />} tone="blue" hint="Waiting or called" />
            <MetricCard
              label={can("clinical.note.create") ? "Ready for consultation" : "With clinician"}
              value={can("clinical.note.create") ? readyForClinician : withClinician}
              icon={<IconConsultation className="h-5 w-5" />}
              tone="pink"
              hint={can("clinical.note.create") ? "Triaged and ready" : "Currently in consultation"}
            />
            {can("billing.invoice.create") ? (
              awaitingPayment === undefined ? (
                <MetricSkeleton />
              ) : (
                <MetricCard label="Awaiting payment" value={awaitingPayment} icon={<IconBilling className="h-5 w-5" />} tone="orange" hint="Unpaid invoices" />
              )
            ) : (
              <MetricCard label="In consultation" value={withClinician} icon={<IconNote className="h-5 w-5" />} tone="teal" hint="Currently with a clinician" />
            )}
          </>
        )}
      </section>

      <section className="grid grid-cols-1 xl:grid-cols-[1.55fr_1fr] gap-5">
        {queue.isLoading ? (
          <CardSkeleton rows={5} />
        ) : queue.isError ? (
          <Card>
            <EmptyState
              icon={<IconQueue className="h-5 w-5" />}
              title="The queue could not be loaded."
              hint="Check your connection and try again."
            />
          </Card>
        ) : entries.length === 0 ? (
          <Card>
            <CardTitleBar title="Today's Queue" />
            <EmptyState
              icon={<IconQueue className="h-5 w-5" />}
              title="No patients are in the queue yet."
              hint="Check in a patient from the Patients workspace to start the visit."
              action={
                can("patient.create") ? (
                  <Link href="/patients">
                    <Button variant="secondary">Go to patients</Button>
                  </Link>
                ) : undefined
              }
            />
          </Card>
        ) : (
          <Card>
            <CardTitleBar
              title="Today's Queue"
              action={
                <Link href="/queue" className="inline-flex items-center gap-1.5 rounded-lg text-[12.5px] font-semibold text-primary-text hover:text-primary-strong transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2">
                  View all <IconArrowRight className="h-4 w-4" />
                </Link>
              }
            />
            <div className="px-5 pt-2 pb-2 divide-y divide-line-soft">
              {entries.slice(0, 6).map((entry, index) => {
                const badge = queueStatusBadge(entry.status);
                return (
                  <div key={entry.id} className="flex items-center gap-3 py-3">
                    <SequenceCircle value={entry.sequence || index + 1} index={index} />
                    <div className="flex-1 min-w-0 leading-tight">
                      <div className="text-[13px] font-semibold text-ink">{entry.patient_name}</div>
                      <div className="mt-0.5 text-[11.5px] font-medium text-muted">
                        {entry.queue_label} <span className="mx-0.5">•</span> {entry.department_name}
                      </div>
                    </div>
                    <div className="text-right leading-tight">
                      <StatusBadge tone={badge.tone}>{badge.label}</StatusBadge>
                      <div className="mt-1 text-[10.5px] font-medium text-muted">{formatTime(entry.arrival_at)}</div>
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="px-5 py-4">
              <Link
                href="/queue"
                className="w-full flex items-center justify-center gap-2 text-[12.5px] font-semibold text-primary-text hover:text-primary-strong transition-colors rounded-lg py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
              >
                View full queue <IconArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </Card>
        )}

        <Card>
          <div className="px-5 pt-5">
            <h2 className="text-[15px] font-bold text-ink">Quick Actions</h2>
          </div>
          <div className="px-5 py-5">
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {quickActions(role).map((action) => (
                <Link
                  key={action.label}
                  href={action.href}
                  className={`flex flex-col items-center justify-center gap-2 rounded-[14px] px-2 py-4 hover:shadow-card-hover hover:-translate-y-[1px] active:scale-[0.97] transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 ${action.tile}`}
                >
                  {action.icon}
                  <span className="text-[11px] font-semibold text-[#4A5164] text-center leading-tight">{action.label}</span>
                </Link>
              ))}
            </div>
          </div>
        </Card>
      </section>
    </>
  );
}
