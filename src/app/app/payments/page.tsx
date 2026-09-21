"use client";

import { useState } from "react";
import { useMutation } from "@apollo/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { PageHeader, SectionCard } from "@/components/rfund/primitives";
import { MAKE_PAYMENT_MUTATION, VERIFY_PAYMENT_MUTATION } from "@/graphql/operations";
import { extractErrorMessage } from "@/lib/graphql";
import { AlertCircle, CreditCard } from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Payments" };

export default function PaymentsPage() {
  const [amount, setAmount] = useState("2000");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [makePayment] = useMutation(MAKE_PAYMENT_MUTATION);
  const [verifyPayment] = useMutation(VERIFY_PAYMENT_MUTATION);

  const fund = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      setNotice("We're processing this transaction…");
      const result = await makePayment({
        variables: {
          input: {
            purpose: "ACCOUNT_FUNDING",
            amount,
            idempotencyKey: `web-fund-${Date.now()}`,
          },
        },
      });
      if (result.errors?.length) {
        setError(extractErrorMessage(result.errors));
        setNotice(null);
        return;
      }
      const paymentId = result.data?.makePayment?.payment?.id;
      const verified = await verifyPayment({ variables: { paymentId } });
      if (verified.errors?.length) {
        setError(extractErrorMessage(verified.errors));
        setNotice(null);
        return;
      }
      const v = verified.data?.verifyPayment;
      if (v?.status === "SUCCESS") {
        setNotice(`Payment received. Reference ${v.reference}. Check Transactions for the full record.`);
      } else {
        setNotice(`Still processing. Reference ${v?.reference ?? ""} — check Transactions shortly.`);
      }
    } catch {
      setError("RFUND is not reachable right now. Your money has not moved.");
      setNotice(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Payments"
        description="Fund your savings account. Payments are verified by the server before anything is recorded."
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard title="Fund your account">
          <form onSubmit={fund} className="space-y-4">
            {error ? (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" aria-hidden />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}
            {notice ? (
              <Alert className="border-rfund-gold/50 bg-rfund-gold/10">
                <AlertDescription className="font-semibold text-rfund-900">{notice}</AlertDescription>
              </Alert>
            ) : null}
            <div className="grid gap-1.5">
              <Label htmlFor="fund-amount">Amount (₦)</Label>
              <Input
                id="fund-amount"
                type="number"
                min={100}
                step={100}
                required
                className="min-h-12 text-base"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              {[1000, 2000, 5000, 10000].map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setAmount(String(v))}
                  className="min-h-10 rounded-full border border-rfund-line bg-rfund-soft px-4 text-sm font-bold text-rfund-800 hover:border-rfund-400"
                >
                  ₦{v.toLocaleString()}
                </button>
              ))}
            </div>
            <Button
              type="submit"
              disabled={busy || Number(amount) < 100}
              className="min-h-12 w-full bg-rfund-700 text-base font-bold text-white hover:bg-rfund-800"
            >
              <CreditCard className="mr-2 h-4 w-4" aria-hidden />
              {busy ? "Processing…" : "Pay now"}
            </Button>
          </form>
        </SectionCard>

        <SectionCard title="How RFUND payments work">
          <ul className="space-y-3 text-sm leading-relaxed text-muted-foreground">
            <li><strong className="text-rfund-900">Server-verified.</strong> A payment only shows as successful after the payment provider confirms it — never because a browser page said so.</li>
            <li><strong className="text-rfund-900">Exactly once.</strong> Every payment carries a unique key; network retries and duplicate provider notifications can never double-charge or double-credit.</li>
            <li><strong className="text-rfund-900">Receipted.</strong> Every completed payment gets a reference like RF-PAY-20260921-000001.</li>
            <li><strong className="text-rfund-900">Agent option.</strong> Prefer cash? Visit any RFUND agent — they record the contribution and you get an SMS receipt.</li>
          </ul>
        </SectionCard>
      </div>
    </div>
  );
}
