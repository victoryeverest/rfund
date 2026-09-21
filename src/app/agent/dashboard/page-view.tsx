"use client";

import { useQuery } from "@apollo/client/react";
import {
  PageHeader, StatCard, SectionCard, LoadingState, ErrorState, EmptyState,
  TransactionItem, StatusBadge,
} from "@/components/rfund/primitives";
import { AGENT_DASHBOARD_QUERY } from "@/graphql/operations";
import { formatNaira, formatDateTime, titleize } from "@/lib/money";
import { HandCoins, Users, Receipt, Wallet } from "lucide-react";

export default function AgentDashboardPage() {
  const { data, loading, error, refetch } = useQuery(AGENT_DASHBOARD_QUERY, {
    fetchPolicy: "cache-and-network",
  });

  if (loading && !data) return <LoadingState label="Loading agent dashboard…" />;
  if (error) {
    return (
      <ErrorState
        title="Agent profile required"
        message="This area is for registered RFUND agents. If you believe this is a mistake, contact your supervisor."
        onRetry={() => refetch()}
      />
    );
  }

  const d = data?.agentDashboard;
  const txns = data?.agentTransactions?.items ?? [];

  return (
    <div>
      <PageHeader
        title={`Agent ${d?.agent?.agentCode ?? ""}`}
        description={`${d?.agent?.territoryState ?? ""} — ${d?.agent?.status ?? ""}`}
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Collections today" value={formatNaira(d?.todayCollections ?? "0", { decimals: false })} icon={<HandCoins className="h-5 w-5" />} tone="dark" />
        <StatCard label="Transactions today" value={String(d?.todayTransactions ?? 0)} icon={<Receipt className="h-5 w-5" />} />
        <StatCard label="Available float" value={formatNaira(d?.availableFloat ?? "0", { decimals: false })} icon={<Wallet className="h-5 w-5" />} tone="gold" />
        <StatCard label="Pending settlements" value={String(d?.agent?.pendingSettlements ?? 0)} icon={<Users className="h-5 w-5" />} />
      </div>

      <div className="mt-6">
        <SectionCard title="Recent transactions">
          {txns.length === 0 ? (
            <EmptyState
              title="No transactions yet."
              description="Use Collections to record a customer's cash savings."
            />
          ) : (
            <div className="space-y-3">
              {txns.map((t: any) => (
                <TransactionItem
                  key={t.id}
                  reference={t.reference}
                  title={`${titleize(t.txnType)} — ${t.customerName}`}
                  amount={formatNaira(t.amount, { decimals: false })}
                  status={t.status}
                  date={formatDateTime(t.performedAt)}
                  negative={t.txnType === "CUSTOMER_PAYOUT"}
                />
              ))}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
