"use client";

// Boolean-only, cross-reload markers for a deliberate workstation exit.
// No identity, token, facility, pending work or clinical data is stored here.
export const EXPLICIT_SIGNIN_KEY = "klinklik:explicit-signin-required";
export const LOGOUT_UNCONFIRMED_KEY = "klinklik:logout-unconfirmed";

function read(key: string): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(key) === "1";
}

function write(key: string, value: boolean) {
  if (typeof window === "undefined") return;
  if (value) window.localStorage.setItem(key, "1");
  else window.localStorage.removeItem(key);
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
