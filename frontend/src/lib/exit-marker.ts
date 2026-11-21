"use client";

// Boolean-only, cross-reload markers for a deliberate workstation exit.
// No identity, token, facility, pending work or clinical data is stored here.
export const EXPLICIT_SIGNIN_KEY = "klinklik:explicit-signin-required";
export const LOGOUT_UNCONFIRMED_KEY = "klinklik:logout-unconfirmed";
export const EXIT_MARKER_EVENT = "klinklik:exit-marker-changed";

type MarkerChange = Readonly<{ key: string; value: boolean }>;

function read(key: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function write(key: string, value: boolean) {
  if (typeof window === "undefined") return;
  try {
    if (value) window.localStorage.setItem(key, "1");
    else window.localStorage.removeItem(key);
  } catch {
    // Blocked storage cannot stop the exit; persistence is simply unavailable.
  }
  try {
    window.dispatchEvent(
      new CustomEvent<MarkerChange>(EXIT_MARKER_EVENT, { detail: { key, value } }),
    );
  } catch {
    // An observer failure must never break the exit either.
  }
}

export function markExplicitSignInRequired() {
  write(EXPLICIT_SIGNIN_KEY, true);
}

export function clearExitMarkers() {
  write(EXPLICIT_SIGNIN_KEY, false);
  write(LOGOUT_UNCONFIRMED_KEY, false);
}

export function explicitSignInRequired() {
  return read(EXPLICIT_SIGNIN_KEY);
}

export function markLogoutUnconfirmed() {
  write(LOGOUT_UNCONFIRMED_KEY, true);
}

export function logoutUnconfirmed() {
  return read(LOGOUT_UNCONFIRMED_KEY);
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
