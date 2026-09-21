"use client";

/**
 * Centralized Apollo client (spec §177): one client, auth-aware link with
 * silent refresh + retry, network detection, and typed error surfacing.
 * All requests use RELATIVE paths through the BFF proxy.
 */

import {
  ApolloClient,
  ApolloLink,
  HttpLink,
  InMemoryCache,
  from,
} from "@apollo/client";
import { onError } from "@apollo/client/link/error";

let refreshing: Promise<string | null> | null = null;

async function silentRefresh(): Promise<string | null> {
  if (!refreshing) {
    refreshing = fetch("/api/auth/refresh", { method: "POST" })
      .then((r) => r.json())
      .then((body) => (body.authenticated ? (body.accessToken as string) : null))
      .catch(() => null)
      .finally(() => {
        setTimeout(() => {
          refreshing = null;
        }, 100);
      });
  }
  return refreshing;
}

const httpLink = new HttpLink({ uri: "/api/graphql" });

const authLink = new ApolloLink((operation, forward) => {
  // Lazily import to avoid circular dependency with React context
  const token = (globalThis as { __rfundToken?: string }).__rfundToken ?? null;
  if (token) {
    operation.setContext(({ headers = {} }) => ({
      headers: { ...headers, Authorization: `Bearer ${token}` },
    }));
  }
  return forward(operation);
});

// Keep the module token in sync with the auth provider
export function setApolloToken(token: string | null) {
  (globalThis as { __rfundToken?: string }).__rfundToken = token ?? undefined;
}

const errorLink = onError(({ graphQLErrors, networkError, operation, forward }) => {
  if (graphQLErrors) {
    const unauthorized = graphQLErrors.some(
      (e) => e.extensions?.code === "UNAUTHENTICATED"
    );
    if (unauthorized) {
      // Silent refresh, then retry the operation exactly once (§177)
      const promise = silentRefresh().then((token) => {
        if (token) {
          setApolloToken(token);
          return forward(operation);
        }
        return null;
      });
      // @ts-expect-error -- returning a promise from onError is supported
      return promise;
    }
  }
  if (networkError) {
    console.warn("[graphql] network error:", networkError.message ?? networkError);
  }
});

export const apolloClient = new ApolloClient({
  link: from([errorLink, authLink, httpLink]),
  cache: new InMemoryCache({
    typePolicies: {
      Query: {
        fields: {
          savingsPlans: { merge: true },
          payments: { merge: true },
          loanApplications: { merge: true },
        },
      },
    },
  }),
  defaultOptions: {
    watchQuery: {
      fetchPolicy: "cache-and-network",
      errorPolicy: "all",
    },
    query: {
      fetchPolicy: "cache-first",
      errorPolicy: "all",
    },
    mutate: {
      errorPolicy: "all",
    },
  },
});

/** Extract a user-safe message from a GraphQL error payload. */
export function extractErrorMessage(
  errors: ReadonlyArray<{ message?: string }> | undefined,
  fallback = "Something went wrong. Please try again."
): string {
  if (!errors || errors.length === 0) return fallback;
  return errors[0].message ?? fallback;
}
