"use client";

import { useState } from "react";
import { useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, StatusBadge, SectionCard,
} from "@/components/rfund/primitives";
import { ADMIN_SUPPORT_QUERY } from "@/graphql/operations";
import { formatDateTime, titleize } from "@/lib/money";

const STATUSES = ["", "OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"];

const PRIORITY_STYLES: Record<string, { bg: string; fg: string }> = {
  URGENT: { bg: "#FEE2E2", fg: "#991B1B" },
  HIGH: { bg: "#FFEDD5", fg: "#9A3412" },
  NORMAL: { bg: "#E5E7EB", fg: "#374151" },
  LOW: { bg: "#E0E7FF", fg: "#3730A3" },
};

export default function AdminSupportPage() {
  const [status, setStatus] = useState("");
  const { data, loading, error, refetch } = useQuery(ADMIN_SUPPORT_QUERY, {
    variables: { status: status || null },
    fetchPolicy: "cache-and-network",
  });

  const tickets = data?.adminSupportTickets?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Support tickets"
        description="Customer support queue across all channels."
      />

      <div className="mb-5 flex flex-wrap gap-2">
        {STATUSES.map((s) => (
          <Button
            key={s}
            variant={status === s ? "default" : "outline"}
            className={`min-h-11 font-bold ${status === s ? "bg-rfund-700 text-white" : ""}`}
            onClick={() => setStatus(s)}
          >
            {s ? titleize(s) : "All"}
          </Button>
        ))}
      </div>

      {loading && !data ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message="We could not load support tickets (permission required)." onRetry={() => refetch()} />
      ) : tickets.length === 0 ? (
        <EmptyState title="No tickets found." />
      ) : (
        <SectionCard title={`${data?.adminSupportTickets?.pageInfo?.totalCount ?? tickets.length} tickets`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-sm">
              <thead>
                <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-4 font-semibold">Reference</th>
                  <th className="py-2 pr-4 font-semibold">Customer</th>
                  <th className="py-2 pr-4 font-semibold">Category</th>
                  <th className="py-2 pr-4 font-semibold">Subject</th>
                  <th className="py-2 pr-4 font-semibold">Status</th>
                  <th className="py-2 pr-4 font-semibold">Priority</th>
                  <th className="py-2 pr-4 font-semibold">Assignee</th>
                  <th className="py-2 font-semibold">Created</th>
                </tr>
              </thead>
              <tbody>
                {tickets.map((t: any) => {
                  const prio = PRIORITY_STYLES[t.priority] ?? PRIORITY_STYLES.NORMAL;
                  return (
                    <tr key={t.id} className="border-b border-rfund-line/60 last:border-0">
                      <td className="py-3 pr-4 font-mono text-xs">{t.reference}</td>
                      <td className="py-2 pr-4 font-semibold text-rfund-900">{t.customerName}</td>
                      <td className="py-2 pr-4">{titleize(t.category)}</td>
                      <td className="py-2 pr-4 max-w-[260px] truncate" title={t.subject}>{t.subject}</td>
                      <td className="py-2 pr-4"><StatusBadge status={t.status} /></td>
                      <td className="py-2 pr-4">
                        <span
                          className="rounded-full px-2.5 py-0.5 text-[11px] font-extrabold"
                          style={{ backgroundColor: prio.bg, color: prio.fg }}
                        >
                          {t.priority}
                        </span>
                      </td>
                      <td className="py-2 pr-4 text-muted-foreground">{t.assigneeName || "Unassigned"}</td>
                      <td className="py-2 text-muted-foreground">{formatDateTime(t.createdAt)}</td>
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
