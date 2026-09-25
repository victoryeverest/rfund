"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, StatusBadge, SectionCard,
} from "@/components/rfund/primitives";
import {
  ADMIN_RECONCILIATION_QUERY,
  ADMIN_RUN_RECONCILIATION_MUTATION,
  ADMIN_RESOLVE_EXCEPTION_MUTATION,
} from "@/graphql/operations";
import { extractErrorMessage } from "@/lib/graphql";
import { formatNaira, formatDateTime, titleize } from "@/lib/money";
import { AlertCircle, Play } from "lucide-react";

export default function AdminReconciliationPage() {
  const { data, loading, error, refetch } = useQuery(ADMIN_RECONCILIATION_QUERY, {
    fetchPolicy: "cache-and-network",
  });
  const [opError, setOpError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [runReconciliation] = useMutation(ADMIN_RUN_RECONCILIATION_MUTATION);
  const [resolveException] = useMutation(ADMIN_RESOLVE_EXCEPTION_MUTATION);

  const runs = data?.adminReconciliationRuns ?? [];
  const exceptions = data?.adminReconciliationExceptions ?? [];
  const openExceptions = exceptions.filter((e: any) => !e.resolved);

  const run = async () => {
    setOpError(null);
    setBusy(true);
    try {
      const result = await runReconciliation({ variables: { provider: "paystack" } });
      if (result.errors?.length) {
        setOpError(extractErrorMessage(result.errors));
        return;
      }
      await refetch();
    } finally {
      setBusy(false);
    }
  };

  const resolve = async (exceptionId: string, resolution: string) => {
    setOpError(null);
    const result = await resolveException({ variables: { input: { exceptionId, resolution } } });
    if (result.errors?.length) {
      setOpError(extractErrorMessage(result.errors));
      return;
    }
    await refetch();
  };

  return (
    <div>
      <PageHeader
        title="Reconciliation"
        description="Match internal records against provider settlements. Every run and resolution is audited."
        action={
          <Button
            onClick={run}
            disabled={busy}
            className="min-h-11 bg-rfund-700 font-bold text-white hover:bg-rfund-800"
          >
            <Play className="mr-1.5 h-4 w-4" aria-hidden /> {busy ? "Running…" : "Run reconciliation"}
          </Button>
        }
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
        <ErrorState message="We could not load reconciliation data (permission required)." onRetry={() => refetch()} />
      ) : (
        <>
          <SectionCard title={`Reconciliation runs (${runs.length})`}>
            {runs.length === 0 ? (
              <EmptyState title="No reconciliation runs yet." description="Start a run to match records against the provider." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-sm">
                  <thead>
                    <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                      <th className="py-2 pr-4 font-semibold">Provider</th>
                      <th className="py-2 pr-4 font-semibold">Period</th>
                      <th className="py-2 pr-4 font-semibold">Status</th>
                      <th className="py-2 pr-4 font-semibold">Matched</th>
                      <th className="py-2 pr-4 font-semibold">Exceptions</th>
                      <th className="py-2 font-semibold">Started</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runs.map((r: any) => (
                      <tr key={r.id} className="border-b border-rfund-line/60 last:border-0">
                        <td className="py-3 pr-4 font-semibold text-rfund-900">{titleize(r.provider)}</td>
                        <td className="py-2 pr-4 text-muted-foreground">
                          {r.periodStart ? `${r.periodStart.slice(0, 10)} → ${r.periodEnd?.slice(0, 10) ?? ""}` : "—"}
                        </td>
                        <td className="py-2 pr-4"><StatusBadge status={r.status} /></td>
                        <td className="py-2 pr-4 font-semibold">{r.matchedCount}</td>
                        <td className="py-2 pr-4 font-semibold text-destructive">{r.exceptionCount}</td>
                        <td className="py-2 text-muted-foreground">{formatDateTime(r.startedAt)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>

          <div className="mt-6">
            <SectionCard title={`Exceptions (${openExceptions.length} open)`}>
              {exceptions.length === 0 ? (
                <EmptyState title="No exceptions." description="All records match the provider." />
              ) : (
                <div className="space-y-3">
                  {exceptions.map((e: any) => (
                    <div
                      key={e.id}
                      className={`rounded-lg border p-4 ${e.resolved ? "border-rfund-line/40 opacity-70" : "border-rfund-gold/50 bg-rfund-gold/5"}`}
                    >
                      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
                        <StatusBadge status={e.itemStatus} />
                        <span className="font-mono text-xs">{e.internalReference}</span>
                        <span className="text-muted-foreground">vs</span>
                        <span className="font-mono text-xs">{e.providerReference || "missing"}</span>
                        <span className="ml-auto font-semibold">
                          {formatNaira(e.internalAmount, { decimals: false })} / {formatNaira(e.providerAmount, { decimals: false })}
                        </span>
                      </div>
                      {e.reason ? (
                        <p className="mt-2 text-sm text-muted-foreground">{e.reason}</p>
                      ) : null}
                      {e.resolved ? (
                        <p className="mt-2 text-xs font-bold text-rfund-700">Resolved: {e.resolution}</p>
                      ) : (
                        <div className="mt-3 flex flex-wrap gap-2">
                          <Button
                            size="sm"
                            className="min-h-10 bg-rfund-700 font-bold text-white hover:bg-rfund-800"
                            onClick={() =>
                              resolve(
                                e.id,
                                `Adjusted internal record ${e.internalReference} to match provider ${e.providerReference || "statement"}`
                              )
                            }
                          >
                            Adjust internal record
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="min-h-10 font-bold"
                            onClick={() =>
                              resolve(e.id, `Provider confirmed ${e.providerReference || "item"} is correct; internal record stands corrected`)
                            }
                          >
                            Accept provider value
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            className="min-h-10 font-bold"
                            onClick={() => resolve(e.id, "Marked as a known processing lag; matched on re-run")}
                          >
                            Defer (lag)
                          </Button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
          </div>
        </>
      )}
    </div>
  );
}
