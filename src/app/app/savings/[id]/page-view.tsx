"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  PageHeader, LoadingState, ErrorState, StatusBadge, SectionCard, StatCard,
} from "@/components/rfund/primitives";
import {
  SAVINGS_PLAN_QUERY, MAKE_PAYMENT_MUTATION, VERIFY_PAYMENT_MUTATION, CANCEL_SAVINGS_PLAN_MUTATION,
} from "@/graphql/operations";
import { formatNaira, formatDate, formatDateTime, titleize } from "@/lib/money";
import { extractErrorMessage } from "@/lib/graphql";
import { AlertCircle, CreditCard, Ban } from "lucide-react";

export default function SavingsPlanDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const { data, loading, error, refetch } = useQuery(SAVINGS_PLAN_QUERY, {
    variables: { id: params.id },
    fetchPolicy: "cache-and-network",
  });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error_, setError] = useState<string | null>(null);
  const [makePayment] = useMutation(MAKE_PAYMENT_MUTATION);
  const [verifyPayment] = useMutation(VERIFY_PAYMENT_MUTATION);
  const [cancelPlan] = useMutation(CANCEL_SAVINGS_PLAN_MUTATION);

  if (loading && !data) return <LoadingState label="Loading plan…" />;
  if (error || !data?.savingsPlan)
    return <ErrorState message="We could not load this savings plan." onRetry={() => refetch()} />;

  const plan = data.savingsPlan;
  const schedule = data.savingsSchedule?.items ?? [];
  const paid = plan.contributionsPaid;
  const total = plan.contributionCount;

  const contribute = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      // §78: never claim success before the backend confirms.
      setNotice("We're processing this transaction…");
      const result = await makePayment({
        variables: {
          input: {
            purpose: "SAVINGS_CONTRIBUTION",
            amount: plan.amount,
            targetPlanId: plan.id,
            idempotencyKey: `web-contrib-${plan.id}-${Date.now()}`,
          },
        },
      });
      if (result.errors?.length) {
        setError(extractErrorMessage(result.errors));
        setNotice(null);
        return;
      }
      const paymentId = result.data?.makePayment?.payment?.id;
      if (!paymentId) {
        setError("Payment could not be initialized. Please try again.");
        setNotice(null);
        return;
      }
      setNotice("We're processing this transaction…");
      const verified = await verifyPayment({ variables: { paymentId } });
      if (verified.errors?.length) {
        setError(extractErrorMessage(verified.errors));
        setNotice(null);
        return;
      }
      const status = verified.data?.verifyPayment?.status;
      if (status === "SUCCESS") {
        setNotice(
          `Payment received. Reference ${verified.data.verifyPayment.reference}. Your balance has been updated.`
        );
        await refetch();
      } else {
        setNotice(
          `Payment is still processing. Reference ${verified.data?.verifyPayment?.reference ?? ""} — check transactions shortly.`
        );
      }
    } catch {
      setError("RFUND is not reachable right now. Your money has not moved.");
      setNotice(null);
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (!confirm("Cancel this savings plan? Future contributions will be cancelled. This cannot be undone.")) {
      return;
    }
    setBusy(true);
    try {
      const result = await cancelPlan({ variables: { planId: plan.id } });
      if (result.errors?.length) {
        setError(extractErrorMessage(result.errors));
      } else {
        router.push("/app/savings");
        return;
      }
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title={plan.productName}
        description={`${titleize(plan.frequency)} contributions of ${formatNaira(plan.amount)} · ${formatDate(plan.startDate)} to ${formatDate(plan.endDate)}`}
        action={
          plan.status === "ACTIVE" ? (
            <div className="flex gap-2">
              <Button
                onClick={contribute}
                disabled={busy}
                className="min-h-11 bg-rfund-700 font-bold text-white hover:bg-rfund-800"
              >
                <CreditCard className="mr-1.5 h-4 w-4" aria-hidden />
                {busy ? "Processing…" : `Contribute ${formatNaira(plan.amount, { decimals: false })}`}
              </Button>
              <Button
                onClick={cancel}
                disabled={busy}
                variant="outline"
                className="min-h-11 border-destructive/40 font-bold text-destructive hover:bg-destructive/10"
              >
                <Ban className="mr-1.5 h-4 w-4" aria-hidden /> Cancel plan
              </Button>
            </div>
          ) : undefined
        }
      />

      {error_ ? (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="h-4 w-4" aria-hidden />
          <AlertDescription>{error_}</AlertDescription>
        </Alert>
      ) : null}
      {notice ? (
        <Alert className="mb-4 border-rfund-gold/50 bg-rfund-gold/10">
          <AlertDescription className="font-semibold text-rfund-900">{notice}</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Total contributed" value={formatNaira(plan.totalContributed, { decimals: false })} tone="dark" />
        <StatCard label="Contributions" value={`${paid} of ${total}`} hint={`${total - paid} remaining`} tone="gold" />
        <StatCard
          label="Next due"
          value={plan.nextDue ? formatDate(plan.nextDue.dueDate) : "—"}
          hint={plan.nextDue ? formatNaira(plan.nextDue.amount, { decimals: false }) : undefined}
        />
      </div>

      <div className="mt-6">
        <SectionCard title="Payment schedule" description="">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-4 font-semibold">Due date</th>
                  <th className="py-2 pr-4 font-semibold">Amount</th>
                  <th className="py-2 pr-4 font-semibold">Status</th>
                  <th className="py-2 pr-4 font-semibold">Paid on</th>
                  <th className="py-2 font-semibold">Receipt</th>
                </tr>
              </thead>
              <tbody>
                {schedule.map((item: any) => (
                  <tr key={item.id} className="border-b border-rfund-line/60 last:border-0">
                    <td className="py-3 pr-4 font-semibold text-rfund-900">{formatDate(item.dueDate)}</td>
                    <td className="py-2 pr-4">{formatNaira(item.amount, { decimals: false })}</td>
                    <td className="py-2 pr-4"><StatusBadge status={item.status} /></td>
                    <td className="py-2 pr-4 text-muted-foreground">{item.paidAt ? formatDateTime(item.paidAt) : "—"}</td>
                    <td className="py-2 font-mono text-xs text-muted-foreground">{item.paymentReference || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Schedule dates are generated on the real calendar — including month-end clamping and
            leap years.
          </p>
        </SectionCard>
      </div>
    </div>
  );
}
