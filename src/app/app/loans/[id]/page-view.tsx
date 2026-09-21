"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  PageHeader, LoadingState, ErrorState, StatusBadge, SectionCard, StatCard,
} from "@/components/rfund/primitives";
import { LOAN_QUERY, MAKE_PAYMENT_MUTATION, VERIFY_PAYMENT_MUTATION } from "@/graphql/operations";
import { formatNaira, formatDate, titleize } from "@/lib/money";
import { extractErrorMessage } from "@/lib/graphql";
import { CreditCard, AlertCircle } from "lucide-react";

export default function LoanDetailPage() {
  const params = useParams<{ id: string }>();
  const { data, loading, error, refetch } = useQuery(LOAN_QUERY, {
    variables: { id: params.id },
    fetchPolicy: "cache-and-network",
  });
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [payError, setPayError] = useState<string | null>(null);
  const [makePayment] = useMutation(MAKE_PAYMENT_MUTATION);
  const [verifyPayment] = useMutation(VERIFY_PAYMENT_MUTATION);

  if (loading && !data) return <LoadingState label="Loading loan…" />;
  if (error || !data?.loan)
    return <ErrorState message="We could not load this loan." onRetry={() => refetch()} />;

  const loan = data.loan;
  const schedule = data.repaymentSchedule?.items ?? [];
  const nextDue = schedule.find(
    (s: any) => s.status !== "PAID" && s.status !== "WAIVED" && s.status !== "RESTRUCTURED"
  );
  const nextAmount = nextDue ? (Number(nextDue.totalDue) - Number(nextDue.amountPaid)).toFixed(2) : "0";

  const repay = async () => {
    setBusy(true);
    setPayError(null);
    setNotice(null);
    try {
      setNotice("We're processing this transaction…");
      const result = await makePayment({
        variables: {
          input: {
            purpose: "LOAN_REPAYMENT",
            amount: nextAmount,
            targetLoanId: loan.id,
            idempotencyKey: `web-repay-${loan.id}-${Date.now()}`,
          },
        },
      });
      if (result.errors?.length) {
        setPayError(extractErrorMessage(result.errors));
        setNotice(null);
        return;
      }
      const paymentId = result.data?.makePayment?.payment?.id;
      const verified = await verifyPayment({ variables: { paymentId } });
      if (verified.errors?.length) {
        setPayError(extractErrorMessage(verified.errors));
        setNotice(null);
        return;
      }
      const v = verified.data?.verifyPayment;
      if (v?.status === "SUCCESS") {
        setNotice(`Repayment received. Reference ${v.reference}. Thank you!`);
        await refetch();
      } else {
        setNotice(`Still processing. Reference ${v?.reference ?? ""}.`);
      }
    } catch {
      setPayError("RFUND is not reachable right now.");
      setNotice(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title={`Loan ${loan.reference}`}
        description={`${loan.productName} · ${formatNaira(loan.principal, { decimals: false })} principal · ${loan.interestRate}% · ${loan.termMonths} months`}
        action={
          nextDue ? (
            <Button
              onClick={repay}
              disabled={busy}
              className="min-h-11 bg-rfund-700 font-bold text-white hover:bg-rfund-800"
            >
              <CreditCard className="mr-1.5 h-4 w-4" aria-hidden />
              {busy ? "Processing…" : `Repay ${formatNaira(nextAmount, { decimals: false })}`}
            </Button>
          ) : undefined
        }
      />

      {payError ? (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="h-4 w-4" aria-hidden />
          <AlertDescription>{payError}</AlertDescription>
        </Alert>
      ) : null}
      {notice ? (
        <Alert className="mb-4 border-rfund-gold/50 bg-rfund-gold/10">
          <AlertDescription className="font-semibold text-rfund-900">{notice}</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Outstanding balance" value={formatNaira(loan.totalOutstanding, { decimals: false })} tone="dark" />
        <StatCard
          label="Next repayment"
          value={nextDue ? formatNaira(nextAmount, { decimals: false }) : "—"}
          hint={nextDue ? `Due ${formatDate(nextDue.dueDate)}` : "All installments settled"}
          tone="gold"
        />
        <StatCard label="Status" value={titleize(loan.status)} />
      </div>

      <div className="mt-6">
        <SectionCard title="Repayment schedule">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-4 font-semibold">#</th>
                  <th className="py-2 pr-4 font-semibold">Due date</th>
                  <th className="py-2 pr-4 font-semibold">Principal</th>
                  <th className="py-2 pr-4 font-semibold">Interest</th>
                  <th className="py-2 pr-4 font-semibold">Total</th>
                  <th className="py-2 pr-4 font-semibold">Paid</th>
                  <th className="py-2 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody>
                {schedule.map((item: any) => (
                  <tr key={item.sequence} className="border-b border-rfund-line/60 last:border-0">
                    <td className="py-3 pr-4 font-semibold text-rfund-900">{item.sequence}</td>
                    <td className="py-2 pr-4">{formatDate(item.dueDate)}</td>
                    <td className="py-2 pr-4">{formatNaira(item.principalDue, { decimals: false })}</td>
                    <td className="py-2 pr-4">{formatNaira(item.interestDue, { decimals: false })}</td>
                    <td className="py-2 pr-4 font-bold">{formatNaira(item.totalDue, { decimals: false })}</td>
                    <td className="py-2 pr-4">{formatNaira(item.amountPaid, { decimals: false })}</td>
                    <td className="py-2"><StatusBadge status={item.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Repayments are applied in a fixed order — penalties first, then fees, interest, and
            principal — so there is never any guesswork about where your money went.
          </p>
        </SectionCard>
      </div>
    </div>
  );
}
