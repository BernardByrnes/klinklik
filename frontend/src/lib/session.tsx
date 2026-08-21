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

type SessionContextValue = {
  session: ApiSession | null;
  restoring: boolean;
  signIn: (username: string, password: string, organisationId?: string) => Promise<ApiSession>;
  signOut: () => Promise<void>;
  switchFacility: (facilityId: string) => void;
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
      const opened = await apiLogin(username, password, organisationId);
      const firstFacility = opened.facilities[0]?.id ?? null;
      setFacilityId(firstFacility);
      setSession(opened);
      setFacilityIdState(firstFacility);
      return opened;
    },
    [],
  );

  const signOut = useCallback(async () => {
    await apiLogout();
    queryClient.clear();
    setSession(null);
    setFacilityIdState(null);
  }, [queryClient]);

  const switchFacility = useCallback(
    (id: string) => {
      setFacilityId(id);
      setFacilityIdState(id);
      queryClient.invalidateQueries();
    },
    [queryClient],
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
