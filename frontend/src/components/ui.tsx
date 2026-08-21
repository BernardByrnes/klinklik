"use client";

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

import { IconAlertTriangle, IconDismiss } from "./icons";

/*
 * Shared visual system translated from the approved reference
 * (K:\new\clinic.html): one card style, one badge style, one button
 * hierarchy, consistent focus rings.
 */

const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2";

export type ButtonVariant = "primary" | "secondary" | "small-secondary" | "link" | "danger";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "inline-flex items-center justify-center gap-2 h-11 rounded-[12px] bg-primary px-5 text-[13.5px] font-semibold text-white shadow-primary hover:bg-primary-strong active:scale-[0.98] transition-all disabled:opacity-50 disabled:pointer-events-none",
  secondary:
    "inline-flex items-center justify-center gap-2 h-11 rounded-[12px] border border-line bg-white px-4 text-[13px] font-semibold text-ink shadow-card hover:bg-surface-muted transition-colors disabled:opacity-50 disabled:pointer-events-none",
  "small-secondary":
    "inline-flex items-center justify-center gap-1.5 h-9 rounded-[10px] border border-line bg-white px-3 text-[12px] font-semibold text-ink hover:bg-surface-muted transition-colors disabled:opacity-50 disabled:pointer-events-none",
  link: "inline-flex items-center justify-center gap-2 rounded-lg text-[12.5px] font-semibold text-primary-text hover:text-primary-strong transition-colors",
  danger:
    "inline-flex items-center justify-center gap-2 h-11 rounded-[12px] border border-transparent bg-accent-pink-soft px-4 text-[13px] font-semibold text-accent-pink hover:brightness-[0.97] transition-all disabled:opacity-50 disabled:pointer-events-none",
};

export function Button({
  variant = "primary",
  className = "",
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  return <button type={type} className={`${BUTTON_VARIANTS[variant]} ${FOCUS_RING} ${className}`} {...props} />;
}

export function Card({ className = "", children }: { className?: string; children?: ReactNode }) {
  return (
    <article className={`bg-white border border-line rounded-[18px] shadow-card ${className}`}>{children}</article>
  );
}

export function CardTitleBar({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between px-5 pt-5">
      <h2 className="text-[15px] font-bold text-ink">{title}</h2>
      {action}
    </div>
  );
}

export type BadgeTone = "amber" | "blue" | "purple" | "pink" | "teal" | "neutral";

const BADGE_TONES: Record<BadgeTone, string> = {
  amber: "bg-accent-orange-soft text-accent-orange-text",
  blue: "bg-accent-blue-soft text-accent-blue",
  purple: "bg-primary-soft text-primary-text",
  pink: "bg-accent-pink-soft text-accent-pink",
  teal: "bg-accent-teal-soft text-accent-teal-text",
  neutral: "bg-line-soft text-secondary",
};

export function StatusBadge({ tone = "neutral", children }: { tone?: BadgeTone; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[10.5px] font-semibold ${BADGE_TONES[tone]}`}>
      {children}
    </span>
  );
}

export function queueStatusBadge(status: string): { tone: BadgeTone; label: string } {
  switch (status) {
    case "WAITING":
      return { tone: "amber", label: "Waiting" };
    case "CALLED":
      return { tone: "blue", label: "Called" };
    case "IN_TRIAGE":
      return { tone: "blue", label: "In triage" };
    case "TRIAGED":
      return { tone: "purple", label: "Ready for consultation" };
    case "IN_CONSULTATION":
      return { tone: "purple", label: "In consultation" };
    case "COMPLETED":
      return { tone: "teal", label: "Completed" };
    default:
      return { tone: "neutral", label: status ? status.charAt(0) + status.slice(1).toLowerCase() : "—" };
  }
}

export function invoiceStatusBadge(status: string): { tone: BadgeTone; label: string } {
  switch (status) {
    case "ISSUED":
      return { tone: "amber", label: "Awaiting payment" };
    case "PARTIALLY_PAID":
      return { tone: "blue", label: "Partially paid" };
    case "PAID":
      return { tone: "teal", label: "Paid" };
    case "VOID":
      return { tone: "neutral", label: "Void" };
    default:
      return { tone: "neutral", label: status ? status.charAt(0) + status.slice(1).toLowerCase() : "—" };
  }
}

const SEQUENCE_TONES = [
  "bg-primary-soft text-primary-text",
  "bg-accent-blue-soft text-accent-blue",
  "bg-accent-pink-soft text-accent-pink",
  "bg-accent-orange-soft text-accent-orange",
  "bg-accent-teal-soft text-accent-teal-text",
];

export function SequenceCircle({ value, index }: { value: ReactNode; index: number }) {
  return (
    <span
      className={`h-9 w-9 shrink-0 rounded-full grid place-items-center text-[13px] font-bold ${SEQUENCE_TONES[index % SEQUENCE_TONES.length]}`}
    >
      {value}
    </span>
  );
}

export function AvatarInitials({ name, className = "" }: { name: string; className?: string }) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
  return (
    <span
      className={`h-9 w-9 shrink-0 rounded-full bg-gradient-to-br from-[#8B6DFF] to-primary grid place-items-center text-white text-[12px] font-semibold ${className}`}
    >
      {initials || "?"}
    </span>
  );
}

export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <section className="flex flex-wrap items-center justify-between gap-4">
      <div>
        <h1 className="text-[26px] font-bold tracking-[-0.02em] text-ink">{title}</h1>
        {subtitle ? <p className="mt-1 text-[13.5px] font-medium text-secondary">{subtitle}</p> : null}
      </div>
      {actions ? <div className="flex items-center gap-3">{actions}</div> : null}
    </section>
  );
}

export function MetricCard({
  label,
  value,
  icon,
  tone = "purple",
  hint,
}: {
  label: string;
  value: ReactNode;
  icon: ReactNode;
  tone?: "purple" | "blue" | "pink" | "orange" | "teal";
  hint?: string;
}) {
  const toneClasses: Record<string, string> = {
    purple: "bg-primary-soft text-primary",
    blue: "bg-accent-blue-soft text-accent-blue",
    pink: "bg-accent-pink-soft text-accent-pink",
    orange: "bg-accent-orange-soft text-accent-orange",
    teal: "bg-accent-teal-soft text-accent-teal",
  };
  return (
    <article className="bg-white border border-line rounded-[18px] shadow-card p-5 hover:shadow-card-hover hover:-translate-y-[1px] transition-all duration-200">
      <div className="flex items-start gap-4">
        <span className={`h-11 w-11 shrink-0 rounded-full grid place-items-center ${toneClasses[tone]}`}>{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="text-[13px] font-medium text-secondary">{label}</div>
          <div className="mt-0.5 text-[24px] leading-8 font-bold tracking-[-0.02em] text-ink">{value}</div>
          {hint ? <div className="mt-0.5 text-[11.5px] font-medium text-muted">{hint}</div> : null}
        </div>
      </div>
    </article>
  );
}

export function LoadingSkeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-[10px] bg-line-soft ${className}`} aria-hidden="true" />;
}

export function CardSkeleton({ rows = 3, className = "" }: { rows?: number; className?: string }) {
  return (
    <article className={`bg-white border border-line rounded-[18px] shadow-card p-5 ${className}`} aria-busy="true" aria-label="Loading">
      <LoadingSkeleton className="h-4 w-32" />
      <div className="mt-5 space-y-4">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="flex items-center gap-3">
            <LoadingSkeleton className="h-9 w-9 rounded-full" />
            <div className="flex-1 space-y-2">
              <LoadingSkeleton className="h-3 w-2/5" />
              <LoadingSkeleton className="h-2.5 w-1/4" />
            </div>
            <LoadingSkeleton className="h-6 w-20 rounded-full" />
          </div>
        ))}
      </div>
    </article>
  );
}

export function MetricSkeleton() {
  return (
    <article className="bg-white border border-line rounded-[18px] shadow-card p-5" aria-busy="true" aria-label="Loading">
      <div className="flex items-start gap-4">
        <LoadingSkeleton className="h-11 w-11 rounded-full" />
        <div className="flex-1 space-y-2">
          <LoadingSkeleton className="h-3 w-24" />
          <LoadingSkeleton className="h-7 w-16" />
        </div>
      </div>
    </article>
  );
}

export function EmptyState({
  icon,
  title,
  hint,
  action,
}: {
  icon: ReactNode;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center px-6 py-12">
      <span className="h-12 w-12 rounded-full bg-primary-soft grid place-items-center text-primary">{icon}</span>
      <p className="mt-4 text-[13.5px] font-semibold text-ink">{title}</p>
      {hint ? <p className="mt-1 max-w-sm text-[12.5px] font-medium text-muted">{hint}</p> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function ErrorBanner({ message, onDismiss }: { message: string; onDismiss?: () => void }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-[14px] bg-accent-pink-soft px-4 py-3"
    >
      <span className="text-accent-pink shrink-0 mt-0.5">
        <IconAlertTriangle className="h-[18px] w-[18px]" />
      </span>
      <p className="flex-1 min-w-0 text-[12.5px] font-medium text-ink leading-relaxed">{message}</p>
      {onDismiss ? (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss error"
          className={`shrink-0 rounded-lg p-1 text-muted hover:text-ink transition-colors ${FOCUS_RING}`}
        >
          <IconDismiss className="h-4 w-4" />
        </button>
      ) : null}
    </div>
  );
}

export function UnauthorisedState({ capability }: { capability: string }) {
  return (
    <Card>
      <EmptyState
        icon={<IconAlertTriangle className="h-5 w-5" />}
        title="You don't have permission to use this workspace."
        hint={`This area requires the "${capability}" permission. Ask an administrator if you need access.`}
      />
    </Card>
  );
}

const INPUT_CLASS =
  "h-11 w-full rounded-[12px] border border-line bg-white px-3.5 text-[13px] font-medium text-ink placeholder-muted shadow-card focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-shadow";

export function Field({ label, htmlFor, children, hint }: { label: string; htmlFor: string; children: ReactNode; hint?: string }) {
  return (
    <div className="grid gap-1.5">
      <label htmlFor={htmlFor} className="text-[12px] font-semibold text-secondary">
        {label}
      </label>
      {children}
      {hint ? <p className="text-[11.5px] font-medium text-muted">{hint}</p> : null}
    </div>
  );
}

export function TextInput({ className = "", ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`${INPUT_CLASS} ${className}`} {...props} />;
}

export function Select({ className = "", children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={`${INPUT_CLASS} appearance-none pr-9 bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%2398A2B3%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpath%20d%3D%22m6%209%206%206%206-6%22%2F%3E%3C%2Fsvg%3E')] bg-no-repeat bg-[right_0.75rem_center] bg-[length:1rem] ${className}`} {...props}>
      {children}
    </select>
  );
}

export function Textarea({ className = "", ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={`min-h-[120px] w-full rounded-[12px] border border-line bg-white px-3.5 py-3 text-[13px] font-medium text-ink placeholder-muted shadow-card focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-shadow resize-y ${className}`}
      {...props}
    />
  );
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  } catch {
    return "—";
  }
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return "—";
  }
}
