"use client";

import { useState } from "react";
import { useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, StatusBadge, SectionCard,
} from "@/components/rfund/primitives";
import { ADMIN_PAYMENTS_QUERY, ADMIN_WEBHOOKS_QUERY } from "@/graphql/operations";
import { formatNaira, formatDateTime, titleize } from "@/lib/money";

const STATUSES = ["", "SUCCESS", "PENDING", "FAILED", "REVERSED"];

export default function AdminPaymentsPage() {
  const [status, setStatus] = useState("");
  const paymentsQuery = useQuery(ADMIN_PAYMENTS_QUERY, {
    variables: { status: status || null },
    fetchPolicy: "cache-and-network",
  });
  const webhooksQuery = useQuery(ADMIN_WEBHOOKS_QUERY, { fetchPolicy: "cache-and-network" });

  const payments = paymentsQuery.data?.adminPayments?.items ?? [];
  const webhooks = webhooksQuery.data?.adminWebhooks?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Payments"
        description="Provider payment operations and incoming webhook processing."
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

      {paymentsQuery.loading && !paymentsQuery.data ? (
        <LoadingState />
      ) : paymentsQuery.error ? (
        <ErrorState message="We could not load payments (permission required)." onRetry={() => paymentsQuery.refetch()} />
      ) : payments.length === 0 ? (
        <EmptyState title="No payments found." />
      ) : (
        <SectionCard title={`${paymentsQuery.data?.adminPayments?.pageInfo?.totalCount ?? payments.length} payments`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead>
                <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-4 font-semibold">Reference</th>
                  <th className="py-2 pr-4 font-semibold">Customer</th>
                  <th className="py-2 pr-4 font-semibold">Purpose</th>
                  <th className="py-2 pr-4 font-semibold">Amount</th>
                  <th className="py-2 pr-4 font-semibold">Status</th>
                  <th className="py-2 pr-4 font-semibold">Provider</th>
                  <th className="py-2 pr-4 font-semibold">Provider ref</th>
                  <th className="py-2 font-semibold">Created</th>
                </tr>
              </thead>
              <tbody>
                {payments.map((p: any) => (
                  <tr key={p.id} className="border-b border-rfund-line/60 last:border-0">
                    <td className="py-3 pr-4 font-mono text-xs">{p.reference}</td>
                    <td className="py-2 pr-4 font-semibold text-rfund-900">{p.customerName}</td>
                    <td className="py-2 pr-4">{titleize(p.purpose)}</td>
                    <td className="py-2 pr-4 font-semibold">{formatNaira(p.amount, { decimals: false })}</td>
                    <td className="py-2 pr-4"><StatusBadge status={p.status} /></td>
                    <td className="py-2 pr-4">{p.provider}</td>
                    <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">{p.providerReference || "—"}</td>
                    <td className="py-2 text-muted-foreground">{formatDateTime(p.createdAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      <div className="mt-6">
        {webhooksQuery.loading && !webhooksQuery.data ? (
          <LoadingState label="Loading webhooks…" />
        ) : webhooksQuery.error ? (
          <ErrorState message="We could not load webhooks (permission required)." onRetry={() => webhooksQuery.refetch()} />
        ) : webhooks.length === 0 ? (
          <EmptyState title="No provider webhooks received yet." />
        ) : (
          <SectionCard title="Provider webhooks">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-4 font-semibold">Provider</th>
                    <th className="py-2 pr-4 font-semibold">Event</th>
                    <th className="py-2 pr-4 font-semibold">Event ID</th>
                    <th className="py-2 pr-4 font-semibold">Signature</th>
                    <th className="py-2 pr-4 font-semibold">Processing</th>
                    <th className="py-2 font-semibold">Received</th>
                  </tr>
                </thead>
                <tbody>
                  {webhooks.map((w: any) => (
                    <tr key={w.id} className="border-b border-rfund-line/60 last:border-0">
                      <td className="py-3 pr-4 font-semibold text-rfund-900">{w.provider}</td>
                      <td className="py-2 pr-4">{w.eventType}</td>
                      <td className="py-2 pr-4 font-mono text-xs text-muted-foreground">{w.eventId}</td>
                      <td className="py-2 pr-4">
                        <StatusBadge status={w.signatureValid ? "VALID" : "INVALID"} />
                      </td>
                      <td className="py-2 pr-4">
                        <StatusBadge status={w.processingStatus} />
                        {w.processingError ? (
                          <span className="ml-2 text-xs text-destructive">{w.processingError}</span>
                        ) : null}
                      </td>
                      <td className="py-2 text-muted-foreground">{formatDateTime(w.receivedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        )}
      </div>
    </div>
  );
}
