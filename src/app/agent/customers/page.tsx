"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@apollo/client";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, StatusBadge,
} from "@/components/rfund/primitives";
import { AGENT_CUSTOMERS_QUERY } from "@/graphql/operations";
import { Search, UserRound } from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Agent customers" };

export default function AgentCustomersPage() {
  const [search, setSearch] = useState("");
  const { data, loading, error, refetch } = useQuery(AGENT_CUSTOMERS_QUERY, {
    variables: { search: search || null, first: 20 },
    fetchPolicy: "cache-and-network",
  });

  const customers = data?.agentCustomers?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Customers"
        description="Find any RFUND customer to collect savings or process a payout."
      />
      <div className="mb-5 flex gap-2">
        <div className="relative flex-1 sm:max-w-md">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            className="min-h-12 pl-9"
            placeholder="Search name, phone or reference…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search customers"
          />
        </div>
        <Button variant="outline" className="min-h-12 font-bold" onClick={() => refetch()}>
          Refresh
        </Button>
      </div>

      {loading && !data ? (
        <LoadingState label="Finding customers…" />
      ) : error ? (
        <ErrorState message="We could not load customers." onRetry={() => refetch()} />
      ) : customers.length === 0 ? (
        <EmptyState
          title={search ? `No customers match “${search}”.` : "No customers found."}
          description="Try a different name or phone number."
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {customers.map((c: any) => (
            <Link
              key={c.id}
              href={`/agent/customers/${c.id}`}
              className="flex items-center gap-4 rounded-xl border border-rfund-line bg-white p-4 transition hover:border-rfund-400 focus-visible:outline-2 focus-visible:outline-rfund-700"
            >
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-rfund-100 text-rfund-700" aria-hidden>
                <UserRound className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <p className="truncate text-sm font-extrabold text-rfund-900">{c.fullName}</p>
                  <StatusBadge status={c.status} />
                </div>
                <p className="mt-0.5 truncate text-xs text-muted-foreground">
                  {c.phone} · {c.customerReference} · KYC {c.kycTier}
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
