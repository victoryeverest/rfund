"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Progress } from "@/components/ui/progress";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, StatusBadge,
} from "@/components/rfund/primitives";
import {
  SAVINGS_GOALS_QUERY, CREATE_GOAL_MUTATION, DELETE_GOAL_MUTATION,
  MAKE_PAYMENT_MUTATION, VERIFY_PAYMENT_MUTATION,
} from "@/graphql/operations";
import { formatNaira, formatDate, titleize } from "@/lib/money";
import { extractErrorMessage } from "@/lib/graphql";
import { Plus, Target, Trash2, AlertCircle } from "lucide-react";

const GOAL_IDEAS = ["School fees", "Farm inputs", "Business stock", "Emergency fund", "Wedding", "Household"];

function CreateGoalDialog({ open, onOpenChange, onCreated }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState({
    name: "",
    targetAmount: "50000",
    targetDate: "",
    contributionFrequency: "MONTHLY",
    contributionAmount: "5000",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [createGoal] = useMutation(CREATE_GOAL_MUTATION);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = await createGoal({
        variables: {
          input: {
            name: form.name,
            targetAmount: form.targetAmount,
            targetDate: form.targetDate || null,
            contributionFrequency: form.contributionFrequency,
            contributionAmount: form.contributionAmount,
          },
        },
      });
      if (result.errors?.length) {
        setError(extractErrorMessage(result.errors));
        return;
      }
      onCreated();
      onOpenChange(false);
    } catch {
      setError("RFUND is not reachable right now.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-rfund-900">Create a savings goal</DialogTitle>
          <DialogDescription>What are you saving towards?</DialogDescription>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-4">
          {error ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" aria-hidden />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          ) : null}
          <div className="grid gap-1.5">
            <Label htmlFor="goal-name">Goal name</Label>
            <Input
              id="goal-name"
              required
              className="min-h-12"
              placeholder="e.g. School fees"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <div className="mt-1 flex flex-wrap gap-1.5">
              {GOAL_IDEAS.map((idea) => (
                <button
                  key={idea}
                  type="button"
                  onClick={() => setForm({ ...form, name: idea })}
                  className="rounded-full border border-rfund-line bg-rfund-soft px-3 py-1 text-xs font-semibold text-rfund-800 hover:border-rfund-400"
                >
                  {idea}
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="goal-target">Target amount (₦)</Label>
              <Input
                id="goal-target"
                type="number"
                min={100}
                required
                className="min-h-12"
                value={form.targetAmount}
                onChange={(e) => setForm({ ...form, targetAmount: e.target.value })}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="goal-date">Target date (optional)</Label>
              <Input
                id="goal-date"
                type="date"
                className="min-h-12"
                value={form.targetDate}
                onChange={(e) => setForm({ ...form, targetDate: e.target.value })}
              />
            </div>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label>Planned frequency</Label>
              <Select
                value={form.contributionFrequency}
                onValueChange={(v) => setForm({ ...form, contributionFrequency: v })}
              >
                <SelectTrigger className="min-h-12"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["DAILY", "WEEKLY", "MONTHLY"].map((f) => (
                    <SelectItem key={f} value={f}>{titleize(f)}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="goal-contrib">Contribution (₦)</Label>
              <Input
                id="goal-contrib"
                type="number"
                min={0}
                className="min-h-12"
                value={form.contributionAmount}
                onChange={(e) => setForm({ ...form, contributionAmount: e.target.value })}
              />
            </div>
          </div>
          <Button type="submit" disabled={busy} className="min-h-12 w-full bg-rfund-700 font-bold text-white hover:bg-rfund-800">
            {busy ? "Creating…" : "Create goal"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function GoalsPage() {
  const { data, loading, error, refetch } = useQuery(SAVINGS_GOALS_QUERY);
  const [createOpen, setCreateOpen] = useState(false);
  const [funding, setFunding] = useState<string | null>(null);
  const [fundAmount, setFundAmount] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const [fundError, setFundError] = useState<string | null>(null);
  const [makePayment] = useMutation(MAKE_PAYMENT_MUTATION);
  const [verifyPayment] = useMutation(VERIFY_PAYMENT_MUTATION);
  const [deleteGoal] = useMutation(DELETE_GOAL_MUTATION);

  const goals = data?.savingsGoals?.items ?? [];

  const fund = async (goalId: string) => {
    setFundError(null);
    setNotice(null);
    setBusyFunding(true);
    try {
      setNotice("We're processing this transaction…");
      const result = await makePayment({
        variables: {
          input: {
            purpose: "GOAL_FUNDING",
            amount: fundAmount,
            targetGoalId: goalId,
            idempotencyKey: `web-goal-${goalId}-${Date.now()}`,
          },
        },
      });
      if (result.errors?.length) {
        setFundError(extractErrorMessage(result.errors));
        setNotice(null);
        return;
      }
      const paymentId = result.data?.makePayment?.payment?.id;
      const verified = await verifyPayment({ variables: { paymentId } });
      if (verified.errors?.length) {
        setFundError(extractErrorMessage(verified.errors));
        setNotice(null);
        return;
      }
      const v = verified.data?.verifyPayment;
      if (v?.status === "SUCCESS") {
        setNotice(`Payment received. Reference ${v.reference}.`);
        setFunding(null);
        await refetch();
      } else {
        setNotice(`Still processing. Reference ${v?.reference ?? ""}.`);
        setFunding(null);
      }
    } catch {
      setFundError("RFUND is not reachable right now.");
      setNotice(null);
    } finally {
      setBusyFunding(false);
    }
  };

  const [busyFunding, setBusyFunding] = useState(false);

  return (
    <div>
      <PageHeader
        title="Savings goals"
        description="Save towards the things that matter — school fees, farm inputs, business stock."
        action={
          <Button onClick={() => setCreateOpen(true)} className="min-h-11 bg-rfund-700 font-bold text-white hover:bg-rfund-800">
            <Plus className="mr-1.5 h-4 w-4" aria-hidden /> New goal
          </Button>
        }
      />

      {notice ? (
        <Alert className="mb-4 border-rfund-gold/50 bg-rfund-gold/10">
          <AlertDescription className="font-semibold text-rfund-900">{notice}</AlertDescription>
        </Alert>
      ) : null}
      {fundError ? (
        <Alert variant="destructive" className="mb-4">
          <AlertCircle className="h-4 w-4" aria-hidden />
          <AlertDescription>{fundError}</AlertDescription>
        </Alert>
      ) : null}

      {loading && !data ? (
        <LoadingState label="Loading your goals…" />
      ) : error ? (
        <ErrorState message="We could not load your goals." onRetry={() => refetch()} />
      ) : goals.length === 0 ? (
        <EmptyState
          title="No savings goals yet."
          description="Set a target and watch your progress grow."
          action={
            <Button onClick={() => setCreateOpen(true)} className="min-h-11 bg-rfund-gold font-extrabold text-rfund-900 hover:bg-rfund-gold-dark">
              <Target className="mr-1.5 h-4 w-4" aria-hidden /> Create your first goal
            </Button>
          }
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {goals.map((goal: any) => {
            const pct = Math.round(goal.progressPct);
            return (
              <div key={goal.id} className="rounded-xl border border-rfund-line bg-white p-5 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-lg font-extrabold text-rfund-900">{goal.name}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {goal.targetDate ? `Target: ${formatDate(goal.targetDate)}` : "No target date"}
                      {Number(goal.contributionAmount) > 0
                        ? ` · ${formatNaira(goal.contributionAmount, { decimals: false })} ${titleize(goal.contributionFrequency)}`
                        : ""}
                    </p>
                  </div>
                  <StatusBadge status={goal.status} />
                </div>
                <div className="mt-4 flex items-end justify-between">
                  <p className="text-2xl font-extrabold text-rfund-900">
                    {formatNaira(goal.currentAmount, { decimals: false })}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    of {formatNaira(goal.targetAmount, { decimals: false })}
                  </p>
                </div>
                <Progress className="mt-3 h-2" value={pct} aria-label={`${pct}% funded`} />
                <p className="mt-1.5 text-xs font-semibold text-rfund-700">{pct}% funded</p>
                <div className="mt-4 flex gap-2">
                  {goal.status === "ACTIVE" ? (
                    <Button
                      size="sm"
                      className="min-h-10 bg-rfund-700 font-bold text-white hover:bg-rfund-800"
                      onClick={() => {
                        setFunding(goal.id);
                        setFundAmount(String(goal.contributionAmount || 1000));
                      }}
                    >
                      Add money
                    </Button>
                  ) : null}
                  {Number(goal.currentAmount) === 0 && goal.status === "ACTIVE" ? (
                    <Button
                      size="sm"
                      variant="outline"
                      className="min-h-10 border-destructive/40 font-bold text-destructive hover:bg-destructive/10"
                      onClick={async () => {
                        const result = await deleteGoal({ variables: { goalId: goal.id } });
                        if (!result.errors?.length) await refetch();
                      }}
                    >
                      <Trash2 className="mr-1 h-3.5 w-3.5" aria-hidden /> Remove
                    </Button>
                  ) : null}
                </div>
                {funding === goal.id ? (
                  <div className="mt-4 flex gap-2 rounded-lg bg-rfund-soft p-3">
                    <Input
                      type="number"
                      min={100}
                      className="min-h-11"
                      value={fundAmount}
                      onChange={(e) => setFundAmount(e.target.value)}
                      aria-label="Amount to add"
                    />
                    <Button
                      disabled={busyFunding || !fundAmount}
                      onClick={() => fund(goal.id)}
                      className="min-h-11 bg-rfund-gold font-extrabold text-rfund-900 hover:bg-rfund-gold-dark"
                    >
                      {busyFunding ? "…" : "Pay"}
                    </Button>
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}

      <CreateGoalDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={() => refetch()} />
    </div>
  );
}
