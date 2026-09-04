import type { QueryClient } from "@tanstack/react-query";

import { cancelProtectedRequests } from "./api";

export async function clearProtectedState(queryClient: QueryClient) {
  cancelProtectedRequests();
  const isProtectedQuery = (query: { queryKey: readonly unknown[] }) =>
    typeof query.queryKey[0] === "number" && query.queryKey.length >= 4;
  await queryClient.cancelQueries({ predicate: isProtectedQuery });
  queryClient.removeQueries({ predicate: isProtectedQuery });
  queryClient.getMutationCache().clear();
}
