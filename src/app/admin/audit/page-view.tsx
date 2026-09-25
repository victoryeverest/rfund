"use client";

import { useState } from "react";
import { useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, SectionCard,
} from "@/components/rfund/primitives";
import { ADMIN_AUDIT_QUERY } from "@/graphql/operations";
import { formatDateTime, titleize } from "@/lib/money";

const RESOURCE_TYPES = ["", "customer", "savings_plan", "loan_application", "loan", "payment", "ledger_transaction", "agent", "fraud_alert", "kyc_profile", "report"];

const ACTION_STYLES: Record<string, { bg: string; fg: string }> = {
  CREATE: { bg: "#DCFCE7", fg: "#166534" },
  UPDATE: { bg: "#E0E7FF", fg: "#3730A3" },
  LOGIN: { bg: "#E5E7EB", fg: "#374151" },
  LOGOUT: { bg: "#E5E7EB", fg: "#6B7280" },
  EXPORT: { bg: "#FEF3C7", fg: "#92400E" },
  APPROVE: { bg: "#DCFCE7", fg: "#166534" },
  REJECT: { bg: "#FEE2E2", fg: "#991B1B" },
  REVERSE: { bg: "#FEE2E2", fg: "#991B1B" },
  SUSPEND: { bg: "#FEE2E2", fg: "#991B1B" },
};

export default function AdminAuditPage() {
  const [resourceType, setResourceType] = useState("");
  const { data, loading, error, refetch } = useQuery(ADMIN_AUDIT_QUERY, {
    variables: { resourceType: resourceType || null },
    fetchPolicy: "cache-and-network",
  });

  const events = data?.adminAuditEvents?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Audit trail"
        description="Immutable record of every privileged action — who, what, when and why."
      />

      <div className="mb-5 flex flex-wrap gap-2">
        {RESOURCE_TYPES.map((rt) => (
          <Button
            key={rt}
            variant={resourceType === rt ? "default" : "outline"}
            className={`min-h-11 font-bold ${resourceType === rt ? "bg-rfund-700 text-white" : ""}`}
            onClick={() => setResourceType(rt)}
          >
            {rt ? titleize(rt) : "All"}
          </Button>
        ))}
      </div>

      {loading && !data ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message="We could not load the audit trail (permission required)." onRetry={() => refetch()} />
      ) : events.length === 0 ? (
        <EmptyState title="No audit events found." />
      ) : (
        <SectionCard title={`${data?.adminAuditEvents?.pageInfo?.totalCount ?? events.length} events`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead>
                <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-4 font-semibold">When</th>
                  <th className="py-2 pr-4 font-semibold">Actor</th>
                  <th className="py-2 pr-4 font-semibold">Action</th>
                  <th className="py-2 pr-4 font-semibold">Resource</th>
                  <th className="py-2 pr-4 font-semibold">Reason</th>
                  <th className="py-2 font-semibold">IP</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e: any) => {
                  const style = ACTION_STYLES[e.action] ?? { bg: "#F3F4F6", fg: "#374151" };
                  return (
                    <tr key={e.id} className="border-b border-rfund-line/60 last:border-0">
                      <td className="py-3 pr-4 whitespace-nowrap text-muted-foreground">{formatDateTime(e.occurredAt)}</td>
                      <td className="py-2 pr-4 font-semibold text-rfund-900">{e.actorLabel}</td>
                      <td className="py-2 pr-4">
                        <span
                          className="rounded-full px-2.5 py-0.5 text-[11px] font-extrabold"
                          style={{ backgroundColor: style.bg, color: style.fg }}
                        >
                          {titleize(e.action)}
                        </span>
                      </td>
                      <td className="py-2 pr-4">
                        <span className="text-xs">{titleize(e.resourceType)}</span>{" "}
                        <span className="font-mono text-xs text-muted-foreground">
                          #{String(e.resourceId).slice(0, 8)}
                        </span>
                      </td>
                      <td className="py-2 pr-4 max-w-[280px] truncate text-muted-foreground" title={e.reason || ""}>
                        {e.reason || "—"}
                      </td>
                      <td className="py-2 font-mono text-xs text-muted-foreground">{e.ipAddress || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}
    </div>
  );
}
