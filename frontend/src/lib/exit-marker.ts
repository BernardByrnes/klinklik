"use client";

// Boolean-only, cross-reload markers for a deliberate workstation exit.
// No identity, token, facility, pending work or clinical data is stored here.
export const EXPLICIT_SIGNIN_KEY = "klinklik:explicit-signin-required";
export const LOGOUT_UNCONFIRMED_KEY = "klinklik:logout-unconfirmed";
export const EXIT_MARKER_EVENT = "klinklik:exit-marker-changed";

type MarkerChange = Readonly<{ key: string; value: boolean }>;
type MarkerStore = "localStorage" | "cookie";

const PROBE_KEY = "klinklik:marker-probe";
const PROBE_COOKIE = "klinklik_marker_probe";
const MARKER_KEYS = [EXPLICIT_SIGNIN_KEY, LOGOUT_UNCONFIRMED_KEY] as const;

const ONE_DAY_SECONDS = 24 * 60 * 60;

// Fallback for an older backend that does not report its effective lifetime.
const configuredRefreshDays = Number(process.env.NEXT_PUBLIC_REFRESH_TOKEN_DAYS ?? "7");
const REFRESH_TOKEN_DAYS =
  Number.isFinite(configuredRefreshDays) && configuredRefreshDays >= 1
    ? Math.floor(configuredRefreshDays)
    : 7;
const FALLBACK_REFRESH_LIFETIME_SECONDS = REFRESH_TOKEN_DAYS * ONE_DAY_SECONDS;

// The backend reports the lifetime of the refresh cookie it just issued. Keep
// the latest value here; a refresh response replaces it. One extra day covers
// a marker written after the cookie and an immediate refresh before exit.
let effectiveRefreshLifetimeSeconds: number | null = null;

export function setEffectiveRefreshLifetime(seconds: unknown) {
  const value = typeof seconds === "number" ? seconds : Number(seconds);
  effectiveRefreshLifetimeSeconds =
    Number.isFinite(value) && value > 0 ? Math.floor(value) : null;
}

export function markerLifetimeSeconds() {
  const lifetime = effectiveRefreshLifetimeSeconds ?? FALLBACK_REFRESH_LIFETIME_SECONDS;
  return lifetime + ONE_DAY_SECONDS;
}

let storeChecked = false;
let reliableStore: MarkerStore | null = null;
let forcedExplicitSignIn = false;

function readLocal(key: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeLocal(key: string, value: boolean): boolean {
  if (typeof window === "undefined") return false;
  try {
    if (value) {
      window.localStorage.setItem(key, "1");
      return window.localStorage.getItem(key) === "1";
    }
    window.localStorage.removeItem(key);
    return window.localStorage.getItem(key) !== "1";
  } catch {
    return false;
  }
}

function cookieName(key: string): string {
  return key === EXPLICIT_SIGNIN_KEY
    ? "klinklik_explicit_signin"
    : "klinklik_logout_unconfirmed";
}

function readCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  const prefix = `${name}=`;
  const entry = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(prefix));
  return entry ? entry.slice(prefix.length) : undefined;
}

function cookieAttributes(value: boolean): string {
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  return `path=/; SameSite=Lax${secure}; Max-Age=${value ? markerLifetimeSeconds() : 0}`;
}

function writeCookie(name: string, value: boolean): boolean {
  if (typeof document === "undefined") return false;
  try {
    document.cookie = `${name}=${value ? "1" : ""}; ${cookieAttributes(value)}`;
    return value ? readCookie(name) === "1" : readCookie(name) === undefined;
  } catch {
    return false;
  }
}

function clearMarkerCookie(name: string) {
  if (typeof document === "undefined") return;
  try {
    document.cookie = `${name}=; ${cookieAttributes(false)}`;
  } catch {
    // Independent clearing attempt; no caller may be blocked by this failure.
  }
}

function probeStores() {
  if (storeChecked) return;
  storeChecked = true;
  if (writeLocal(PROBE_KEY, true)) {
    writeLocal(PROBE_KEY, false);
    reliableStore = "localStorage";
    return;
  }
  if (writeCookie(PROBE_COOKIE, true)) {
    writeCookie(PROBE_COOKIE, false);
    reliableStore = "cookie";
    return;
  }
  reliableStore = null;
}

function notify(key: string, value: boolean) {
  try {
    window.dispatchEvent(
      new CustomEvent<MarkerChange>(EXIT_MARKER_EVENT, { detail: { key, value } }),
    );
  } catch {
    // An observer failure must never break the exit.
  }
}

function writeMarker(key: string, value: boolean) {
  if (typeof window === "undefined") return;
  probeStores();
  let persisted = false;
  if (reliableStore === "localStorage") persisted = writeLocal(key, value);
  if (!persisted) persisted = writeCookie(cookieName(key), value);
  if (!persisted && reliableStore === "localStorage") persisted = writeLocal(key, value);
  if (value && !persisted) forcedExplicitSignIn = true;
  if (!value) forcedExplicitSignIn = false;
  notify(key, value);
}

function readMarker(key: string): boolean {
  if (typeof window === "undefined") return false;
  if (readLocal(key)) return true;
  return readCookie(cookieName(key)) === "1";
}

export function markExplicitSignInRequired() {
  writeMarker(EXPLICIT_SIGNIN_KEY, true);
}

export function clearExitMarkers() {
  forcedExplicitSignIn = false;
  storeChecked = false;
  reliableStore = null;
  for (const key of MARKER_KEYS) {
    writeLocal(key, false);
    clearMarkerCookie(cookieName(key));
    notify(key, false);
  }
  clearMarkerCookie(PROBE_COOKIE);
  writeLocal(PROBE_KEY, false);
}

export function explicitSignInRequired() {
  return forcedExplicitSignIn || readMarker(EXPLICIT_SIGNIN_KEY);
}

export function markLogoutUnconfirmed() {
  writeMarker(LOGOUT_UNCONFIRMED_KEY, true);
}

export function logoutUnconfirmed() {
  return readMarker(LOGOUT_UNCONFIRMED_KEY);
}

export function automaticRefreshAllowed() {
  if (!explicitSignInRequired()) {
    probeStores();
    if (reliableStore !== null) return true;
  }
  return false;
}

export function subscribeExitMarker(listener: (key: string, value: boolean) => void) {
  if (typeof window === "undefined") return () => undefined;
  function onMarker(event: Event) {
    const detail = (event as CustomEvent<MarkerChange>).detail;
    if (detail) listener(detail.key, detail.value);
  }
  function onStorage(event: StorageEvent) {
    if (event.key !== EXPLICIT_SIGNIN_KEY && event.key !== LOGOUT_UNCONFIRMED_KEY) return;
    listener(event.key, event.newValue === "1");
  }
  window.addEventListener(EXIT_MARKER_EVENT, onMarker);
  window.addEventListener("storage", onStorage);
  return () => {
    window.removeEventListener(EXIT_MARKER_EVENT, onMarker);
    window.removeEventListener("storage", onStorage);
  };
}
