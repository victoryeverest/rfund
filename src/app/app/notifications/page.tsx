"use client";

import { useQuery } from "@apollo/client";
import { PageHeader, LoadingState, ErrorState, EmptyState, SectionCard, TransactionItem } from "@/components/rfund/primitives";
import { DASHBOARD_QUERY } from "@/graphql/operations";
import { formatNaira, formatDateTime, titleize } from "@/lib/money";
import type { Metadata } from "next";
import { Bell } from "lucide-react";

export const metadata: Metadata = { title: "Notifications" };

export default function NotificationsPage() {
  const { data, loading, error, refetch } = useQuery(DASHBOARD_QUERY);
  const payments = data?.payments?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Notifications"
        description="Recent account activity. Important alerts are also sent by SMS to your registered phone."
      />
      <SectionCard title="Recent activity">
        {loading && !data ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message="We could not load your notifications." onRetry={() => refetch()} />
        ) : payments.length === 0 ? (
          <EmptyState
            title="Nothing here yet."
            description="Payment and savings activity will appear here."
            action={
              <span className="inline-flex items-center gap-2 text-sm font-semibold text-rfund-700">
                <Bell className="h-4 w-4" aria-hidden /> We will alert you by SMS
              </span>
            }
          />
        ) : (
          <div className="space-y-3">
            {payments.map((p: any) => (
              <TransactionItem
                key={p.id}
                reference={p.reference}
                title={`${titleize(p.purpose)} ${p.status === "SUCCESS" ? "confirmed" : titleize(p.status)}`}
                amount={formatNaira(p.amount, { decimals: false })}
                status={p.status}
                date={formatDateTime(p.createdAt)}
              />
            ))}
          </div>
        )}
      </SectionCard>
      <p className="mt-4 text-xs text-muted-foreground">
        SMS alerts are sent for successful payments, savings dues, loan reminders and security
        events. Standard message rates may apply.
      </p>
    </div>
  );
}
