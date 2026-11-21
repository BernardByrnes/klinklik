"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  ApiSession,
  Facility,
  cancelProtectedRequests,
  getFacilityId,
  login as apiLogin,
  logout as apiLogout,
  resetLocalAuth,
  restoreSession,
  setFacilityId,
} from "./api";
import { clearAuthority, subscribeAuthority } from "./authority";
import { resetConnectivity } from "./connectivity";
import {
  EXPLICIT_SIGNIN_KEY,
  clearExitMarkers,
  explicitSignInRequired,
  markExplicitSignInRequired,
  markLogoutUnconfirmed,
} from "./exit-marker";
import { clearIntents } from "./intent-registry";
import { clearProtectedState } from "./query-state";

type SessionContextValue = {
  session: ApiSession | null;
  restoring: boolean;
  signIn: (username: string, password: string, organisationId?: string) => Promise<ApiSession>;
  signOut: () => Promise<void>;
  switchUser: () => Promise<void>;
  switchFacility: (facilityId: string) => Promise<void>;
  can: (capability: string) => boolean;
  currentFacility: Facility | undefined;
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<ApiSession | null>(null);
  const [facilityId, setFacilityIdState] = useState<string | null>(null);
  const [restoring, setRestoring] = useState(true);
  const sessionRef = useRef<ApiSession | null>(null);
  sessionRef.current = session;

  useEffect(() => {
    const unsubscribe = subscribeAuthority(() => {
      resetConnectivity();
      void clearProtectedState(queryClient).catch(() => undefined);
    });
    return () => {
      unsubscribe();
    };
  }, [queryClient]);

  useEffect(() => {
    // A deliberate workstation exit suppresses automatic refresh until the
    // next user signs in explicitly.
    if (explicitSignInRequired()) {
      setRestoring(false);
      return;
    }
    let mounted = true;
    restoreSession()
      .then((restored) => {
        if (mounted && restored) {
          const restoredFacility = getFacilityId();
          setSession(restored);
          setFacilityIdState(restoredFacility);
        }
      })
      .catch(() => {
        /* no session; stay signed out */
      })
      .finally(() => {
        if (mounted) setRestoring(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const clearForExitEvent = useCallback(() => {
    if (!explicitSignInRequired()) return;
    cancelProtectedRequests();
    clearIntents();
    resetConnectivity();
    resetLocalAuth();
    setSession(null);
    setFacilityIdState(null);
    void clearProtectedState(queryClient).catch(() => undefined);
  }, [queryClient]);

  useEffect(() => {
    function onStorage(event: StorageEvent) {
      if (event.key === EXPLICIT_SIGNIN_KEY && event.newValue === "1") clearForExitEvent();
    }
    function onVisibility() {
      if (!document.hidden && explicitSignInRequired() && sessionRef.current) clearForExitEvent();
    }
    window.addEventListener("storage", onStorage);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("storage", onStorage);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [clearForExitEvent]);

  const signIn = useCallback(
    async (username: string, password: string, organisationId?: string) => {
      await clearProtectedState(queryClient);
      const opened = await apiLogin(username, password, organisationId);
      clearExitMarkers();
      const firstFacility = opened.facilities[0]?.id ?? null;
      setSession(opened);
      setFacilityIdState(firstFacility);
      setRestoring(false);
      return opened;
    },
    [queryClient],
  );

  const performExit = useCallback(async () => {
    // All local invalidation starts before the network request is awaited.
    markExplicitSignInRequired();
    cancelProtectedRequests();
    clearIntents();
    resetConnectivity();
    setSession(null);
    setFacilityIdState(null);
    clearAuthority();
    const cleanup = clearProtectedState(queryClient);
    await cleanup;
    const { revoked, owned } = await apiLogout();
    if (!revoked && owned) markLogoutUnconfirmed();
  }, [queryClient]);

  const signOut = useCallback(() => performExit(), [performExit]);
  const switchUser = useCallback(() => performExit(), [performExit]);

  const switchFacility = useCallback(
    async (id: string) => {
      if (!session?.facilities.some((facility) => facility.id === id)) return;
      await clearProtectedState(queryClient);
      setFacilityId(id);
      setFacilityIdState(id);
    },
    [queryClient, session],
  );

  const value = useMemo<SessionContextValue>(
    () => ({
      session,
      restoring,
      signIn,
      signOut,
      switchUser,
      switchFacility,
      can: (capability: string) => Boolean(session?.capabilities.includes(capability)),
      currentFacility: session?.facilities.find((facility) => facility.id === facilityId) ?? session?.facilities[0],
    }),
    [session, facilityId, restoring, signIn, signOut, switchUser, switchFacility],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) {
    throw new Error("useSession must be used inside SessionProvider");
  }
  return context;
}
