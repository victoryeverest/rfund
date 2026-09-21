"use client";

import { useState } from "react";
import { useQuery } from "@apollo/client";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, TransactionItem,
} from "@/components/rfund/primitives";
import { PAYMENTS_QUERY } from "@/graphql/operations";
import { formatNaira, formatDateTime, titleize } from "@/lib/money";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Transactions" };

const PURPOSES = [
  { value: "", label: "All types" },
  { value: "SAVINGS_CONTRIBUTION", label: "Savings" },
  { value: "GOAL_FUNDING", label: "Goals" },
  { value: "LOAN_REPAYMENT", label: "Loan repayment" },
  { value: "ACCOUNT_FUNDING", label: "Account funding" },
];

const STATUSES = [
  { value: "", label: "All statuses" },
  { value: "SUCCESS", label: "Successful" },
  { value: "PENDING", label: "Pending" },
  { value: "FAILED", label: "Failed" },
];

export default function TransactionsPage() {
  const [purpose, setPurpose] = useState("");
  const [status, setStatus] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState<{ after?: string }>({});

  const { data, loading, error, refetch, fetchMore } = useQuery(PAYMENTS_QUERY, {
    variables: { first: 20, after: page.after, purpose: purpose || null, status: status || null },
    fetchPolicy: "cache-and-network",
  });

  const payments = (data?.payments?.items ?? []).filter((p: any) =>
    search
      ? p.reference.toLowerCase().includes(search.toLowerCase()) ||
        (p.providerReference ?? "").toLowerCase().includes(search.toLowerCase())
      : true
  );

  return (
    <div>
      <PageHeader
        title="Transactions"
        description="Every payment with its full reference — quote any reference to support for instant tracing."
      />
      <div className="mb-5 flex flex-wrap items-end gap-3">
        <div className="grid gap-1.5">
          <label className="text-xs font-bold text-rfund-900" htmlFor="txn-type">Type</label>
          <Select value={purpose} onValueChange={(v) => { setPurpose(v); setPage({}); }}>
            <SelectTrigger id="txn-type" className="min-h-11 w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              {PURPOSES.map((p) => <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-1.5">
          <label className="text-xs font-bold text-rfund-900" htmlFor="txn-status">Status</label>
          <Select value={status} onValueChange={(v) => { setStatus(v); setPage({}); }}>
            <SelectTrigger id="txn-status" className="min-h-11 w-40"><SelectValue /></SelectTrigger>
            <SelectContent>
              {STATUSES.map((s) => <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <div className="grid flex-1 gap-1.5 sm:max-w-xs">
          <label className="text-xs font-bold text-rfund-900" htmlFor="txn-search">Search reference</label>
          <Input
            id="txn-search"
            placeholder="RF-PAY-…"
            className="min-h-11"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Button variant="outline" className="min-h-11 font-bold" onClick={() => refetch()}>
          Refresh
        </Button>
      </div>

      {loading && !data ? (
        <LoadingState label="Loading transactions…" />
      ) : error ? (
        <ErrorState message="We could not load your transactions." onRetry={() => refetch()} />
      ) : payments.length === 0 ? (
        <EmptyState
          title="No transactions found."
          description={search || purpose || status ? "Try clearing the filters." : "Your payments will appear here."}
        />
      ) : (
        <div className="space-y-3">
          {payments.map((p: any) => (
            <TransactionItem
              key={p.id}
              reference={p.reference}
              title={titleize(p.purpose)}
              subtitle={`${titleize(p.method || "card")} · ${p.provider}`}
              amount={formatNaira(p.amount)}
              status={p.status}
              date={formatDateTime(p.createdAt)}
            />
          ))}
          {data?.payments?.pageInfo?.hasNextPage ? (
            <Button
              variant="outline"
              className="min-h-11 w-full font-bold"
              onClick={() =>
                fetchMore({
                  variables: { after: data.payments.pageInfo.nextCursor },
                  updateQuery: (prev, { fetchMoreResult }) => {
                    if (!fetchMoreResult) return prev;
                    return {
                      ...prev,
                      payments: {
                        ...fetchMoreResult.payments,
                        items: [...prev.payments.items, ...fetchMoreResult.payments.items],
                      },
                    };
                  },
                })
              }
            >
              Load more
            </Button>
          ) : null}
          <p className="pt-2 text-center text-xs text-muted-foreground">
            Showing {payments.length} of {data?.payments?.pageInfo?.totalCount ?? payments.length}
          </p>
        </div>
      )}
    </div>
  );
}
