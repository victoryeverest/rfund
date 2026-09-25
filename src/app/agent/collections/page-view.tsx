"use client";

import { useQuery, useMutation } from "@apollo/client/react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { PageHeader, SectionCard, LoadingState, ErrorState, EmptyState, TransactionItem } from "@/components/rfund/primitives";
import { AGENT_CUSTOMERS_QUERY, AGENT_CUSTOMER_PLANS_QUERY, AGENT_DASHBOARD_QUERY, AGENT_CASH_COLLECTION_MUTATION } from "@/graphql/operations";
import { extractErrorMessage } from "@/lib/graphql";
import { formatNaira, formatDateTime } from "@/lib/money";
import { AlertCircle, HandCoins } from "lucide-react";

export default function AgentCollectionsPage() {
  const customersQuery = useQuery(AGENT_CUSTOMERS_QUERY, { variables: { first: 100 } });
  const dashboardQuery = useQuery(AGENT_DASHBOARD_QUERY, { fetchPolicy: "cache-and-network" });
  const [customerId, setCustomerId] = useState("");
  const [planId, setPlanId] = useState("");
  const [amount, setAmount] = useState("1000");
  const [notice, setNotice] = useState<string | null>(null);
  const [opError, setOpError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [collect] = useMutation(AGENT_CASH_COLLECTION_MUTATION);

  const customers = customersQuery.data?.agentCustomers?.items ?? [];
  const selected = customers.find((c: any) => c.id === customerId);
  const plansQuery = useQuery(AGENT_CUSTOMER_PLANS_QUERY, {
    variables: { customerId },
    skip: !customerId,
  });
  const plans = plansQuery.data?.agentCustomerPlans ?? [];

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setOpError(null);
    setNotice(null);
    try {
      setNotice("Recording the collection…");
      const result = await collect({
        variables: {
          input: {
            customerId,
            amount,
            purpose: "SAVINGS_CONTRIBUTION",
            targetPlanId: planId || undefined,
            idempotencyKey: `agent-coll-${customerId}-${Date.now()}`,
          },
        },
      });
      if (result.errors?.length) {
        setOpError(extractErrorMessage(result.errors));
        setNotice(null);
        return;
      }
      const txn = result.data?.agentCashCollection;
      setNotice(`Recorded. Receipt ${txn.reference} — SMS confirmation sent to ${selected?.phone ?? "the customer"}.`);
      await dashboardQuery.refetch();
    } catch {
      setOpError("RFUND is not reachable. The collection was NOT recorded.");
      setNotice(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Cash collections"
        description="Record cash savings you collect from customers. Each entry posts to the ledger and issues a receipt."
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard title="New collection">
          {customersQuery.loading && !customersQuery.data ? (
            <LoadingState />
          ) : customersQuery.error ? (
            <ErrorState message="We could not load customers." onRetry={() => customersQuery.refetch()} />
          ) : (
            <form onSubmit={submit} className="space-y-4">
              {opError ? (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" aria-hidden />
                  <AlertDescription>{opError}</AlertDescription>
                </Alert>
              ) : null}
              {notice ? (
                <Alert className="border-rfund-500/40 bg-rfund-100">
                  <AlertDescription className="font-semibold text-rfund-900">{notice}</AlertDescription>
                </Alert>
              ) : null}
              <div className="grid gap-1.5">
                <Label htmlFor="coll-customer">Customer</Label>
                <select
                  id="coll-customer"
                  required
                  className="min-h-12 rounded-lg border border-rfund-line bg-white px-3 text-base"
                  value={customerId}
                  onChange={(e) => {
                    setCustomerId(e.target.value);
                    setPlanId("");
                  }}
                >
                  <option value="">Choose customer…</option>
                  {customers.map((c: any) => (
                    <option key={c.id} value={c.id}>
                      {c.fullName} — {c.phone}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="coll-plan">Savings plan</Label>
                <select
                  id="coll-plan"
                  className="min-h-12 rounded-lg border border-rfund-line bg-white px-3 text-base"
                  value={planId}
                  onChange={(e) => setPlanId(e.target.value)}
                  disabled={!customerId}
                >
                  <option value="">
                    {customerId
                      ? plans.length === 1
                        ? `Auto — ${plans[0].productName} (${plans[0].reference})`
                        : "Auto — customer's active plan"
                      : "Choose a customer first"}
                  </option>
                  {plans.map((p: any) => (
                    <option key={p.id} value={p.id}>
                      {p.productName} · {p.frequency} · {formatNaira(p.amount, { decimals: false })} ({p.reference})
                    </option>
                  ))}
                </select>
                <p className="text-xs text-muted-foreground">
                  {plans.length > 1
                    ? "This customer has several active plans — pick one so the money lands in the right plan."
                    : "Leave on Auto to credit the customer's active savings plan."}
                </p>
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="coll-amount">Amount received (₦)</Label>
                <Input
                  id="coll-amount"
                  type="number"
                  min={100}
                  required
                  className="min-h-12 text-base"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
              </div>
              <Button
                type="submit"
                disabled={busy || !customerId || Number(amount) < 100}
                className="min-h-12 w-full bg-rfund-700 text-base font-bold text-white hover:bg-rfund-800"
              >
                <HandCoins className="mr-2 h-4 w-4" aria-hidden />
                {busy ? "Recording…" : "Record collection"}
              </Button>
            </form>
          )}
        </SectionCard>

        <SectionCard title="Today's activity">
          {dashboardQuery.loading && !dashboardQuery.data ? (
            <LoadingState />
          ) : (dashboardQuery.data?.agentTransactions?.items ?? []).filter((t: any) => t.txnType === "CASH_COLLECTION").length === 0 ? (
            <EmptyState title="No collections recorded yet today." description="Collections you record will appear here." />
          ) : (
            <div className="space-y-3">
              {(dashboardQuery.data?.agentTransactions?.items ?? [])
                .filter((t: any) => t.txnType === "CASH_COLLECTION")
                .map((t: any) => (
                  <TransactionItem
                    key={t.id}
                    reference={t.reference}
                    title={`Collection — ${t.customerName}`}
                    amount={formatNaira(t.amount, { decimals: false })}
                    status={t.status}
                    date={formatDateTime(t.performedAt)}
                  />
                ))}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
