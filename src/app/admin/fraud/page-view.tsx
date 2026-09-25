"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, StatusBadge, SectionCard,
} from "@/components/rfund/primitives";
import { ADMIN_FRAUD_ALERTS_QUERY, ADMIN_REVIEW_FRAUD_MUTATION } from "@/graphql/operations";
import { extractErrorMessage } from "@/lib/graphql";
import { formatDateTime } from "@/lib/money";
import { AlertCircle } from "lucide-react";

const SEVERITY_STYLES: Record<string, { bg: string; fg: string }> = {
  CRITICAL: { bg: "#FEE2E2", fg: "#991B1B" },
  HIGH: { bg: "#FFEDD5", fg: "#9A3412" },
  MEDIUM: { bg: "#FEF3C7", fg: "#92400E" },
  LOW: { bg: "#E0E7FF", fg: "#3730A3" },
};

export default function AdminFraudPage() {
  const { data, loading, error, refetch } = useQuery(ADMIN_FRAUD_ALERTS_QUERY, {
    fetchPolicy: "cache-and-network",
  });
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [opError, setOpError] = useState<string | null>(null);
  const [reviewFraud] = useMutation(ADMIN_REVIEW_FRAUD_MUTATION);

  const alerts = data?.adminFraudAlerts?.items ?? [];

  const review = async (alertId: string, decision: string) => {
    const note = notes[alertId]?.trim();
    if (!note) {
      setOpError("Review notes are required for every decision (audit trail).");
      return;
    }
    setOpError(null);
    const result = await reviewFraud({ variables: { input: { alertId, decision, notes: note } } });
    if (result.errors?.length) {
      setOpError(extractErrorMessage(result.errors));
      return;
    }
    await refetch();
  };

  return (
    <div>
      <PageHeader
        title="Fraud alerts"
        description="Rule-engine signals. Every review decision is audited with your name, time and notes."
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
        <ErrorState message="We could not load fraud alerts (permission required)." onRetry={() => refetch()} />
      ) : alerts.length === 0 ? (
        <EmptyState title="No fraud alerts." description="The rule engine will surface suspicious activity here." />
      ) : (
        <div className="space-y-4">
          {alerts.map((alert: any) => {
            const sev = SEVERITY_STYLES[alert.severity] ?? SEVERITY_STYLES.LOW;
            return (
              <SectionCard key={alert.id} title={alert.ruleCode}>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                  <StatusBadge status={alert.status} />
                  <span
                    className="rounded-full px-2.5 py-0.5 text-[11px] font-extrabold"
                    style={{ backgroundColor: sev.bg, color: sev.fg }}
                  >
                    {alert.severity}
                  </span>
                  <span className="text-muted-foreground">
                    Resource: <span className="font-mono text-xs text-rfund-900">{alert.resourceType}#{String(alert.resourceId).slice(0, 8)}</span>
                  </span>
                  <span className="text-muted-foreground">{formatDateTime(alert.createdAt)}</span>
                </div>
                {alert.details ? (
                  <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg bg-rfund-soft p-3 text-xs text-muted-foreground">
                    {typeof alert.details === "string" ? alert.details : JSON.stringify(alert.details, null, 2)}
                  </pre>
                ) : null}
                {alert.status === "OPEN" || alert.status === "UNDER_REVIEW" ? (
                  <>
                    <Textarea
                      className="mt-3 min-h-20"
                      placeholder="Review notes (required — becomes part of the audit trail)…"
                      value={notes[alert.id] ?? ""}
                      onChange={(e) => setNotes({ ...notes, [alert.id]: e.target.value })}
                      aria-label={`Review notes for ${alert.ruleCode}`}
                    />
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button
                        variant="outline"
                        className="min-h-11 font-bold"
                        onClick={() => review(alert.id, "UNDER_REVIEW")}
                      >
                        Mark under review
                      </Button>
                      <Button
                        className="min-h-11 bg-rfund-700 font-bold text-white hover:bg-rfund-800"
                        onClick={() => review(alert.id, "CLEARED")}
                      >
                        Clear
                      </Button>
                      <Button
                        variant="outline"
                        className="min-h-11 border-destructive/40 font-bold text-destructive hover:bg-destructive/10"
                        onClick={() => review(alert.id, "CONFIRMED")}
                      >
                        Confirm fraud
                      </Button>
                    </div>
                  </>
                ) : null}
              </SectionCard>
            );
          })}
        </div>
      )}
    </div>
  );
}
