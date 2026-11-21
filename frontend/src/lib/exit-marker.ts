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
  const entry = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith(prefix));
  return entry ? entry.slice(prefix.length) : undefined;
}

function writeCookie(name: string, value: boolean): boolean {
  if (typeof document === "undefined") return false;
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${name}=${value ? "1" : ""}; path=/; SameSite=Lax${secure}; Max-Age=${value ? 86400 : 0}`;
  return value ? readCookie(name) === "1" : readCookie(name) === undefined;
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
  writeMarker(EXPLICIT_SIGNIN_KEY, false);
  writeMarker(LOGOUT_UNCONFIRMED_KEY, false);
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
