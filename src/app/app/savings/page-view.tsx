"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  PageHeader, SectionCard, LoadingState, ErrorState, EmptyState, StatusBadge,
} from "@/components/rfund/primitives";
import {
  SAVINGS_PRODUCTS_QUERY, SAVINGS_PLANS_QUERY, SAVINGS_PROJECTION_QUERY,
  CREATE_SAVINGS_PLAN_MUTATION,
} from "@/graphql/operations";
import { formatNaira, formatDate, titleize } from "@/lib/money";
import { extractErrorMessage } from "@/lib/graphql";
import { Plus, AlertCircle } from "lucide-react";

function todayISO(offsetDays = 0) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

function CreatePlanDialog({ open, onOpenChange, onCreated }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: () => void;
}) {
  const { data, loading: productsLoading } = useQuery(SAVINGS_PRODUCTS_QUERY);
  const [form, setForm] = useState({
    productCode: "",
    amount: "1000",
    frequency: "DAILY",
    startDate: todayISO(),
    endDate: todayISO(90),
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [createPlan] = useMutation(CREATE_SAVINGS_PLAN_MUTATION);
  const products = data?.savingsProducts ?? [];
  const selectedProduct = products.find((p: any) => p.code === form.productCode);

  const projection = useQuery(SAVINGS_PROJECTION_QUERY, {
    variables: {
      amount: form.amount || "0",
      frequency: form.frequency,
      startDate: form.startDate,
      endDate: form.endDate,
    },
    skip: !open,
    fetchPolicy: "no-cache",
  });

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = await createPlan({ variables: { input: form } });
      if (result.errors?.length) {
        setError(extractErrorMessage(result.errors));
        return;
      }
      onCreated();
      onOpenChange(false);
    } catch {
      setError("RFUND is not reachable right now. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const projData = projection.data?.savingsProjection;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-rfund-900">Create a savings plan</DialogTitle>
          <DialogDescription>
            Choose a product, set your contribution and pick your term. The exact schedule is
            generated on real calendar dates before you confirm.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          {error ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" aria-hidden />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          <div className="grid gap-1.5">
            <Label>Product</Label>
            <Select
              value={form.productCode}
              onValueChange={(v) => {
                const product = products.find((p: any) => p.code === v);
                setForm({
                  ...form,
                  productCode: v,
                  frequency: product?.allowedFrequencies?.[0] ?? form.frequency,
                  amount: String(product?.minContribution ?? form.amount),
                });
              }}
            >
              <SelectTrigger className="min-h-12">
                <SelectValue placeholder={productsLoading ? "Loading products…" : "Choose a product"} />
              </SelectTrigger>
              <SelectContent>
                {products.map((product: any) => (
                  <SelectItem key={product.code} value={product.code}>
                    {product.name} ({formatNaira(product.minContribution, { decimals: false })}+)
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="plan-amount">Contribution (₦)</Label>
              <Input
                id="plan-amount"
                type="number"
                min={selectedProduct ? Number(selectedProduct.minContribution) : 100}
                required
                className="min-h-12"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>How often</Label>
              <Select value={form.frequency} onValueChange={(v) => setForm({ ...form, frequency: v })}>
                <SelectTrigger className="min-h-12">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(selectedProduct?.allowedFrequencies ?? ["DAILY", "WEEKLY", "MONTHLY"]).map((f: string) => (
                    <SelectItem key={f} value={f}>{titleize(f)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="plan-start">Start date</Label>
              <Input
                id="plan-start"
                type="date"
                required
                min={todayISO()}
                className="min-h-12"
                value={form.startDate}
                onChange={(e) => setForm({ ...form, startDate: e.target.value })}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="plan-end">End date</Label>
              <Input
                id="plan-end"
                type="date"
                required
                min={form.startDate}
                className="min-h-12"
                value={form.endDate}
                onChange={(e) => setForm({ ...form, endDate: e.target.value })}
              />
            </div>
          </div>

          {projData ? (
            <div className="rounded-lg bg-rfund-900 p-4 text-white" aria-live="polite">
              <p className="text-xs font-bold uppercase tracking-wide text-white/60">Your schedule</p>
              <p className="mt-1 text-2xl font-extrabold">
                {projData.contributionCount} × {formatNaira(form.amount, { decimals: false })}
              </p>
              <p className="mt-0.5 text-sm text-white/80">
                Total {formatNaira(projData.totalAmount, { decimals: false })} · first{" "}
                {formatDate(projData.firstDue)} · last {formatDate(projData.lastDue)}
              </p>
            </div>
          ) : (
            <p className="text-xs text-muted-foreground">Schedule preview will appear here.</p>
          )}

          <Button
            type="submit"
            disabled={busy || !form.productCode}
            className="min-h-12 w-full bg-rfund-700 font-bold text-white hover:bg-rfund-800"
          >
            {busy ? "Creating…" : "Create plan"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function SavingsPage() {
  const { data, loading, error, refetch } = useQuery(SAVINGS_PLANS_QUERY, { variables: { first: 20 } });
  const [createOpen, setCreateOpen] = useState(false);
  const router = useRouter();

  return (
    <div>
      <PageHeader
        title="Savings"
        description="Your Digital Ajo plans — every contribution dated, receipted and ledgered."
        action={
          <Button onClick={() => setCreateOpen(true)} className="min-h-11 bg-rfund-700 font-bold text-white hover:bg-rfund-800">
            <Plus className="mr-1.5 h-4 w-4" aria-hidden /> New plan
          </Button>
        }
      />
      {loading && !data ? (
        <LoadingState label="Loading your plans…" />
      ) : error ? (
        <ErrorState message="We could not load your savings plans." onRetry={() => refetch()} />
      ) : data?.savingsPlans?.items?.length ? (
        <div className="grid gap-4 md:grid-cols-2">
          {data.savingsPlans.items.map((plan: any) => {
            const paid = plan.contributionsPaid;
            const total = plan.contributionCount;
            const pct = total > 0 ? Math.round((paid / total) * 100) : 0;
            return (
              <button
                key={plan.id}
                type="button"
                onClick={() => router.push(`/app/savings/${plan.id}`)}
                className="rounded-xl border border-rfund-line bg-white p-5 text-left shadow-sm transition hover:border-rfund-400 hover:shadow-md focus-visible:outline-2 focus-visible:outline-rfund-700"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-extrabold text-rfund-900">{plan.productName}</p>
                    <p className="mt-0.5 font-mono text-xs text-muted-foreground">{plan.reference}</p>
                  </div>
                  <StatusBadge status={plan.status} />
                </div>
                <div className="mt-4 flex items-end justify-between">
                  <div>
                    <p className="text-2xl font-extrabold text-rfund-900">
                      {formatNaira(plan.totalContributed, { decimals: false })}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      of {formatNaira(Number(plan.amount) * total, { decimals: false })} target
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-bold text-rfund-700">
                      {formatNaira(plan.amount, { decimals: false })} / {titleize(plan.frequency)}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {plan.nextDue ? `Next: ${formatDate(plan.nextDue.dueDate)}` : "No pending dues"}
                    </p>
                  </div>
                </div>
                <div
                  className="mt-4 h-2 overflow-hidden rounded-full bg-rfund-100"
                  role="progressbar"
                  aria-valuenow={pct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`${pct}% of contributions paid`}
                >
                  <div className="h-full rounded-full bg-rfund-500 transition-all" style={{ width: `${pct}%` }} />
                </div>
                <p className="mt-1.5 text-xs text-muted-foreground">
                  {paid} of {total} contributions paid ({pct}%)
                </p>
              </button>
            );
          })}
        </div>
      ) : (
        <EmptyState
          title="You don't have any savings plans yet."
          description="Start your first Digital Ajo plan — daily, weekly or monthly contributions with a fixed payout term."
          action={
            <Button onClick={() => setCreateOpen(true)} className="min-h-11 bg-rfund-gold font-extrabold text-rfund-900 hover:bg-rfund-gold-dark">
              Start your first plan
            </Button>
          }
        />
      )}

      <CreatePlanDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={() => refetch()}
      />
    </div>
  );
}
