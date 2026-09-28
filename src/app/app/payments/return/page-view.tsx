"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMutation } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { PageHeader, SectionCard, LoadingState, ErrorState } from "@/components/rfund/primitives";
import { VERIFY_PAYMENT_MUTATION } from "@/graphql/operations";
import { formatNaira } from "@/lib/money";
import { CheckCircle2, Clock, AlertCircle } from "lucide-react";

/**
 * Hosted-checkout landing page (spec §23): the provider (Paystack) redirects
 * here after checkout. The browser claim is never trusted — this page asks
 * the server to verify the payment against the provider before showing a
 * result. Replays are safe: verify is idempotent.
 */
export default function PaymentReturnView() {
  const params = useSearchParams();
  const paymentId = params.get("payment_id") || params.get("paymentId");
  const providerRef = params.get("reference") || params.get("trxref") || "";

  const [verifyPayment] = useMutation(VERIFY_PAYMENT_MUTATION);
  const [state, setState] = useState<
    | { kind: "loading" }
    | { kind: "success"; reference: string; amount?: string }
    | { kind: "pending"; reference: string }
    | { kind: "failed"; message: string; reference: string }
    | { kind: "error"; message: string }
  >({ kind: "loading" });
  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current) return;
    attempted.current = true;
    if (!paymentId) {
      // Synchronous setState in an effect is intentional here (one-shot
      // validation of the query params); the async verify path below defers.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setState({
        kind: "error",
        message: providerRef
          ? `We could not identify this payment (reference ${providerRef}). Check your transactions — nothing is lost.`
          : "This page needs a payment reference. Nothing has moved without verification.",
      });
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const result = await verifyPayment({ variables: { paymentId } });
        if (cancelled) return;
        if (result.errors?.length) {
          setState({
            kind: "failed",
            message: result.errors[0]?.message ?? "Verification failed.",
            reference: providerRef,
          });
          return;
        }
        const v = result.data?.verifyPayment;
        if (v?.status === "SUCCESS") {
          setState({ kind: "success", reference: v.reference, amount: v.amount });
        } else if (v?.status === "FAILED") {
          setState({
            kind: "failed",
            message: "The payment was not completed. No money has moved.",
            reference: v.reference,
          });
        } else {
          setState({ kind: "pending", reference: v?.reference ?? providerRef });
        }
      } catch {
        if (!cancelled) {
          setState({
            kind: "error",
            message: "RFUND could not be reached to verify this payment. Check your transactions in a moment.",
          });
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [paymentId, providerRef, verifyPayment]);

  return (
    <div>
      <PageHeader
        title="Payment status"
        description="Payments are only recorded after the server verifies them with the payment provider."
      />
      <div className="mx-auto max-w-xl">
        {state.kind === "loading" ? (
          <LoadingState label="Verifying your payment with the provider…" />
        ) : state.kind === "success" ? (
          <SectionCard title="Payment received">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="mt-0.5 h-8 w-8 shrink-0 text-green-600" aria-hidden />
              <div>
                <p className="text-lg font-extrabold text-rfund-900">
                  {state.amount ? formatNaira(state.amount) : "Your payment"} was received.
                </p>
                <p className="mt-1 font-mono text-sm text-muted-foreground">{state.reference}</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Keep this reference — quote it to support for instant tracing.
                </p>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <Button asChild className="min-h-11 bg-rfund-700 font-bold text-white hover:bg-rfund-800">
                <Link href="/app/transactions">View transactions</Link>
              </Button>
              <Button asChild variant="outline" className="min-h-11 font-bold">
                <Link href="/app/dashboard">Back to dashboard</Link>
              </Button>
            </div>
          </SectionCard>
        ) : state.kind === "pending" ? (
          <SectionCard title="Still processing">
            <div className="flex items-start gap-3">
              <Clock className="mt-0.5 h-8 w-8 shrink-0 text-amber-500" aria-hidden />
              <div>
                <p className="text-lg font-extrabold text-rfund-900">
                  Your payment is being confirmed.
                </p>
                <p className="mt-1 font-mono text-sm text-muted-foreground">{state.reference}</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  This can take a few moments. Nothing else is needed from you — the balance
                  updates automatically once the provider confirms.
                </p>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <Button asChild className="min-h-11 bg-rfund-700 font-bold text-white hover:bg-rfund-800">
                <Link href="/app/transactions">View transactions</Link>
              </Button>
              <Button asChild variant="outline" className="min-h-11 font-bold">
                <Link href="/app/dashboard">Back to dashboard</Link>
              </Button>
            </div>
          </SectionCard>
        ) : state.kind === "failed" ? (
          <SectionCard title="Payment not completed">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-8 w-8 shrink-0 text-red-500" aria-hidden />
              <div>
                <p className="text-lg font-extrabold text-rfund-900">{state.message}</p>
                {state.reference ? (
                  <p className="mt-1 font-mono text-sm text-muted-foreground">{state.reference}</p>
                ) : null}
                <p className="mt-2 text-sm text-muted-foreground">
                  You can safely try again — payments are exactly-once per reference.
                </p>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap gap-2">
              <Button asChild className="min-h-11 bg-rfund-700 font-bold text-white hover:bg-rfund-800">
                <Link href="/app/payments">Try again</Link>
              </Button>
              <Button asChild variant="outline" className="min-h-11 font-bold">
                <Link href="/app/dashboard">Back to dashboard</Link>
              </Button>
            </div>
          </SectionCard>
        ) : (
          <ErrorState message={state.message} />
        )}
      </div>
    </div>
  );
}
