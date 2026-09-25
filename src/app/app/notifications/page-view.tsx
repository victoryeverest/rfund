"use client";

import { useQuery } from "@apollo/client/react";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, SectionCard, StatusBadge,
} from "@/components/rfund/primitives";
import { NOTIFICATIONS_QUERY } from "@/graphql/operations";
import { formatNaira, formatDateTime } from "@/lib/money";
import { Bell, MessageSquare, CheckCheck } from "lucide-react";

export default function NotificationsPage() {
  const { data, loading, error, refetch } = useQuery(NOTIFICATIONS_QUERY, {
    variables: { first: 30 },
    fetchPolicy: "cache-and-network",
  });

  const items = data?.notifications?.items ?? [];
  const total = data?.notifications?.totalCount ?? 0;

  return (
    <div>
      <PageHeader
        title="Notifications"
        description="Account activity and alerts. Important events are also sent by SMS to your registered phone."
      />
      <SectionCard title={total > 0 ? `${total} notifications` : "Recent activity"}>
        {loading && !data ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message="We could not load your notifications." onRetry={() => refetch()} />
        ) : items.length === 0 ? (
          <EmptyState
            title="Nothing here yet."
            description="Savings payments, loan reminders and security events will appear here."
            action={
              <span className="inline-flex items-center gap-2 text-sm font-semibold text-rfund-700">
                <Bell className="h-4 w-4" aria-hidden /> We will alert you by SMS
              </span>
            }
          />
        ) : (
          <div className="space-y-3">
            {items.map((n: any) => (
              <div
                key={n.id}
                className="flex items-start justify-between gap-4 rounded-lg border border-rfund-line/60 bg-rfund-soft/40 p-4"
              >
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-bold text-rfund-900">{n.label}</p>
                    <span
                      className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-bold"
                      style={
                        n.dispatched
                          ? { backgroundColor: "#DCFCE7", color: "#166534" }
                          : { backgroundColor: "#FEF3C7", color: "#92400E" }
                      }
                    >
                      {n.dispatched ? (
                        <>
                          <CheckCheck className="h-3 w-3" aria-hidden /> SMS sent
                        </>
                      ) : (
                        <>
                          <MessageSquare className="h-3 w-3" aria-hidden /> SMS pending
                        </>
                      )}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {n.reference ? (
                      <span className="font-mono">{n.reference}</span>
                    ) : null}
                    {n.reference ? " · " : ""}
                    {formatDateTime(n.createdAt)}
                  </p>
                </div>
                {n.amount ? (
                  <p className="shrink-0 text-sm font-extrabold text-rfund-900">
                    {formatNaira(n.amount, { decimals: false })}
                  </p>
                ) : null}
              </div>
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
