"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useQuery, useMutation } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  PageHeader, LoadingState, ErrorState, SectionCard, StatusBadge,
} from "@/components/rfund/primitives";
import { AGENT_CUSTOMERS_QUERY, AGENT_CUSTOMER_PLANS_QUERY, AGENT_CASH_COLLECTION_MUTATION, AGENT_PAYOUT_MUTATION } from "@/graphql/operations";
import { extractErrorMessage } from "@/lib/graphql";
import { titleize } from "@/lib/money";
import { AlertCircle, HandCoins, Banknote } from "lucide-react";

export default function AgentCustomerPage() {
  const params = useParams<{ id: string }>();
  const { data, loading, error, refetch } = useQuery(AGENT_CUSTOMERS_QUERY, {
    variables: { search: "", first: 100 },
  });
  const [amount, setAmount] = useState("1000");
  const [planId, setPlanId] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [opError, setOpError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [collect] = useMutation(AGENT_CASH_COLLECTION_MUTATION);
  const [payout] = useMutation(AGENT_PAYOUT_MUTATION);

  const customer = (data?.agentCustomers?.items ?? []).find((c: any) => c.id === params.id);
  const plansQuery = useQuery(AGENT_CUSTOMER_PLANS_QUERY, {
    variables: { customerId: params.id },
    skip: !params.id,
  });
  const plans = plansQuery.data?.agentCustomerPlans ?? [];

  if (loading && !data) return <LoadingState />;
  if (error || !customer)
    return <ErrorState message="We could not load this customer." onRetry={() => refetch()} />;

  const run = async (kind: "collect" | "payout") => {
    setBusy(true);
    setOpError(null);
    setNotice(null);
    try {
      setNotice("Recording the transaction…");
      const input = {
        customerId: customer.id,
        amount,
        targetPlanId: planId || undefined,
        idempotencyKey: `agent-${kind}-${customer.id}-${Date.now()}`,
      };
      const result =
        kind === "collect"
          ? await collect({ variables: { input: { ...input, purpose: "SAVINGS_CONTRIBUTION" } } })
          : await payout({ variables: { input } });
      if (result.errors?.length) {
        setOpError(extractErrorMessage(result.errors));
        setNotice(null);
        return;
      }
      const txn = result.data?.agentCashCollection ?? result.data?.agentCustomerPayout;
      setNotice(
        `Recorded. Receipt reference ${txn.reference}. The customer will receive an SMS confirmation.`
      );
    } catch {
      setOpError("RFUND is not reachable right now. The transaction was NOT recorded — do not hand over money.");
      setNotice(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title={customer.fullName}
        description={`${customer.phone} · ${customer.customerReference} · ${customer.state || ""} ${customer.lga ? "· " + customer.lga : ""}`}
      />

      {opError ? (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="h-4 w-4" aria-hidden />
          <AlertDescription>{opError}</AlertDescription>
        </Alert>
      ) : null}
      {notice ? (
        <Alert className="mb-4 border-rfund-500/40 bg-rfund-100">
          <AlertDescription className="font-semibold text-rfund-900">{notice}</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard title="Collect cash savings">
          <div className="space-y-4">
            <div className="grid gap-1.5">
              <Label htmlFor="collect-plan">Savings plan</Label>
              <select
                id="collect-plan"
                className="min-h-12 rounded-lg border border-rfund-line bg-white px-3 text-base"
                value={planId}
                onChange={(e) => setPlanId(e.target.value)}
              >
                <option value="">
                  {plans.length === 1
                    ? `Auto — ${plans[0].productName} (${plans[0].reference})`
                    : "Auto — active plan"}
                </option>
                {plans.map((p: any) => (
                  <option key={p.id} value={p.id}>
                    {p.productName} · {p.frequency} · ₦{p.amount} ({p.reference})
                  </option>
                ))}
              </select>
              {plans.length > 1 ? (
                <p className="text-xs text-muted-foreground">
                  Several active plans — pick one so the money lands in the right plan.
                </p>
              ) : null}
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="collect-amount">Amount received (₦)</Label>
              <Input
                id="collect-amount"
                type="number"
                min={100}
                required
                className="min-h-12 text-base"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
            <Button
              onClick={() => run("collect")}
              disabled={busy || Number(amount) < 100}
              className="min-h-12 w-full bg-rfund-700 text-base font-bold text-white hover:bg-rfund-800"
            >
              <HandCoins className="mr-2 h-4 w-4" aria-hidden />
              {busy ? "Recording…" : "Record collection"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Only record after physically receiving the cash. The platform posts the entry and
              sends the customer an SMS receipt.
            </p>
          </div>
        </SectionCard>

        <SectionCard title="Pay out to customer">
          <div className="space-y-4">
            <div className="grid gap-1.5">
              <Label htmlFor="payout-amount">Amount to pay (₦)</Label>
              <Input
                id="payout-amount"
                type="number"
                min={100}
                className="min-h-12 text-base"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
              />
            </div>
            <Button
              onClick={() => run("payout")}
              disabled={busy || Number(amount) < 100}
              variant="outline"
              className="min-h-12 w-full border-rfund-700 text-base font-bold text-rfund-900 hover:bg-rfund-100"
            >
              <Banknote className="mr-2 h-4 w-4" aria-hidden />
              {busy ? "Recording…" : "Record payout"}
            </Button>
            <p className="text-xs text-muted-foreground">
              Payouts draw from your float. The platform checks your limits before recording.
            </p>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
