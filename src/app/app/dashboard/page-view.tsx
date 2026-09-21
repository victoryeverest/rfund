"use client";

import Link from "next/link";
import { useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import {
  PageHeader, StatCard, SectionCard, LoadingState, ErrorState, EmptyState,
  TransactionItem, StatusBadge,
} from "@/components/rfund/primitives";
import { DASHBOARD_QUERY, SAVINGS_PLANS_QUERY } from "@/graphql/operations";
import { formatNaira, formatDate, formatDateTime, titleize } from "@/lib/money";
import { PiggyBank, Landmark, Target, CalendarClock, Plus, ArrowRight } from "lucide-react";

export default function CustomerDashboard() {
  const { data, loading, error, refetch } = useQuery(DASHBOARD_QUERY, { fetchPolicy: "cache-and-network" });
  const plansQuery = useQuery(SAVINGS_PLANS_QUERY, { variables: { first: 3 } });

  if (loading && !data) return <LoadingState label="Loading your dashboard…" />;
  if (error)
    return (
      <ErrorState
        message="We could not load your dashboard. This may be a connection problem."
        onRetry={() => refetch()}
      />
    );

  const d = data?.dashboard;
  const plans = plansQuery.data?.savingsPlans?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Dashboard"
        description="Your money at a glance — every figure comes from the RFUND ledger."
        action={
          <Button asChild className="min-h-11 bg-rfund-700 font-bold text-white hover:bg-rfund-800">
            <Link href="/app/savings">
              <Plus className="mr-1.5 h-4 w-4" aria-hidden /> New savings plan
            </Link>
          </Button>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Money saved"
          value={formatNaira(d?.savings?.totalSaved ?? "0", { decimals: false })}
          hint={`${d?.savings?.activePlans ?? 0} active plan${d?.savings?.activePlans === 1 ? "" : "s"}`}
          icon={<PiggyBank className="h-5 w-5" />}
          tone="dark"
        />
        <StatCard
          label="Next payment"
          value={d?.savings?.nextContributionDate ? formatNaira(d?.savings?.nextContributionAmount ?? "0", { decimals: false }) : "—"}
          hint={d?.savings?.nextContributionDate ? `Due ${formatDate(d.savings.nextContributionDate)}` : "Nothing due"}
          icon={<CalendarClock className="h-5 w-5" />}
          tone="gold"
        />
        <StatCard
          label="Loan balance"
          value={d?.loan ? formatNaira(d.loan.outstanding, { decimals: false }) : "No loan"}
          hint={
            d?.loan
              ? `Next repayment ${d.loan.nextRepaymentDate ? formatDate(d.loan.nextRepaymentDate) : "—"}`
              : "See what you qualify for"
          }
          icon={<Landmark className="h-5 w-5" />}
        />
        <StatCard
          label="Savings goals"
          value={String(d?.goalsCount ?? 0)}
          hint={d?.goalsCount ? "Keep going!" : "Set your first goal"}
          icon={<Target className="h-5 w-5" />}
        />
      </div>

      {d?.loan ? (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rfund-line bg-rfund-100/70 p-4">
          <div className="flex items-center gap-3">
            <StatusBadge status={d.loan.status} />
            <p className="text-sm font-bold text-rfund-900">
              Loan {d.loan.reference} — {formatNaira(d.loan.outstanding)} outstanding
            </p>
          </div>
          <Button asChild variant="outline" className="min-h-11 font-bold">
            <Link href={`/app/loans`}>
              Manage repayments <ArrowRight className="ml-1.5 h-4 w-4" aria-hidden />
            </Link>
          </Button>
        </div>
      ) : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <SectionCard
          title="Active savings plans"
          action={
            <Button asChild variant="link" className="min-h-9 px-0 font-bold text-rfund-700">
              <Link href="/app/savings">View all</Link>
            </Button>
          }
        >
          {plansQuery.loading ? (
            <LoadingState />
          ) : plans.length === 0 ? (
            <EmptyState
              title="You don't have any savings plans yet."
              description="Start your first Digital Ajo plan — it takes under a minute."
              action={
                <Button asChild className="min-h-11 bg-rfund-gold font-extrabold text-rfund-900 hover:bg-rfund-gold-dark">
                  <Link href="/app/savings">Start saving</Link>
                </Button>
              }
            />
          ) : (
            <div className="space-y-3">
              {plans.map((plan: any) => (
                <Link
                  key={plan.id}
                  href={`/app/savings/${plan.id}`}
                  className="flex items-center justify-between gap-3 rounded-lg border border-rfund-line bg-white p-3 transition hover:border-rfund-400"
                >
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-bold text-rfund-900">{plan.productName}</p>
                      <StatusBadge status={plan.status} />
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {formatNaira(plan.amount, { decimals: false })} · {titleize(plan.frequency)} ·{" "}
                      {plan.contributionsPaid}/{plan.contributionCount} paid
                    </p>
                  </div>
                  <p className="shrink-0 text-sm font-extrabold text-rfund-700">
                    {formatNaira(plan.totalContributed, { decimals: false })}
                  </p>
                </Link>
              ))}
            </div>
          )}
        </SectionCard>

        <SectionCard
          title="Recent transactions"
          action={
            <Button asChild variant="link" className="min-h-9 px-0 font-bold text-rfund-700">
              <Link href="/app/transactions">View all</Link>
            </Button>
          }
        >
          {data?.payments?.items?.length ? (
            <div className="space-y-3">
              {data.payments.items.map((payment: any) => (
                <TransactionItem
                  key={payment.id}
                  reference={payment.reference}
                  title={titleize(payment.purpose)}
                  amount={formatNaira(payment.amount, { decimals: false })}
                  status={payment.status}
                  date={formatDateTime(payment.createdAt)}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              title="No transactions yet."
              description="Your payments will appear here with full references."
            />
          )}
        </SectionCard>
      </div>
    </div>
  );
}
