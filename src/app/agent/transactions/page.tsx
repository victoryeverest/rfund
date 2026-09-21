"use client";

import { useQuery } from "@apollo/client";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, TransactionItem,
} from "@/components/rfund/primitives";
import { AGENT_DASHBOARD_QUERY } from "@/graphql/operations";
import { formatNaira, formatDateTime } from "@/lib/money";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Agent transactions" };

export default function AgentTransactionsPage() {
  const { data, loading, error, refetch } = useQuery(AGENT_DASHBOARD_QUERY, {
    fetchPolicy: "cache-and-network",
  });

  const txns = data?.agentTransactions?.items ?? [];

  return (
    <div>
      <PageHeader title="Transactions" description="Your full agent transaction history." />
      {loading && !data ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message="We could not load your transactions." onRetry={() => refetch()} />
      ) : txns.length === 0 ? (
        <EmptyState title="No transactions yet." description="Collections and payouts you record will appear here." />
      ) : (
        <div className="space-y-3">
          {txns.map((t: any) => (
            <TransactionItem
              key={t.id}
              reference={t.reference}
              title={`${t.txnType === "CASH_COLLECTION" ? "Collection" : "Payout"} — ${t.customerName}`}
              amount={formatNaira(t.amount, { decimals: false })}
              status={t.status}
              date={formatDateTime(t.performedAt)}
              negative={t.txnType === "CUSTOMER_PAYOUT"}
            />
          ))}
        </div>
      )}
    </div>
  );
}
