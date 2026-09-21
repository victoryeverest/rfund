"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, StatusBadge, SectionCard,
} from "@/components/rfund/primitives";
import { ADMIN_CUSTOMERS_QUERY } from "@/graphql/operations";
import { formatDate, formatDateTime, titleize } from "@/lib/money";
import { Search } from "lucide-react";

export default function AdminCustomersPage() {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const { data, loading, error, refetch } = useQuery(ADMIN_CUSTOMERS_QUERY, {
    variables: { search: search || null, status: status || null, first: 30 },
    fetchPolicy: "cache-and-network",
  });

  const customers = data?.adminCustomers?.items ?? [];

  return (
    <div>
      <PageHeader title="Customers" description="Search, review and manage customer records." />
      <div className="mb-5 flex flex-wrap gap-3">
        <div className="relative flex-1 sm:max-w-sm">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            className="min-h-11 pl-9"
            placeholder="Name, phone or reference…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Search customers"
          />
        </div>
        {["", "ACTIVE", "SUSPENDED", "DEACTIVATED"].map((s) => (
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

      {loading && !data ? (
        <LoadingState />
      ) : error ? (
        <ErrorState message="We could not load customers (permission required)." onRetry={() => refetch()} />
      ) : customers.length === 0 ? (
        <EmptyState title="No customers found." />
      ) : (
        <SectionCard title={`${data?.adminCustomers?.pageInfo?.totalCount ?? customers.length} customers`}>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-b border-rfund-line text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="py-2 pr-4 font-semibold">Reference</th>
                  <th className="py-2 pr-4 font-semibold">Name</th>
                  <th className="py-2 pr-4 font-semibold">Phone</th>
                  <th className="py-2 pr-4 font-semibold">Location</th>
                  <th className="py-2 pr-4 font-semibold">KYC</th>
                  <th className="py-2 pr-4 font-semibold">Status</th>
                  <th className="py-2 font-semibold">Joined</th>
                </tr>
              </thead>
              <tbody>
                {customers.map((c: any) => (
                  <tr key={c.id} className="border-b border-rfund-line/60 last:border-0">
                    <td className="py-3 pr-4 font-mono text-xs">{c.customerReference}</td>
                    <td className="py-2 pr-4 font-semibold text-rfund-900">{c.fullName}</td>
                    <td className="py-2 pr-4">{c.phone}</td>
                    <td className="py-2 pr-4 text-muted-foreground">{[c.state, c.lga].filter(Boolean).join(", ") || "—"}</td>
                    <td className="py-2 pr-4">{c.kycTier}</td>
                    <td className="py-2 pr-4"><StatusBadge status={c.status} /></td>
                    <td className="py-2 text-muted-foreground">{formatDate(c.createdAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}
    </div>
  );
}
