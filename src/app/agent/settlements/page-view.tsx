"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  PageHeader, StatCard, SectionCard, LoadingState, ErrorState, EmptyState, StatusBadge,
} from "@/components/rfund/primitives";
import { AGENT_DASHBOARD_QUERY, AGENT_SETTLEMENTS_QUERY, REQUEST_AGENT_SETTLEMENT_MUTATION } from "@/graphql/operations";
import { extractErrorMessage } from "@/lib/graphql";
import { formatNaira, formatDateTime } from "@/lib/money";
import { AlertCircle, Wallet } from "lucide-react";

export default function AgentSettlementsPage() {
  const dashboard = useQuery(AGENT_DASHBOARD_QUERY, { fetchPolicy: "cache-and-network" });
  const settlementsQuery = useQuery(AGENT_SETTLEMENTS_QUERY);
  const [notice, setNotice] = useState<string | null>(null);
  const [opError, setOpError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [requestSettlement] = useMutation(REQUEST_AGENT_SETTLEMENT_MUTATION);

  const float = dashboard.data?.agentDashboard?.availableFloat ?? "0";
  const settlements = settlementsQuery.data?.agentSettlements ?? [];

  const request = async () => {
    setBusy(true);
    setOpError(null);
    setNotice(null);
    try {
      const result = await requestSettlement({ variables: { amount: null } });
      if (result.errors?.length) {
        setOpError(extractErrorMessage(result.errors));
        return;
      }
      const s = result.data?.requestAgentSettlement;
      setNotice(`Settlement ${s.reference} requested for ${formatNaira(s.amount, { decimals: false })}. Finance review follows.`);
      await settlementsQuery.refetch();
    } catch {
      setOpError("RFUND is not reachable right now.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Settlements"
        description="Hand collected cash over to RFUND. Requests are reviewed and approved by finance before confirmation."
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

      <div className="grid gap-4 sm:grid-cols-2">
        <StatCard label="Collected, awaiting settlement" value={formatNaira(float, { decimals: false })} tone="gold" icon={<Wallet className="h-5 w-5" />} />
        <div className="flex items-center">
          <Button
            onClick={request}
            disabled={busy || Number(float) <= 0}
            className="min-h-12 w-full bg-rfund-700 text-base font-bold text-white hover:bg-rfund-800"
          >
            {busy ? "Requesting…" : "Request settlement of full float"}
          </Button>
        </div>
      </div>

      <div className="mt-6">
        <SectionCard title="Settlement history">
          {settlementsQuery.loading && !settlementsQuery.data ? (
            <LoadingState />
          ) : settlementsQuery.error ? (
            <ErrorState message="We could not load settlements." onRetry={() => settlementsQuery.refetch()} />
          ) : settlements.length === 0 ? (
            <EmptyState title="No settlements yet." description="When you hand over collected cash, records appear here." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-sm">
                <thead>
                  <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-4 font-semibold">Reference</th>
                    <th className="py-2 pr-4 font-semibold">Amount</th>
                    <th className="py-2 pr-4 font-semibold">Status</th>
                    <th className="py-2 pr-4 font-semibold">Requested</th>
                    <th className="py-2 font-semibold">Settled</th>
                  </tr>
                </thead>
                <tbody>
                  {settlements.map((s: any) => (
                    <tr key={s.id} className="border-b border-rfund-line/60 last:border-0">
                      <td className="py-3 pr-4 font-mono text-xs">{s.reference}</td>
                      <td className="py-2 pr-4 font-bold">{formatNaira(s.amount, { decimals: false })}</td>
                      <td className="py-2 pr-4"><StatusBadge status={s.status} /></td>
                      <td className="py-2 pr-4 text-muted-foreground">{s.requestedAt ? formatDateTime(s.requestedAt) : "—"}</td>
                      <td className="py-2 text-muted-foreground">{s.settledAt ? formatDateTime(s.settledAt) : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
