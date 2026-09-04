"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  ApiSession,
  Facility,
  login as apiLogin,
  logout as apiLogout,
  restoreSession,
  setFacilityId,
} from "./api";
import { subscribeAuthority } from "./authority";
import { clearProtectedState } from "./query-state";

type SessionContextValue = {
  session: ApiSession | null;
  restoring: boolean;
  signIn: (username: string, password: string, organisationId?: string) => Promise<ApiSession>;
  signOut: () => Promise<void>;
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

  useEffect(() => {
    return subscribeAuthority(() => {
      void clearProtectedState(queryClient).catch(() => undefined);
    });
  }, [queryClient]);

  useEffect(() => {
    let mounted = true;
    restoreSession()
      .then((restored) => {
        if (mounted && restored) {
          setSession(restored);
          setFacilityIdState(restored.facilities[0]?.id ?? null);
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

  const signIn = useCallback(
    async (username: string, password: string, organisationId?: string) => {
      await clearProtectedState(queryClient);
      const opened = await apiLogin(username, password, organisationId);
      const firstFacility = opened.facilities[0]?.id ?? null;
      setSession(opened);
      setFacilityIdState(firstFacility);
      return opened;
    },
    [queryClient],
  );

  const signOut = useCallback(async () => {
    try {
      await clearProtectedState(queryClient);
      await apiLogout();
    } finally {
      setSession(null);
      setFacilityIdState(null);
    }
  }, [queryClient]);

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
      switchFacility,
      can: (capability: string) => Boolean(session?.capabilities.includes(capability)),
      currentFacility: session?.facilities.find((facility) => facility.id === facilityId) ?? session?.facilities[0],
    }),
    [session, facilityId, restoring, signIn, signOut, switchFacility],
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
