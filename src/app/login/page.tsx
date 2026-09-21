"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useMutation } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { LOGIN_MUTATION } from "@/graphql/operations";
import { useAuth } from "@/lib/auth";
import { extractErrorMessage } from "@/lib/graphql";
import { LogIn, AlertCircle } from "lucide-react";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { signIn } = useAuth();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [login] = useMutation(LOGIN_MUTATION);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = await login({ variables: { input: { phone, password, deviceLabel: "web" } } });
      if (result.errors?.length) {
        setError(extractErrorMessage(result.errors));
        return;
      }
      const pair = result.data?.login;
      if (!pair?.accessToken) {
        setError("Sign-in did not complete. Please try again.");
        return;
      }
      await signIn(pair.accessToken, pair.refreshToken, pair.user);
      const next = params.get("next");
      if (next && next.startsWith("/")) {
        router.replace(next);
      } else {
        router.replace("/app/dashboard");
      }
    } catch {
      setError("RFUND is not reachable right now. Please check your connection.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-rfund-soft/60 px-4 py-10">
      <Link href="/" className="mb-6 flex items-center gap-2 font-extrabold text-rfund-900" aria-label="RFUND home">
        <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-rfund-700 text-white">R</span>
        <span className="text-xl">RFUND</span>
      </Link>
      <Card className="w-full max-w-md border border-rfund-line shadow-lg">
        <CardContent className="p-6 sm:p-8">
          <h1 className="text-2xl font-extrabold text-rfund-900">Welcome back</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Sign in with the phone number you registered with.
          </p>

          {error ? (
            <Alert variant="destructive" className="mt-4">
              <AlertCircle className="h-4 w-4" aria-hidden />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <form onSubmit={submit} className="mt-5 space-y-4">
            <div className="grid gap-1.5">
              <Label htmlFor="login-phone">Phone number</Label>
              <Input
                id="login-phone"
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                required
                placeholder="0803 123 4567"
                className="min-h-12 text-base"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="login-password">Password</Label>
              <Input
                id="login-password"
                type="password"
                autoComplete="current-password"
                required
                className="min-h-12 text-base"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <Button
              type="submit"
              disabled={busy}
              className="min-h-12 w-full bg-rfund-700 text-base font-bold text-white hover:bg-rfund-800"
            >
              <LogIn className="mr-2 h-4 w-4" aria-hidden />
              {busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>

          <p className="mt-5 text-center text-sm text-muted-foreground">
            New to RFUND?{" "}
            <Link href="/signup" className="font-bold text-rfund-700 underline">
              Create an account
            </Link>
          </p>
        </CardContent>
      </Card>
      <p className="mt-6 max-w-md text-center text-xs text-muted-foreground">
        Protected by device-aware sessions with automatic sign-out. RFUND staff will never ask
        for your password or PIN.
      </p>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
