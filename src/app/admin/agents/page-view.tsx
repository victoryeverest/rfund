"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, StatusBadge, SectionCard,
} from "@/components/rfund/primitives";
import {
  ADMIN_AGENTS_QUERY,
  ADMIN_SET_AGENT_STATUS_MUTATION,
  ADMIN_APPROVE_SETTLEMENT_MUTATION,
} from "@/graphql/operations";
import { extractErrorMessage } from "@/lib/graphql";
import { formatNaira, formatDate, formatDateTime, titleize } from "@/lib/money";
import { AlertCircle } from "lucide-react";

export default function AdminAgentsPage() {
  const { data, loading, error, refetch } = useQuery(ADMIN_AGENTS_QUERY, {
    fetchPolicy: "cache-and-network",
  });
  const [opError, setOpError] = useState<string | null>(null);
  const [setAgentStatus] = useMutation(ADMIN_SET_AGENT_STATUS_MUTATION);
  const [approveSettlement] = useMutation(ADMIN_APPROVE_SETTLEMENT_MUTATION);

  const agents = data?.adminAgents?.items ?? [];
  const settlements = data?.adminAgentSettlements ?? [];
  const pendingSettlements = settlements.filter((s: any) => s.status === "REQUESTED" || s.status === "PENDING");

  const changeStatus = async (agentId: string, status: string) => {
    const reason =
      status === "ACTIVE"
        ? "reinstated by admin"
        : window.prompt(`Reason for ${status.toLowerCase()} (recorded in the audit trail):`);
    if (reason === null) return;
    setOpError(null);
    const result = await setAgentStatus({
      variables: { agentId, status, reason: reason || undefined },
    });
    if (result.errors?.length) {
      setOpError(extractErrorMessage(result.errors));
      return;
    }
    await refetch();
  };

  const approve = async (settlementId: string) => {
    setOpError(null);
    const result = await approveSettlement({ variables: { settlementId } });
    if (result.errors?.length) {
      setOpError(extractErrorMessage(result.errors));
      return;
    }
    await refetch();
  };

  return (
    <div>
      <PageHeader
        title="Agent network"
        description="Agent registrations, float balances and settlement approvals."
      />
      {opError ? (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="h-4 w-4" aria-hidden />
          <AlertDescription>{opError}</AlertDescription>
        </Alert>
      ) : null}

      {loading && !data ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message="We could not load agents (permission required)." onRetry={() => refetch()} />
      ) : (
        <>
          <SectionCard title={`Agents (${data?.adminAgents?.pageInfo?.totalCount ?? agents.length})`}>
            {agents.length === 0 ? (
              <EmptyState title="No agents registered." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[860px] text-sm">
                  <thead>
                    <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-4 font-semibold">Code</th>
                      <th className="py-2 pr-4 font-semibold">Business</th>
                      <th className="py-2 pr-4 font-semibold">Phone</th>
                      <th className="py-2 pr-4 font-semibold">Territory</th>
                      <th className="py-2 pr-4 font-semibold">Float</th>
                      <th className="py-2 pr-4 font-semibold">Status</th>
                      <th className="py-2 pr-4 font-semibold">Since</th>
                      <th className="py-2 font-semibold">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agents.map((a: any) => (
                      <tr key={a.id} className="border-b border-rfund-line/60 last:border-0">
                        <td className="py-3 pr-4 font-mono text-xs">{a.agentCode}</td>
                        <td className="py-2 pr-4 font-semibold text-rfund-900">{a.businessName}</td>
                        <td className="py-2 pr-4">{a.phone}</td>
                        <td className="py-2 pr-4 text-muted-foreground">
                          {a.territoryCode ? `${a.territoryCode}, ${a.territoryState ?? ""}` : "—"}
                        </td>
                        <td className="py-2 pr-4 font-semibold">{formatNaira(a.floatBalance, { decimals: false })}</td>
                        <td className="py-2 pr-4"><StatusBadge status={a.status} /></td>
                        <td className="py-2 pr-4 text-muted-foreground">{formatDate(a.createdAt)}</td>
                        <td className="py-2">
                          {a.status === "ACTIVE" ? (
                            <Button
                              size="sm"
                              variant="outline"
                              className="min-h-9 border-destructive/40 font-bold text-destructive hover:bg-destructive/10"
                              onClick={() => changeStatus(a.id, "SUSPENDED")}
                            >
                              Suspend
                            </Button>
                          ) : a.status === "SUSPENDED" || a.status === "INACTIVE" ? (
                            <Button
                              size="sm"
                              variant="outline"
                              className="min-h-9 font-bold text-rfund-700 hover:bg-rfund-100"
                              onClick={() => changeStatus(a.id, "ACTIVE")}
                            >
                              Reactivate
                            </Button>
                          ) : (
                            <span className="text-xs text-muted-foreground">—</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>

          <div className="mt-6">
            <SectionCard title={`Agent settlements (${pendingSettlements.length} awaiting approval)`}>
              {settlements.length === 0 ? (
                <EmptyState title="No settlement requests yet." />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[760px] text-sm">
                    <thead>
                      <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                        <th className="py-2 pr-4 font-semibold">Reference</th>
                        <th className="py-2 pr-4 font-semibold">Agent</th>
                        <th className="py-2 pr-4 font-semibold">Amount</th>
                        <th className="py-2 pr-4 font-semibold">Status</th>
                        <th className="py-2 pr-4 font-semibold">Requested</th>
                        <th className="py-2 pr-4 font-semibold">Settled</th>
                        <th className="py-2 font-semibold">Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {settlements.map((s: any) => (
                        <tr key={s.id} className="border-b border-rfund-line/60 last:border-0">
                          <td className="py-3 pr-4 font-mono text-xs">{s.reference}</td>
                          <td className="py-2 pr-4 font-semibold text-rfund-900">{s.agentCode}</td>
                          <td className="py-2 pr-4 font-semibold">{formatNaira(s.amount, { decimals: false })}</td>
                          <td className="py-2 pr-4"><StatusBadge status={s.status} /></td>
                          <td className="py-2 pr-4 text-muted-foreground">{formatDateTime(s.requestedAt)}</td>
                          <td className="py-2 pr-4 text-muted-foreground">
                            {s.settledAt ? formatDateTime(s.settledAt) : "—"}
                          </td>
                          <td className="py-2">
                            {s.status === "REQUESTED" || s.status === "PENDING" ? (
                              <Button
                                size="sm"
                                className="min-h-9 bg-rfund-700 font-bold text-white hover:bg-rfund-800"
                                onClick={() => approve(s.id)}
                              >
                                Approve
                              </Button>
                            ) : (
                              <span className="text-xs text-muted-foreground">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </SectionCard>
          </div>
        </>
      )}
    </div>
  );
}
