"use client";

import { useQuery } from "@apollo/client";
import { PageHeader, StatCard, LoadingState, ErrorState } from "@/components/rfund/primitives";
import { ADMIN_DASHBOARD_QUERY } from "@/graphql/operations";
import { formatNaira } from "@/lib/money";
import { Users, PiggyBank, Landmark, ShieldAlert, LifeBuoy, Wallet } from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Admin dashboard" };

export default function AdminDashboardPage() {
  const { data, loading, error, refetch } = useQuery(ADMIN_DASHBOARD_QUERY, {
    fetchPolicy: "cache-and-network",
  });

  if (loading && !data) return <LoadingState label="Loading platform KPIs…" />;
  if (error)
    return (
      <ErrorState
        title="Administrator access required"
        message="This dashboard requires staff permissions. If you believe this is an error, contact the platform owner."
        onRetry={() => refetch()}
      />
    );

  const d = data?.adminDashboard;
  return (
    <div>
      <PageHeader
        title="Platform dashboard"
        description="Operational KPIs across customers, savings, loans, payments and risk. No personal data on this screen."
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Active customers" value={String(d?.activeCustomers ?? 0)} hint={`+${d?.newCustomers7d ?? 0} in 7 days`} icon={<Users className="h-5 w-5" />} tone="dark" />
        <StatCard label="Savings balance" value={formatNaira(d?.savingsBalance ?? "0", { compact: true })} hint={`${d?.activeSavingsPlans ?? 0} active plans`} icon={<PiggyBank className="h-5 w-5" />} tone="gold" />
        <StatCard label="Loan portfolio" value={formatNaira(d?.loanPortfolio ?? "0", { compact: true })} hint={`${d?.activeLoans ?? 0} active loans`} icon={<Landmark className="h-5 w-5" />} />
        <StatCard label="Repayments (30d)" value={formatNaira(d?.repaymentVolume30d ?? "0", { compact: true })} hint={`Interest income ${formatNaira(d?.interestIncome ?? "0", { compact: true })}`} />
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Pending KYC" value={String(d?.pendingKyc ?? 0)} icon={<Users className="h-5 w-5" />} />
        <StatCard label="Pending loan apps" value={String(d?.pendingLoanApplications ?? 0)} />
        <StatCard label="Payment failures (24h)" value={String(d?.paymentFailures24h ?? 0)} />
        <StatCard label="Reconciliation exceptions" value={String(d?.reconciliationExceptions ?? 0)} icon={<Wallet className="h-5 w-5" />} />
      </div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Active agents" value={String(d?.activeAgents ?? 0)} />
        <StatCard label="Agent collections today" value={formatNaira(d?.agentCollectionsToday ?? "0", { compact: true })} />
        <StatCard label="Open fraud alerts" value={String(d?.openFraudAlerts ?? 0)} icon={<ShieldAlert className="h-5 w-5" />} />
        <StatCard label="Open support tickets" value={String(d?.openSupportTickets ?? 0)} icon={<LifeBuoy className="h-5 w-5" />} />
      </div>
    </div>
  );
}
