"use client";

/**
 * Auth store: access token lives in memory only (XSS-safe); the refresh
 * token sits in an httpOnly cookie managed by the BFF routes. On mount we
 * silently refresh; on 401 we retry once after refreshing (§176, §177).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

export type SessionUser = {
  id: string;
  phone: string;
  firstName: string;
  lastName: string;
};

type AuthState = {
  user: SessionUser | null;
  status: "loading" | "authenticated" | "anonymous";
  signIn: (accessToken: string, refreshToken: string, user: SessionUser) => Promise<void>;
  signOut: () => Promise<void>;
  refresh: () => Promise<string | null>;
  getAccessToken: () => string | null;
};

const AuthContext = createContext<AuthState | null>(null);

// Module-level token store — survives re-renders, dies on reload (by design)
let accessTokenStore: string | null = null;

function setToken(token: string | null) {
  accessTokenStore = token;
  // Keep the Apollo link in sync without a circular import
  import("@/lib/graphql").then(({ setApolloToken }) => setApolloToken(token)).catch(() => undefined);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [status, setStatus] = useState<AuthState["status"]>("loading");

  const refresh = useCallback(async (): Promise<string | null> => {
    try {
      const res = await fetch("/api/auth/refresh", { method: "POST" });
      const body = await res.json();
      if (body.authenticated && body.accessToken) {
        setToken(body.accessToken);
        setUser(body.user ?? null);
        setStatus("authenticated");
        return body.accessToken as string;
      }
      accessTokenStore = null;
      setUser(null);
      setStatus("anonymous");
      return null;
    } catch {
      setToken(null);
      setStatus("anonymous");
      return null;
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const signIn = useCallback(
    async (accessToken: string, refreshToken: string, sessionUser: SessionUser) => {
      setToken(accessToken);
      setUser(sessionUser);
      setStatus("authenticated");
      await fetch("/api/auth/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refreshToken }),
      }).catch(() => undefined);
    },
    []
  );

  const signOut = useCallback(async () => {
    const token = accessTokenStore;
    setToken(null);
    setUser(null);
    setStatus("anonymous");
    await fetch("/api/auth/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ logout: true }),
    }).catch(() => undefined);
    if (token) {
      void fetch("/api/graphql", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ query: "mutation { logout }" }),
      }).catch(() => undefined);
    }
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      status,
      signIn,
      signOut,
      refresh,
      getAccessToken: () => accessTokenStore,
    }),
    [user, status, signIn, signOut, refresh]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
