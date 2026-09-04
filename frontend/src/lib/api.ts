import type { SessionResponse } from "../generated/api-client";

import {
  clearAuthority,
  getAuthoritySnapshot,
  isCurrentAuthority,
  setAuthorityFacility,
  setAuthoritySession,
  type AuthoritySnapshot,
} from "./authority";

export type ApiSession = SessionResponse;
export type RoleGrant = SessionResponse["roles"][number];
export type Facility = SessionResponse["facilities"][number];

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export class ApiRequestError extends Error {
  readonly status: number;
  readonly data: unknown;
  readonly headers: Headers;

  constructor(status: number, data: unknown, headers: Headers) {
    const detail =
      data && typeof data === "object" && "detail" in data && typeof data.detail === "string"
        ? data.detail
        : "The request could not be completed.";
    super(detail);
    this.name = "ApiRequestError";
    this.status = status;
    this.data = data;
    this.headers = new Headers(headers);
  }
}

export class StaleAuthorityResponseError extends Error {
  constructor() {
    super("The response belongs to an earlier authority or facility context.");
    this.name = "StaleAuthorityResponseError";
  }
}

let accessToken: string | null = null;
let facilityId: string | null = null;
const activeProtectedControllers = new Set<AbortController>();

export function cancelProtectedRequests() {
  for (const controller of activeProtectedControllers) controller.abort();
  activeProtectedControllers.clear();
}

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function setFacilityId(id: string | null) {
  if (facilityId === id) return;
  facilityId = id;
  setAuthorityFacility(id);
}

let restoreInFlight: Promise<ApiSession | null> | null = null;

export function restoreSession(): Promise<ApiSession | null> {
  if (!restoreInFlight) {
    restoreInFlight = (async () => {
      try {
        const response = await fetch(API_URL + "/api/v1/auth/refresh/", {
          method: "POST",
          credentials: "include",
        });
        if (!response.ok) {
          accessToken = null;
          facilityId = null;
          clearAuthority();
          return null;
        }
        const data = (await response.json()) as ApiSession;
        accessToken = data.access_token;
        facilityId = data.facilities[0]?.id || null;
        setAuthoritySession(data.organisation.id, facilityId);
        return data;
      } catch (error) {
        accessToken = null;
        facilityId = null;
        clearAuthority();
        throw error;
      } finally {
        restoreInFlight = null;
      }
    })();
  }
  return restoreInFlight;
}

async function refreshAccessToken() {
  return Boolean(await restoreSession());
}
export async function login(username: string, password: string, organisationId?: string) {
  const response = await fetch(API_URL + "/api/v1/auth/login/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      username,
      password,
      ...(organisationId ? { organisation_id: organisationId } : {}),
    }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "Could not sign in.");
  }
  accessToken = data.access_token;
  facilityId = data.facilities[0]?.id || null;
  setAuthoritySession(data.organisation.id, facilityId);
  return data as ApiSession;
}

export async function logout() {
  cancelProtectedRequests();
  try {
    if (accessToken) {
      await fetch(API_URL + "/api/v1/auth/logout/", {
        method: "POST",
        credentials: "include",
        headers: {
          Authorization: "Bearer " + accessToken,
          ...(facilityId ? { "X-Facility-Id": facilityId } : {}),
        },
      });
    }
  } finally {
    accessToken = null;
    facilityId = null;
    clearAuthority();
  }
}

function attachExternalAbort(signal: AbortSignal | null | undefined, controller: AbortController) {
  if (!signal) return () => undefined;
  if (signal.aborted) {
    controller.abort(signal.reason);
    return () => undefined;
  }
  const abort = () => controller.abort(signal.reason);
  signal.addEventListener("abort", abort, { once: true });
  return () => signal.removeEventListener("abort", abort);
}

export async function apiRequest<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const origin: AuthoritySnapshot = getAuthoritySnapshot();
  const controller = new AbortController();
  const removeExternalAbort = attachExternalAbort(init.signal, controller);
  activeProtectedControllers.add(controller);
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (accessToken) {
    headers.set("Authorization", "Bearer " + accessToken);
  }
  if (facilityId) {
    headers.set("X-Facility-Id", facilityId);
  }
  try {
    const response = await fetch(API_URL + path, {
      ...init,
      headers,
      credentials: "include",
      signal: controller.signal,
    });
    if (!isCurrentAuthority(origin)) throw new StaleAuthorityResponseError();
    if (response.status === 401 && retry && (await refreshAccessToken())) {
      if (!isCurrentAuthority(origin)) throw new StaleAuthorityResponseError();
      return apiRequest<T>(path, init, false);
    }
    const text = await response.text();
    const data = text ? JSON.parse(text) : null;
    if (!isCurrentAuthority(origin)) throw new StaleAuthorityResponseError();
    if (!response.ok) {
      throw new ApiRequestError(response.status, data, response.headers);
    }
    return data as T;
  } finally {
    removeExternalAbort();
    activeProtectedControllers.delete(controller);
  }
}

export function newIdempotencyKey(prefix: string) {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.trunc(Math.random() * 1_000_000)}`;
}
