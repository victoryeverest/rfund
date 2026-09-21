"use client";

/**
 * Apollo React provider wrapper (Apollo Client v4).
 *
 * `ApolloProvider` and the React hooks live in `@apollo/client/react` since
 * v4; the client instance itself is created once in `@/lib/graphql`.
 * This wrapper keeps the root layout (a Server Component) clean — it only
 * imports this client-boundary file.
 */

import { ApolloProvider } from "@apollo/client/react";
import { apolloClient } from "@/lib/graphql";

export function ApolloWrapper({ children }: { children: React.ReactNode }) {
  return <ApolloProvider client={apolloClient}>{children}</ApolloProvider>;
}
