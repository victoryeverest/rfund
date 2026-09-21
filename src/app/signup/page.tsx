"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Checkbox } from "@/components/ui/checkbox";
import { REGISTER_MUTATION } from "@/graphql/operations";
import { useAuth } from "@/lib/auth";
import { extractErrorMessage } from "@/lib/graphql";
import { AlertCircle, UserPlus } from "lucide-react";

export default function SignupPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [form, setForm] = useState({ firstName: "", lastName: "", phone: "", password: "" });
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [register] = useMutation(REGISTER_MUTATION);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!agreed) {
      setError("Please accept the terms to continue.");
      return;
    }
    setError(null);
    setBusy(true);
    try {
      const result = await register({ variables: { input: form } });
      if (result.errors?.length) {
        setError(extractErrorMessage(result.errors));
        return;
      }
      const pair = result.data?.registerCustomer;
      if (!pair?.accessToken) {
        setError("Registration did not complete. Please try again.");
        return;
      }
      await signIn(pair.accessToken, pair.refreshToken, pair.user);
      router.replace("/app/dashboard");
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
          <h1 className="text-2xl font-extrabold text-rfund-900">Open your RFUND account</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            All you need to start is your phone number. Everything else comes later, when you
            need it.
          </p>

          {error ? (
            <Alert variant="destructive" className="mt-4">
              <AlertCircle className="h-4 w-4" aria-hidden />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}

          <form onSubmit={submit} className="mt-5 space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="signup-first">First name</Label>
                <Input
                  id="signup-first"
                  required
                  autoComplete="given-name"
                  className="min-h-12 text-base"
                  value={form.firstName}
                  onChange={(e) => setForm({ ...form, firstName: e.target.value })}
                />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="signup-last">Last name</Label>
                <Input
                  id="signup-last"
                  required
                  autoComplete="family-name"
                  className="min-h-12 text-base"
                  value={form.lastName}
                  onChange={(e) => setForm({ ...form, lastName: e.target.value })}
                />
              </div>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="signup-phone">Phone number</Label>
              <Input
                id="signup-phone"
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                required
                placeholder="0803 123 4567"
                className="min-h-12 text-base"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                This becomes your login. Message rates may apply for SMS alerts.
              </p>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="signup-password">Password</Label>
              <Input
                id="signup-password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                className="min-h-12 text-base"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
              <p className="text-xs text-muted-foreground">
                At least 8 characters, not all numbers.
              </p>
            </div>
            <label className="flex items-start gap-3 text-sm text-muted-foreground">
              <Checkbox
                checked={agreed}
                onCheckedChange={(v) => setAgreed(v === true)}
                className="mt-0.5"
                aria-label="Accept terms"
              />
              <span>
                I understand RFUND is a technology platform, that regulated financial services
                are provided with licensed partners, and I accept the terms of service and
                privacy policy.
              </span>
            </label>
            <Button
              type="submit"
              disabled={busy}
              className="min-h-12 w-full bg-rfund-gold text-base font-extrabold text-rfund-900 hover:bg-rfund-gold-dark"
            >
              <UserPlus className="mr-2 h-4 w-4" aria-hidden />
              {busy ? "Creating account…" : "Create my account"}
            </Button>
          </form>

          <p className="mt-5 text-center text-sm text-muted-foreground">
            Already registered?{" "}
            <Link href="/login" className="font-bold text-rfund-700 underline">
              Sign in
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
