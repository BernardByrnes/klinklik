import type { SessionResponse } from "../generated/api-client";

import {
  clearAuthority,
  getAuthoritySnapshot,
  isCurrentAuthority,
  setAuthorityFacility,
  setAuthoritySession,
  type AuthoritySnapshot,
} from "./authority";
import { markSyncFailure, markSyncStart, markSyncSuccess, viewFromPath } from "./connectivity";
import { automaticRefreshAllowed, markAuthReordered } from "./exit-marker";

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
let sessionGeneration = 0;
let restoreInFlight: Promise<ApiSession | null> | null = null;
let restoreController: AbortController | null = null;
let logoutController: AbortController | null = null;
const activeProtectedControllers = new Set<AbortController>();

export function resetLocalAuth() {
  sessionGeneration += 1;
  accessToken = null;
  facilityId = null;
  clearAuthority();
}

export function cancelProtectedRequests() {
  for (const controller of activeProtectedControllers) controller.abort();
  activeProtectedControllers.clear();
}

function abortRestoreRequest() {
  if (restoreController || restoreInFlight) markAuthReordered();
  restoreController?.abort();
  restoreController = null;
  restoreInFlight = null;
}

// Cookie-changing requests are serialized per session generation. JavaScript
// cannot undo a Set-Cookie that has already reached the browser, so a newer
// login must cancel older refresh/logout requests BEFORE it sends its own
// request. State generation guards alone cannot protect the cookie jar.
export function prepareAuthForNewLogin() {
  if (restoreController || logoutController || restoreInFlight) markAuthReordered();
  abortRestoreRequest();
  logoutController?.abort();
  logoutController = null;
}

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getFacilityId() {
  return facilityId;
}

export function setFacilityId(id: string | null) {
  if (facilityId === id) return;
  facilityId = id;
  setAuthorityFacility(id);
}

export function restoreSession(): Promise<ApiSession | null> {
  if (!automaticRefreshAllowed()) return Promise.resolve(null);
  if (!restoreInFlight) {
    const controller = new AbortController();
    restoreController = controller;
    restoreInFlight = (async () => {
      const origin = getAuthoritySnapshot();
      const generation = sessionGeneration;
      const previousOrganisation = origin.organisationId;
      const previousFacility = origin.facilityId ?? facilityId;
      markSyncStart();
      try {
        const response = await fetch(API_URL + "/api/v1/auth/refresh/", {
          method: "POST",
          credentials: "include",
          signal: controller.signal,
        });
        if (!response.ok) {
          if (generation === sessionGeneration) resetLocalAuth();
          markSyncFailure();
          return null;
        }
        const data = (await response.json()) as ApiSession;
        if (!isCurrentAuthority(origin) || generation !== sessionGeneration) {
          markSyncFailure();
          return null;
        }
        const keepFacility =
          previousOrganisation === data.organisation.id &&
          Boolean(previousFacility) &&
          data.facilities.some((facility) => facility.id === previousFacility);
        const restoredFacility = keepFacility
          ? previousFacility
          : data.facilities[0]?.id || null;
        accessToken = data.access_token;
        facilityId = restoredFacility;
        sessionGeneration += 1;
        setAuthoritySession(data.organisation.id, restoredFacility);
        markSyncSuccess("Workspace");
        return data;
      } catch (error) {
        if (generation === sessionGeneration) resetLocalAuth();
        markSyncFailure();
        throw error;
      } finally {
        if (restoreController === controller) restoreController = null;
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
  // Cancel any older cookie-writing request before this login sends. A stale
  // refresh/logout response delivered afterwards would overwrite or delete the
  // new user's refresh cookie, which JavaScript cannot repair.
  prepareAuthForNewLogin();
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
  sessionGeneration += 1;
  setAuthoritySession(data.organisation.id, facilityId);
  return data as ApiSession;
}

export async function logout(): Promise<{ revoked: boolean; owned: boolean }> {
  cancelProtectedRequests();
  abortRestoreRequest();
  const controller = new AbortController();
  logoutController = controller;
  const generation = sessionGeneration;
  const bearer = accessToken;
  const exitFacility = facilityId;
  let revoked = false;
  let owned = false;
  try {
    if (bearer) {
      const response = await fetch(API_URL + "/api/v1/auth/logout/", {
        method: "POST",
        credentials: "include",
        signal: controller.signal,
        headers: {
          Authorization: "Bearer " + bearer,
          ...(exitFacility ? { "X-Facility-Id": exitFacility } : {}),
        },
      });
      revoked = response.ok;
    }
  } catch {
    revoked = false;
  } finally {
    if (logoutController === controller) logoutController = null;
    // A newer explicit sign-in owns the module state now; never clear it from
    // an older exit request that completes late.
    owned = generation === sessionGeneration;
    if (owned) {
      accessToken = null;
      facilityId = null;
      clearAuthority();
    }
  }
  return { revoked, owned };
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
  const view = viewFromPath(path);
  const tracked = retry;
  if (tracked) markSyncStart();
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
    let succeeded = false;
    const response = await fetch(API_URL + path, {
      ...init,
      headers,
      credentials: "include",
      signal: controller.signal,
    });
    if (!isCurrentAuthority(origin)) throw new StaleAuthorityResponseError();
    if (response.status === 401 && retry && (await refreshAccessToken())) {
      if (!isCurrentAuthority(origin)) throw new StaleAuthorityResponseError();
      if (tracked) markSyncSuccess(view);
      return apiRequest<T>(path, init, false);
    }
    const text = await response.text();
    const data = text ? JSON.parse(text) : null;
    if (!isCurrentAuthority(origin)) throw new StaleAuthorityResponseError();
    if (!response.ok) {
      throw new ApiRequestError(response.status, data, response.headers);
    }
    succeeded = true;
    if (tracked) markSyncSuccess(view);
    return data as T;
  } catch (error) {
    if (tracked) markSyncFailure();
    throw error;
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
