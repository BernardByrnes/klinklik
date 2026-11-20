"use client";

import { useEffect, useSyncExternalStore } from "react";

import { getAuthoritySnapshot, type AuthoritySnapshot } from "./authority";

export type PendingIntent = Readonly<{
  id: string;
  operation: string;
  target: string;
  authority: AuthoritySnapshot;
  createdAt: number;
  retry: () => Promise<void>;
}>;

type Listener = () => void;

const intents = new Map<string, PendingIntent>();
const listeners = new Set<Listener>();
let counter = 0;
let cachedIntents: PendingIntent[] = [];

function publish() {
  cachedIntents = [...intents.values()];
  for (const listener of listeners) listener();
}

export function registerIntent(input: {
  operation: string;
  target: string;
  retry: () => Promise<void>;
}): string {
  counter += 1;
  const id = `intent-${counter}`;
  intents.set(id, {
    id,
    operation: input.operation,
    target: input.target,
    authority: getAuthoritySnapshot(),
    createdAt: Date.now(),
    retry: input.retry,
  });
  publish();
  return id;
}

export function resolveIntent(id: string | null | undefined) {
  if (!id || !intents.delete(id)) return;
  publish();
}

export function clearIntents() {
  if (intents.size === 0) return;
  intents.clear();
  publish();
}

export function getPendingIntents(): PendingIntent[] {
  return cachedIntents;
}

export function subscribeIntents(listener: Listener) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function usePendingIntents() {
  return useSyncExternalStore(subscribeIntents, getPendingIntents, () => [] as PendingIntent[]);
}
