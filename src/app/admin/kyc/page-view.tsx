"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, StatusBadge, SectionCard,
} from "@/components/rfund/primitives";
import { ADMIN_KYC_QUEUE_QUERY, ADMIN_REVIEW_KYC_MUTATION } from "@/graphql/operations";
import { extractErrorMessage } from "@/lib/graphql";
import { formatDateTime, titleize } from "@/lib/money";
import { AlertCircle } from "lucide-react";

export default function AdminKycPage() {
  const { data, loading, error, refetch } = useQuery(ADMIN_KYC_QUEUE_QUERY, {
    fetchPolicy: "cache-and-network",
  });
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [opError, setOpError] = useState<string | null>(null);
  const [reviewKYC] = useMutation(ADMIN_REVIEW_KYC_MUTATION);

  const decide = async (profileId: string, decision: string, newLevel?: string) => {
    const reason = reasons[profileId]?.trim();
    if (!reason) {
      setOpError("A reason is required for every decision (audit trail).");
      return;
    }
    setOpError(null);
    const result = await reviewKYC({
      variables: { input: { profileId, decision, reason, newLevel: newLevel ?? null } },
    });
    if (result.errors?.length) {
      setOpError(extractErrorMessage(result.errors));
      return;
    }
    await refetch();
  };

  const queue = data?.adminKycQueue?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Identity verification queue"
        description="Review submitted identity documents. Every decision is audited with your name, time and reason."
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
        <ErrorState message="Permission required: kyc.review" onRetry={() => refetch()} />
      ) : queue.length === 0 ? (
        <EmptyState title="Queue is empty." description="No identity submissions awaiting review." />
      ) : (
        <div className="space-y-4">
          {queue.map((item: any) => (
            <SectionCard key={item.id} title={`${item.customerName} — ${item.customerReference}`}>
              <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                <StatusBadge status={item.status} />
                <span>Document: <strong className="text-rfund-900">{titleize(item.submittedDocType)}</strong></span>
                <span>Submitted {formatDateTime(item.createdAt)}</span>
                <span>Current level: {titleize(item.level)}</span>
              </div>
              <Textarea
                className="mt-3 min-h-20"
                placeholder="Decision reason (required — becomes part of the audit trail)…"
                value={reasons[item.id] ?? ""}
                onChange={(e) => setReasons({ ...reasons, [item.id]: e.target.value })}
                aria-label={`Reason for ${item.customerName}`}
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  className="min-h-11 bg-rfund-700 font-bold text-white hover:bg-rfund-800"
                  onClick={() => decide(item.id, "APPROVED", "STANDARD")}
                >
                  Approve → Standard
                </Button>
                <Button
                  variant="outline"
                  className="min-h-11 font-bold"
                  onClick={() => decide(item.id, "APPROVED", "ENHANCED")}
                >
                  Approve → Enhanced
                </Button>
                <Button
                  variant="outline"
                  className="min-h-11 font-bold"
                  onClick={() => decide(item.id, "INFO_REQUESTED")}
                >
                  Request more info
                </Button>
                <Button
                  variant="outline"
                  className="min-h-11 border-destructive/40 font-bold text-destructive hover:bg-destructive/10"
                  onClick={() => decide(item.id, "REJECTED")}
                >
                  Reject
                </Button>
              </div>
            </SectionCard>
          ))}
        </div>
      )}
    </div>
  );
}
