import { ApiRequestError, StaleAuthorityResponseError } from "./api";

export function isIdempotencyInProgress(reason: unknown): boolean {
  if (!(reason instanceof ApiRequestError) || reason.status !== 409) return false;
  const data = reason.data;
  return Boolean(
    data &&
      typeof data === "object" &&
      "code" in data &&
      (data as { code?: unknown }).code === "IDEMPOTENCY_IN_PROGRESS",
  );
}

export function isStaleAuthorityFailure(reason: unknown): boolean {
  return reason instanceof StaleAuthorityResponseError;
}

export function isDefiniteFailure(reason: unknown): boolean {
  if (isStaleAuthorityFailure(reason) || isIdempotencyInProgress(reason)) return false;
  if (!(reason instanceof ApiRequestError)) return false;
  return reason.status < 500 && reason.status !== 408 && reason.status !== 429;
}

export function shouldRegisterIntent(reason: unknown): boolean {
  return !isDefiniteFailure(reason) && !isStaleAuthorityFailure(reason);
}
