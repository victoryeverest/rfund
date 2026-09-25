"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, StatusBadge, SectionCard, StatCard,
} from "@/components/rfund/primitives";
import {
  ADMIN_LOAN_APPLICATIONS_QUERY,
  ADMIN_DECIDE_LOAN_MUTATION,
  ADMIN_DISBURSE_LOAN_MUTATION,
} from "@/graphql/operations";
import { extractErrorMessage } from "@/lib/graphql";
import { formatNaira, formatDateTime, titleize } from "@/lib/money";
import { AlertCircle } from "lucide-react";

const STATES = ["", "PENDING", "APPROVED", "OFFERED", "REJECTED", "DISBURSED"];

export default function AdminLoansPage() {
  const [state, setState] = useState("");
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [opError, setOpError] = useState<string | null>(null);
  const { data, loading, error, refetch } = useQuery(ADMIN_LOAN_APPLICATIONS_QUERY, {
    variables: { state: state || null },
    fetchPolicy: "cache-and-network",
  });
  const [decideLoan] = useMutation(ADMIN_DECIDE_LOAN_MUTATION);
  const [disburseLoan] = useMutation(ADMIN_DISBURSE_LOAN_MUTATION);

  const apps = data?.adminLoanApplications?.items ?? [];

  const decide = async (applicationId: string, approve: boolean) => {
    const reason = reasons[applicationId]?.trim();
    if (!reason) {
      setOpError("A reason is required for every decision (audit trail).");
      return;
    }
    setOpError(null);
    const result = await decideLoan({
      variables: { input: { applicationId, approve, reason } },
    });
    if (result.errors?.length) {
      setOpError(extractErrorMessage(result.errors));
      return;
    }
    await refetch();
  };

  const disburse = async (applicationId: string) => {
    setOpError(null);
    const result = await disburseLoan({ variables: { applicationId } });
    if (result.errors?.length) {
      setOpError(extractErrorMessage(result.errors));
      return;
    }
    await refetch();
  };

  const pending = apps.filter((a: any) => a.state === "PENDING").length;
  const approved = apps.filter((a: any) => a.state === "APPROVED").length;

  return (
    <div>
      <PageHeader
        title="Loan applications"
        description="Review, decide and disburse. Every decision is audited with your name, time and reason."
      />
      {opError ? (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="h-4 w-4" aria-hidden />
          <AlertDescription>{opError}</AlertDescription>
        </Alert>
      ) : null}

      <div className="mb-5 grid gap-4 sm:grid-cols-3">
        <StatCard
          label="Total in view"
          value={String(data?.adminLoanApplications?.pageInfo?.totalCount ?? apps.length)}
          tone="dark"
        />
        <StatCard label="Awaiting decision" value={String(pending)} />
        <StatCard label="Approved (awaiting offer/disbursement)" value={String(approved)} tone="gold" />
      </div>

      <div className="mb-5 flex flex-wrap gap-2">
        {STATES.map((s) => (
          <Button
            key={s}
            variant={state === s ? "default" : "outline"}
            className={`min-h-11 font-bold ${state === s ? "bg-rfund-700 text-white" : ""}`}
            onClick={() => setState(s)}
          >
            {s ? titleize(s) : "All"}
          </Button>
        ))}
      </div>

      {loading && !data ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message="We could not load loan applications (permission required)." onRetry={() => refetch()} />
      ) : apps.length === 0 ? (
        <EmptyState title="No applications found." description="Applications matching this filter will appear here." />
      ) : (
        <div className="space-y-4">
          {apps.map((app: any) => (
            <SectionCard key={app.id} title={`${app.reference} — ${app.customerName}`}>
              <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm text-muted-foreground">
                <StatusBadge status={app.state} />
                <span>Customer: <strong className="font-mono text-xs text-rfund-900">{app.customerReference}</strong></span>
                <span>Product: <strong className="text-rfund-900">{app.productName}</strong></span>
                <span>Amount: <strong className="text-rfund-900">{formatNaira(app.amountRequested, { decimals: false })}</strong></span>
                <span>Term: <strong className="text-rfund-900">{app.termMonths} months</strong></span>
                <span>Risk score: <strong className="text-rfund-900">{app.riskScore ?? "—"}</strong></span>
                <span>Risk decision: <strong className="text-rfund-900">{app.riskDecision ?? "—"}</strong></span>
                <span>Submitted {formatDateTime(app.createdAt)}</span>
              </div>
              {app.state === "PENDING" ? (
                <>
                  <Textarea
                    className="mt-3 min-h-20"
                    placeholder="Decision reason (required — becomes part of the audit trail)…"
                    value={reasons[app.id] ?? ""}
                    onChange={(e) => setReasons({ ...reasons, [app.id]: e.target.value })}
                    aria-label={`Reason for ${app.reference}`}
                  />
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button
                      className="min-h-11 bg-rfund-700 font-bold text-white hover:bg-rfund-800"
                      onClick={() => decide(app.id, true)}
                    >
                      Approve
                    </Button>
                    <Button
                      variant="outline"
                      className="min-h-11 border-destructive/40 font-bold text-destructive hover:bg-destructive/10"
                      onClick={() => decide(app.id, false)}
                    >
                      Reject
                    </Button>
                  </div>
                </>
              ) : app.state === "OFFERED" || app.state === "ACCEPTED" ? (
                <div className="mt-3">
                  <Button
                    className="min-h-11 bg-rfund-gold font-extrabold text-rfund-900 hover:bg-rfund-gold-dark"
                    onClick={() => disburse(app.id)}
                  >
                    Disburse funds
                  </Button>
                </div>
              ) : null}
            </SectionCard>
          ))}
        </div>
      )}
    </div>
  );
}
