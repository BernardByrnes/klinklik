"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";

import { apiRequest } from "../../lib/api";
import { useSession } from "../../lib/session";
import { roleLabel } from "../../lib/roles";
import { QueueEntry } from "../../features/clinic";
import {
  BrandMark,
  IconBilling,
  IconChevronDown,
  IconConsultation,
  IconFacility,
  IconLogout,
  IconMenu,
  IconOverview,
  IconPatients,
  IconQueue,
  IconSearch,
  IconTriage,
} from "../icons";
import { AvatarInitials } from "../ui";

const FOCUS_RING =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2";

type NavItem = {
  href: string;
  label: string;
  icon: (props: { className?: string }) => ReactNode;
  capability: string | null;
};

const NAV_ITEMS: NavItem[] = [
  { href: "/overview", label: "Overview", icon: IconOverview, capability: null },
  { href: "/patients", label: "Patients", icon: IconPatients, capability: "patient.view" },
  { href: "/queue", label: "Queue", icon: IconQueue, capability: "queue.view" },
  { href: "/triage", label: "Triage", icon: IconTriage, capability: "triage.record" },
  { href: "/consultations", label: "Consultations", icon: IconConsultation, capability: "clinical.note.create" },
  { href: "/billing", label: "Billing & Payments", icon: IconBilling, capability: "billing.invoice.create" },
];

function useQueueBadge(enabled: boolean) {
  const query = useQuery({
    queryKey: ["queue"],
    queryFn: () => apiRequest<QueueEntry[]>("/api/v1/clinic/queue/"),
    enabled,
    staleTime: 10_000,
    refetchInterval: 30_000,
  });
  return query.data?.length ?? 0;
}

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const { can } = useSession();
  const badgeCount = useQueueBadge(can("queue.view"));

  return (
    <nav className="flex-1 overflow-y-auto px-3 lg:px-3.5 pt-2 pb-4 space-y-1" aria-label="Main navigation">
      {NAV_ITEMS.filter((item) => item.capability === null || can(item.capability)).map((item) => {
        const active = pathname === item.href || pathname.startsWith(item.href + "/");
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={`w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] justify-center lg:justify-start transition-colors ${FOCUS_RING} ${
              active
                ? "font-semibold bg-primary-soft text-primary-text"
                : "font-medium text-secondary hover:bg-primary-hover hover:text-ink"
            }`}
          >
            <Icon className="h-[19px] w-[19px] shrink-0" />
            <span className="hidden lg:inline flex-1 text-left">{item.label}</span>
            {item.href === "/queue" && badgeCount > 0 ? (
              <span className="hidden lg:inline-flex items-center rounded-full bg-[#EFECFB] px-2 py-0.5 text-[11px] font-semibold text-primary-text">
                {badgeCount}
              </span>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}

function FacilitySwitcher() {
  const { session, currentFacility, switchFacility } = useSession();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onDocumentClick(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocumentClick);
    return () => document.removeEventListener("mousedown", onDocumentClick);
  }, []);

  if (!session || session.facilities.length === 0) return null;

  return (
    <div className="relative" ref={wrapperRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Switch facility"
        className={`w-full flex items-center gap-3 rounded-[14px] border border-line bg-surface-muted p-2.5 hover:bg-primary-hover transition-colors text-left ${FOCUS_RING}`}
      >
        <span className="h-9 w-9 shrink-0 rounded-[10px] bg-accent-blue-soft grid place-items-center text-accent-blue">
          <IconFacility className="h-[18px] w-[18px]" />
        </span>
        <span className="flex-1 leading-tight">
          <span className="block text-[12.5px] font-semibold text-ink">{currentFacility?.name ?? "Facility"}</span>
          <span className="block text-[11px] font-medium text-muted">{session.organisation.name}</span>
        </span>
        <IconChevronDown className="h-4 w-4 text-muted" />
      </button>
      {open ? (
        <div
          role="listbox"
          aria-label="Facilities"
          className="absolute left-0 right-0 z-20 mt-2 rounded-[14px] border border-line bg-white p-1.5 shadow-elevated"
        >
          {session.facilities.map((facility) => (
            <button
              key={facility.id}
              type="button"
              role="option"
              aria-selected={facility.id === currentFacility?.id}
              onClick={() => {
                switchFacility(facility.id);
                setOpen(false);
              }}
              className={`w-full rounded-[10px] px-3 py-2 text-left text-[12px] transition-colors ${FOCUS_RING} ${
                facility.id === currentFacility?.id
                  ? "font-semibold text-primary-text bg-primary-soft"
                  : "font-medium text-secondary hover:bg-primary-hover"
              }`}
            >
              {facility.name}
              <span className="block text-[10.5px] font-medium text-muted">{facility.code}</span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function TopBar({ onOpenSidebar }: { onOpenSidebar: () => void }) {
  const { session, signOut } = useSession();
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const { can } = useSession();

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    function onDocumentClick(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setMenuOpen(false);
    }
    document.addEventListener("mousedown", onDocumentClick);
    return () => document.removeEventListener("mousedown", onDocumentClick);
  }, []);

  const displayName = session?.user.full_name || session?.user.username || "";
  const initials = session?.user.username.slice(0, 2).toUpperCase() ?? "";

  return (
    <header className="sticky top-0 z-30 h-[72px] bg-canvas/95 backdrop-blur border-b border-line">
      <div className="flex h-full items-center gap-4 px-5 lg:px-7">
        <button
          type="button"
          aria-label="Open navigation"
          onClick={onOpenSidebar}
          className={`md:hidden h-10 w-10 shrink-0 rounded-[12px] border border-line bg-white grid place-items-center text-ink shadow-card hover:bg-surface-muted active:scale-[0.97] transition-all ${FOCUS_RING}`}
        >
          <IconMenu className="h-[18px] w-[18px]" />
        </button>

        {can("patient.view") ? (
          <div className="flex-1 flex justify-center px-2">
            <form
              className="relative flex items-center w-full max-w-[600px]"
              onSubmit={(event) => {
                event.preventDefault();
                const term = search.trim();
                router.push(term ? `/patients?q=${encodeURIComponent(term)}` : "/patients");
              }}
            >
              <IconSearch className="pointer-events-none absolute left-4 h-[18px] w-[18px] text-muted" />
              <input
                ref={searchRef}
                type="search"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search patients…"
                aria-label="Search patients"
                className={`h-11 w-full rounded-[14px] border border-line bg-white pl-11 pr-16 text-[13px] font-medium text-ink placeholder-muted shadow-card focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition-shadow ${FOCUS_RING}`}
              />
              <span className="absolute right-3 flex items-center gap-1" aria-hidden="true">
                <kbd className="hidden sm:inline-flex rounded-md border border-line bg-canvas px-1.5 py-0.5 text-[11px] font-semibold text-muted">
                  Ctrl
                </kbd>
                <kbd className="hidden sm:inline-flex rounded-md border border-line bg-canvas px-1.5 py-0.5 text-[11px] font-semibold text-muted">
                  K
                </kbd>
              </span>
            </form>
          </div>
        ) : (
          <div className="flex-1" />
        )}

        <div className="flex items-center gap-2 shrink-0">
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen((value) => !value)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              className={`ml-1 flex items-center gap-2.5 rounded-full py-1 pl-1 pr-2 hover:bg-white transition-colors ${FOCUS_RING}`}
            >
              <span className="h-9 w-9 rounded-full bg-gradient-to-br from-[#8B6DFF] to-primary grid place-items-center text-white text-[12px] font-semibold ring-2 ring-white">
                {initials}
              </span>
              <span className="hidden xl:block text-[13px] font-semibold text-ink">{displayName}</span>
              <IconChevronDown className="h-4 w-4 text-muted" />
            </button>
            {menuOpen ? (
              <div
                role="menu"
                className="absolute right-0 z-20 mt-2 w-56 rounded-[14px] border border-line bg-white p-1.5 shadow-elevated"
              >
                <div className="px-3 py-2.5 border-b border-line-soft">
                  <p className="text-[13px] font-semibold text-ink">{displayName}</p>
                  <p className="mt-0.5 text-[11.5px] font-medium text-muted">
                    {session ? roleLabel(session) : ""} · {session?.user.username}
                  </p>
                </div>
                <button
                  type="button"
                  role="menuitem"
                  onClick={async () => {
                    setMenuOpen(false);
                    await signOut();
                    router.replace("/login");
                  }}
                  className={`mt-1 w-full flex items-center gap-3 rounded-[10px] px-3 py-2.5 text-[13px] font-medium text-secondary hover:bg-accent-pink-soft hover:text-accent-pink transition-colors ${FOCUS_RING}`}
                >
                  <IconLogout className="h-[18px] w-[18px]" />
                  Sign out
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  );
}

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  const { session, signOut } = useSession();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const displayName = session?.user.full_name || session?.user.username || "";

  return (
    <div className="min-h-screen">
      {/* Sidebar: icon rail from md, full from lg */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden md:flex w-[76px] lg:w-[264px] flex-col bg-white border-r border-line">
        <div className="flex items-center gap-3 px-4 lg:px-5 h-[76px] shrink-0 justify-center lg:justify-start">
          <BrandMark className="h-9 w-9 shrink-0" />
          <div className="hidden lg:block leading-tight">
            <div className="text-[16px] font-bold tracking-[0.02em] text-ink">KLINKLIK</div>
            <div className="text-[11px] font-medium text-muted">Clinic Management System</div>
          </div>
        </div>

        <SidebarNav />

        <div className="hidden lg:block px-4 pb-4 space-y-3 shrink-0">
          <FacilitySwitcher />
          <div className="flex items-center gap-3 rounded-[14px] border border-line bg-white p-2.5">
            <AvatarInitials name={displayName} />
            <span className="flex-1 leading-tight">
              <span className="block text-[12.5px] font-semibold text-ink">{displayName}</span>
              <span className="block text-[11px] font-medium text-muted">{session ? roleLabel(session) : ""}</span>
              <span className="mt-0.5 flex items-center gap-1 text-[10.5px] font-medium text-accent-teal">
                <span className="h-1.5 w-1.5 rounded-full bg-accent-teal" />
                Online
              </span>
            </span>
          </div>
          <button
            type="button"
            onClick={async () => {
              await signOut();
              router.replace("/login");
            }}
            className={`w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-secondary hover:bg-accent-pink-soft hover:text-accent-pink transition-colors ${FOCUS_RING}`}
          >
            <IconLogout className="h-[18px] w-[18px]" />
            Log out
          </button>
        </div>
      </aside>

      {/* Mobile sidebar overlay */}
      {mobileOpen ? (
        <div className="md:hidden fixed inset-0 z-50">
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
            className="absolute inset-0 bg-ink/30 backdrop-blur-[2px]"
          />
          <aside className="absolute inset-y-0 left-0 w-[264px] flex flex-col bg-white border-r border-line shadow-elevated">
            <div className="flex items-center gap-3 px-5 h-[76px] shrink-0">
              <BrandMark className="h-9 w-9 shrink-0" />
              <div className="leading-tight">
                <div className="text-[16px] font-bold tracking-[0.02em] text-ink">KLINKLIK</div>
                <div className="text-[11px] font-medium text-muted">Clinic Management System</div>
              </div>
            </div>
            <SidebarNav onNavigate={() => setMobileOpen(false)} />
            <div className="px-4 pb-4 space-y-3 shrink-0">
              <FacilitySwitcher />
              <button
                type="button"
                onClick={async () => {
                  setMobileOpen(false);
                  await signOut();
                  router.replace("/login");
                }}
                className={`w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium text-secondary hover:bg-accent-pink-soft hover:text-accent-pink transition-colors ${FOCUS_RING}`}
              >
                <IconLogout className="h-[18px] w-[18px]" />
                Log out
              </button>
            </div>
          </aside>
        </div>
      ) : null}

      <div className="md:pl-[76px] lg:pl-[264px]">
        <TopBar onOpenSidebar={() => setMobileOpen(true)} />
        <main className="px-5 lg:px-7 pt-6 pb-8 space-y-5">{children}</main>
      </div>
    </div>
  );
}
