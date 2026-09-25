"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, StatusBadge, SectionCard,
} from "@/components/rfund/primitives";
import { ADMIN_LEDGER_QUERY, ADMIN_REVERSE_TRANSACTION_MUTATION } from "@/graphql/operations";
import { extractErrorMessage } from "@/lib/graphql";
import { formatNaira, formatDateTime, titleize } from "@/lib/money";
import { AlertCircle, ChevronDown, ChevronRight } from "lucide-react";

export default function AdminLedgerPage() {
  const { data, loading, error, refetch } = useQuery(ADMIN_LEDGER_QUERY, {
    fetchPolicy: "cache-and-network",
  });
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [opError, setOpError] = useState<string | null>(null);
  const [reverseTransaction] = useMutation(ADMIN_REVERSE_TRANSACTION_MUTATION);

  const accounts = data?.adminLedgerAccounts ?? [];
  const txns = data?.adminLedgerTransactions?.items ?? [];

  const reverse = async (transactionId: string) => {
    const reason = reasons[transactionId]?.trim();
    if (!reason) {
      setOpError("A reason is required to reverse a ledger transaction (audit trail).");
      return;
    }
    setOpError(null);
    const result = await reverseTransaction({ variables: { transactionId, reason } });
    if (result.errors?.length) {
      setOpError(extractErrorMessage(result.errors));
      return;
    }
    await refetch();
  };

  return (
    <div>
      <PageHeader
        title="General ledger"
        description="Double-entry accounts and posted transactions. Reversals are audited and keep the books balanced."
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
        <ErrorState message="We could not load the ledger (permission required)." onRetry={() => refetch()} />
      ) : (
        <>
          <SectionCard title={`Chart of accounts (${accounts.length})`}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                    <th className="py-2 pr-4 font-semibold">Code</th>
                    <th className="py-2 pr-4 font-semibold">Account</th>
                    <th className="py-2 pr-4 font-semibold">Type</th>
                    <th className="py-2 pr-4 font-semibold">Balance</th>
                    <th className="py-2 pr-4 font-semibold">Status</th>
                    <th className="py-2 font-semibold">Last posted</th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.map((a: any) => (
                    <tr key={a.id} className="border-b border-rfund-line/60 last:border-0">
                      <td className="py-3 pr-4 font-mono text-xs">{a.code}</td>
                      <td className="py-2 pr-4 font-semibold text-rfund-900">{a.name}</td>
                      <td className="py-2 pr-4">{titleize(a.type)}</td>
                      <td className="py-2 pr-4 font-semibold">{formatNaira(a.balance, { decimals: false })}</td>
                      <td className="py-2 pr-4"><StatusBadge status={a.status} /></td>
                      <td className="py-2 text-muted-foreground">
                        {a.lastPostedAt ? formatDateTime(a.lastPostedAt) : "Never"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>

          <div className="mt-6">
            <SectionCard title={`${data?.adminLedgerTransactions?.pageInfo?.totalCount ?? txns.length} posted transactions`}>
              {txns.length === 0 ? (
                <EmptyState title="No transactions posted yet." />
              ) : (
                <div className="space-y-3">
                  {txns.map((t: any) => (
                    <div key={t.id} className="rounded-lg border border-rfund-line/60">
                      <button
                        type="button"
                        className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 p-4 text-left"
                        onClick={() => setExpanded({ ...expanded, [t.id]: !expanded[t.id] })}
                        aria-expanded={!!expanded[t.id]}
                      >
                        {expanded[t.id] ? (
                          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                        ) : (
                          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                        )}
                        <span className="font-mono text-xs">{t.reference}</span>
                        <span className="text-sm font-semibold text-rfund-900">{titleize(t.transactionType)}</span>
                        <StatusBadge status={t.status} />
                        <span className="ml-auto text-xs text-muted-foreground">{formatDateTime(t.postedAt ?? t.createdAt)}</span>
                      </button>
                      {expanded[t.id] ? (
                        <div className="border-t border-rfund-line/60 p-4">
                          <p className="text-sm text-muted-foreground">{t.description}</p>
                          {t.externalReference ? (
                            <p className="mt-1 text-xs text-muted-foreground">
                              External ref: <span className="font-mono">{t.externalReference}</span>
                            </p>
                          ) : null}
                          <div className="mt-3 overflow-x-auto">
                            <table className="w-full min-w-[520px] text-sm">
                              <thead>
                                <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                                  <th className="py-2 pr-4 font-semibold">Account</th>
                                  <th className="py-2 pr-4 font-semibold">Direction</th>
                                  <th className="py-2 font-semibold">Amount</th>
                                </tr>
                              </thead>
                              <tbody>
                                {t.entries?.map((e: any, i: number) => (
                                  <tr key={i} className="border-b border-rfund-line/40 last:border-0">
                                    <td className="py-2 pr-4">
                                      <span className="font-mono text-xs">{e.accountCode}</span>{" "}
                                      <span className="text-muted-foreground">{e.accountName}</span>
                                    </td>
                                    <td className="py-2 pr-4">{e.direction === "DEBIT" ? "Debit" : "Credit"}</td>
                                    <td className="py-2 font-semibold">{formatNaira(e.amount, { decimals: false })}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                          {t.status === "POSTED" ? (
                            <div className="mt-4">
                              <Textarea
                                className="min-h-16"
                                placeholder="Reversal reason (required — becomes part of the audit trail)…"
                                value={reasons[t.id] ?? ""}
                                onChange={(e) => setReasons({ ...reasons, [t.id]: e.target.value })}
                                aria-label={`Reversal reason for ${t.reference}`}
                              />
                              <Button
                                variant="outline"
                                className="mt-2 min-h-10 border-destructive/40 font-bold text-destructive hover:bg-destructive/10"
                                onClick={() => reverse(t.id)}
                              >
                                Reverse transaction
                              </Button>
                            </div>
                          ) : null}
                        </div>
                      ) : null}
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
