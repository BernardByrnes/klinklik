import type { QueryClient } from "@tanstack/react-query";

import { cancelProtectedRequests } from "./api";
import { clearIntents } from "./intent-registry";

export async function clearProtectedState(queryClient: QueryClient) {
  cancelProtectedRequests();
  clearIntents();
  const isProtectedQuery = (query: { queryKey: readonly unknown[] }) =>
    typeof query.queryKey[0] === "number" && query.queryKey.length >= 4;
  await queryClient.cancelQueries({ predicate: isProtectedQuery });
  queryClient.removeQueries({ predicate: isProtectedQuery });
  queryClient.getMutationCache().clear();
}
