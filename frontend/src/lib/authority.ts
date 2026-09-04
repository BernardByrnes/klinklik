import { useSyncExternalStore } from "react";

export type AuthoritySnapshot = Readonly<{
  epoch: number;
  organisationId: string | null;
  facilityId: string | null;
}>;

type QueryKeyPart = string | number | boolean | null | undefined;

const INITIAL_SNAPSHOT: AuthoritySnapshot = {
  epoch: 0,
  organisationId: null,
  facilityId: null,
};

let snapshot = INITIAL_SNAPSHOT;
const listeners = new Set<() => void>();

function publish(organisationId: string | null, facilityId: string | null) {
  snapshot = {
    epoch: snapshot.epoch + 1,
    organisationId,
    facilityId,
  };
  for (const listener of listeners) listener();
}

export function setAuthoritySession(organisationId: string, facilityId: string | null) {
  publish(organisationId, facilityId);
}

export function setAuthorityFacility(facilityId: string | null) {
  publish(snapshot.organisationId, facilityId);
}

export function clearAuthority() {
  publish(null, null);
}

export function subscribeAuthority(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function getAuthoritySnapshot(): AuthoritySnapshot {
  return snapshot;
}

export function isCurrentAuthority(origin: AuthoritySnapshot): boolean {
  const current = getAuthoritySnapshot();
  return (
    current.epoch === origin.epoch &&
    current.organisationId === origin.organisationId &&
    current.facilityId === origin.facilityId
  );
}

export function protectedQueryKey(resourceIdentity: string, ...parts: QueryKeyPart[]) {
  const current = getAuthoritySnapshot();
  return [
    current.epoch,
    current.organisationId ?? "",
    current.facilityId ?? "",
    resourceIdentity,
    ...parts,
  ] as const;
}

export function useAuthoritySnapshot(): AuthoritySnapshot {
  return useSyncExternalStore(
    subscribeAuthority,
    getAuthoritySnapshot,
    () => INITIAL_SNAPSHOT,
  );
}

export function useProtectedQueryKey(resourceIdentity: string, ...parts: QueryKeyPart[]) {
  const current = useAuthoritySnapshot();
  return [
    current.epoch,
    current.organisationId ?? "",
    current.facilityId ?? "",
    resourceIdentity,
    ...parts,
  ] as const;
}
