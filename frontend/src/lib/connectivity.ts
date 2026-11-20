"use client";

import { useEffect, useState, useSyncExternalStore } from "react";

export type ConnectivitySnapshot = Readonly<{
  online: boolean;
  lastSyncAt: number | null;
  lastSyncView: string | null;
  byView: Readonly<Record<string, number>>;
  pendingSyncs: number;
}>;

type Listener = () => void;

const INITIAL: ConnectivitySnapshot = {
  online: true,
  lastSyncAt: null,
  lastSyncView: null,
  byView: {},
  pendingSyncs: 0,
};

let snapshot: ConnectivitySnapshot = INITIAL;
const listeners = new Set<Listener>();
let started = false;

function publish(next: ConnectivitySnapshot) {
  snapshot = next;
  for (const listener of listeners) listener();
}

export function viewFromRoute(path: string): string {
  if (path.startsWith("/patients")) return "Patients";
  if (path.startsWith("/billing")) return "Billing";
  if (path.startsWith("/lab")) return "Laboratory";
  if (path.startsWith("/pharmacy")) return "Pharmacy";
  if (path.startsWith("/inventory")) return "Inventory";
  if (path.startsWith("/consultations")) return "Consultations";
  if (path.startsWith("/queue")) return "Queue";
  return "Workspace";
}

export function viewFromPath(path: string): string {
  if (path.startsWith("/api/v1/reception")) return "Patients";
  if (path.startsWith("/api/v1/billing")) return "Billing";
  if (path.startsWith("/api/v1/lab")) return "Laboratory";
  if (path.startsWith("/api/v1/pharmacy")) return "Pharmacy";
  if (path.startsWith("/api/v1/inventory")) return "Inventory";
  if (path.startsWith("/api/v1/clinic") || path.startsWith("/api/v1/clinical")) return "Consultations";
  if (path.startsWith("/api/v1/scheduling") || path.startsWith("/api/v1/queue")) return "Queue";
  return "Workspace";
}

export function markSyncStart() {
  publish({ ...snapshot, pendingSyncs: snapshot.pendingSyncs + 1 });
}

export function markSyncSuccess(view: string) {
  const at = Date.now();
  publish({
    ...snapshot,
    online: true,
    pendingSyncs: Math.max(0, snapshot.pendingSyncs - 1),
    lastSyncAt: at,
    lastSyncView: view,
    byView: { ...snapshot.byView, [view]: at },
  });
}

export function markSyncFailure() {
  publish({
    ...snapshot,
    pendingSyncs: Math.max(0, snapshot.pendingSyncs - 1),
  });
}

export function setOnline(online: boolean) {
  if (snapshot.online === online) return;
  publish({ ...snapshot, online });
}

export function startConnectivityMonitor() {
  if (started || typeof window === "undefined") return () => undefined;
  started = true;
  const update = () => setOnline(navigator.onLine !== false);
  update();
  window.addEventListener("online", update);
  window.addEventListener("offline", update);
  return () => {
    window.removeEventListener("online", update);
    window.removeEventListener("offline", update);
    started = false;
  };
}

export function subscribeConnectivity(listener: Listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getConnectivitySnapshot() {
  return snapshot;
}

export function useConnectivity() {
  useEffect(() => startConnectivityMonitor(), []);
  return useSyncExternalStore(subscribeConnectivity, getConnectivitySnapshot, () => INITIAL);
}

export function lastSyncForView(view: string): number | null {
  return snapshot.byView[view] ?? null;
}

export function formatSyncTime(at: number | null): string {
  if (!at) return "not yet synced";
  return new Date(at).toLocaleTimeString();
}
