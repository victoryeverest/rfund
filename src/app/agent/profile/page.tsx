"use client";

import { useQuery } from "@apollo/client";
import {
  PageHeader, LoadingState, ErrorState, SectionCard, StatusBadge, StatCard,
} from "@/components/rfund/primitives";
import { AGENT_DASHBOARD_QUERY } from "@/graphql/operations";
import { formatNaira } from "@/lib/money";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Agent profile" };

export default function AgentProfilePage() {
  const { data, loading, error, refetch } = useQuery(AGENT_DASHBOARD_QUERY);

  if (loading && !data) return <LoadingState />;
  if (error)
    return <ErrorState title="Agent profile required" message="This area is for registered RFUND agents." onRetry={() => refetch()} />;

  const d = data?.agentDashboard;
  const agent = d?.agent;

  return (
    <div>
      <PageHeader title="Agent profile" description="Your registration and operating status." />
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Agent code" value={agent?.agentCode ?? "—"} tone="dark" />
        <StatCard label="Territory" value={agent?.territoryCode ?? "—"} hint={agent?.territoryState} />
        <StatCard label="Float balance" value={formatNaira(d?.availableFloat ?? "0", { decimals: false })} tone="gold" />
      </div>
      <div className="mt-6">
        <SectionCard title="Registration">
          <dl className="grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Business name</dt>
              <dd className="mt-1 text-sm font-semibold text-rfund-900">{agent?.businessName || "—"}</dd>
            </div>
            <div>
              <dt className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Status</dt>
              <dd className="mt-1"><StatusBadge status={agent?.status ?? "ACTIVE"} /></dd>
            </div>
            <div>
              <dt className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Pending settlements</dt>
              <dd className="mt-1 text-sm font-semibold text-rfund-900">{agent?.pendingSettlements ?? 0}</dd>
            </div>
            <div>
              <dt className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Operating limits</dt>
              <dd className="mt-1 text-sm text-muted-foreground">
                Enforced server-side per transaction, per day and per month. Contact your supervisor
                for changes.
              </dd>
            </div>
          </dl>
        </SectionCard>
      </div>
    </div>
  );
}
