"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, StatusBadge, StatCard,
} from "@/components/rfund/primitives";
import {
  LOAN_PRODUCTS_QUERY, LOAN_ELIGIBILITY_QUERY, LOAN_APPLICATIONS_QUERY, LOANS_QUERY,
  APPLY_FOR_LOAN_MUTATION, ACCEPT_LOAN_OFFER_MUTATION,
} from "@/graphql/operations";
import { formatNaira, formatDate, titleize } from "@/lib/money";
import { extractErrorMessage } from "@/lib/graphql";
import { Plus, AlertCircle, CheckCircle2, XCircle } from "lucide-react";

function ApplyDialog({ open, onOpenChange, onApplied, defaultProduct }: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onApplied: () => void;
  defaultProduct?: string;
}) {
  const { data } = useQuery(LOAN_PRODUCTS_QUERY);
  const [form, setForm] = useState({
    productCode: defaultProduct ?? "",
    amount: "50000",
    termMonths: 6,
    purpose: "",
    businessName: "",
    businessType: "",
    monthlyIncome: "",
    farmState: "",
    farmLga: "",
    farmSizeHectares: "",
    crop: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [apply] = useMutation(APPLY_FOR_LOAN_MUTATION);
  const products = data?.loanProducts ?? [];
  const selected = products.find((p: any) => p.code === form.productCode);
  const isFarmerCash = form.productCode === "FARMERCASH";

  const eligibility = useQuery(LOAN_ELIGIBILITY_QUERY, {
    variables: {
      productCode: form.productCode,
      amount: form.amount || "0",
      termMonths: form.termMonths,
    },
    skip: !open || !form.productCode,
    fetchPolicy: "no-cache",
  });
  const elig = eligibility.data?.loanEligibility;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const result = await apply({ variables: { input: form } });
      if (result.errors?.length) {
        setError(extractErrorMessage(result.errors));
        return;
      }
      onApplied();
      onOpenChange(false);
    } catch {
      setError("RFUND is not reachable right now.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-rfund-900">Apply for financing</DialogTitle>
          <DialogDescription>
            Tell us about the business or farm this supports. Every field you fill makes the
            decision faster.
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
            <Label>Loan product</Label>
            <Select value={form.productCode} onValueChange={(v) => {
              const product = products.find((p: any) => p.code === v);
              setForm({ ...form, productCode: v, amount: String(product?.minAmount ?? form.amount) });
            }}>
              <SelectTrigger className="min-h-12">
                <SelectValue placeholder="Choose a product" />
              </SelectTrigger>
              <SelectContent>
                {products.map((p: any) => (
                  <SelectItem key={p.code} value={p.code}>{p.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="loan-amount">Amount needed (₦)</Label>
              <Input
                id="loan-amount"
                type="number"
                min={selected ? Number(selected.minAmount) : 1000}
                max={selected ? Number(selected.maxAmount) : undefined}
                required
                className="min-h-12"
                value={form.amount}
                onChange={(e) => setForm({ ...form, amount: e.target.value })}
              />
            </div>
            <div className="grid gap-1.5">
              <Label>Repayment term</Label>
              <Select value={String(form.termMonths)} onValueChange={(v) => setForm({ ...form, termMonths: Number(v) })}>
                <SelectTrigger className="min-h-12"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {(selected?.termValues ?? [3, 6, 12]).map((t: number) => (
                    <SelectItem key={t} value={String(t)}>{t} months</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {elig ? (
            <Alert variant={elig.eligible ? "default" : "destructive"}>
              {elig.eligible ? (
                <CheckCircle2 className="h-4 w-4 text-rfund-600" aria-hidden />
              ) : (
                <XCircle className="h-4 w-4" aria-hidden />
              )}
              <AlertDescription>
                {elig.eligible
                  ? "You meet the requirements for this product — go ahead and apply."
                  : `Before you can apply: ${elig.reasons.join(" ")}`}
              </AlertDescription>
            </Alert>
          ) : null}

          {isFarmerCash ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="farm-state">Farm state</Label>
                <Input id="farm-state" className="min-h-12" value={form.farmState}
                  onChange={(e) => setForm({ ...form, farmState: e.target.value })} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="farm-lga">Farm LGA</Label>
                <Input id="farm-lga" className="min-h-12" value={form.farmLga}
                  onChange={(e) => setForm({ ...form, farmLga: e.target.value })} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="farm-size">Farm size (hectares)</Label>
                <Input id="farm-size" type="number" step="0.1" className="min-h-12" value={form.farmSizeHectares}
                  onChange={(e) => setForm({ ...form, farmSizeHectares: e.target.value })} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="farm-crop">Main crop</Label>
                <Input id="farm-crop" placeholder="e.g. Maize" className="min-h-12" value={form.crop}
                  onChange={(e) => setForm({ ...form, crop: e.target.value })} />
              </div>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-1.5">
                <Label htmlFor="biz-name">Business name</Label>
                <Input id="biz-name" className="min-h-12" value={form.businessName}
                  onChange={(e) => setForm({ ...form, businessName: e.target.value })} />
              </div>
              <div className="grid gap-1.5">
                <Label htmlFor="biz-type">Business type</Label>
                <Input id="biz-type" placeholder="e.g. Retail trading" className="min-h-12" value={form.businessType}
                  onChange={(e) => setForm({ ...form, businessType: e.target.value })} />
              </div>
              <div className="grid gap-1.5 sm:col-span-2">
                <Label htmlFor="biz-income">Monthly income (₦, approx.)</Label>
                <Input id="biz-income" type="number" className="min-h-12" value={form.monthlyIncome}
                  onChange={(e) => setForm({ ...form, monthlyIncome: e.target.value })} />
              </div>
            </div>
          )}

          <div className="grid gap-1.5">
            <Label htmlFor="loan-purpose">What will you use it for?</Label>
            <Textarea
              id="loan-purpose"
              required
              rows={3}
              placeholder="e.g. Restock the shop before the market season"
              className="min-h-24"
              value={form.purpose}
              onChange={(e) => setForm({ ...form, purpose: e.target.value })}
            />
          </div>
          <Button type="submit" disabled={busy || !form.productCode} className="min-h-12 w-full bg-rfund-700 font-bold text-white hover:bg-rfund-800">
            {busy ? "Submitting…" : "Submit application"}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function LoansPage() {
  const appsQuery = useQuery(LOAN_APPLICATIONS_QUERY, { fetchPolicy: "cache-and-network" });
  const loansQuery = useQuery(LOANS_QUERY);
  const [applyOpen, setApplyOpen] = useState(false);
  const [acceptOffer] = useMutation(ACCEPT_LOAN_OFFER_MUTATION);

  const applications = appsQuery.data?.loanApplications?.items ?? [];
  const loans = loansQuery.data?.loans ?? [];

  const accept = async (applicationId: string) => {
    const result = await acceptOffer({ variables: { applicationId } });
    if (result.errors?.length) {
      alert(extractErrorMessage(result.errors));
      return;
    }
    await appsQuery.refetch();
  };

  if (appsQuery.loading && !appsQuery.data) return <LoadingState label="Loading your loans…" />;
  if (appsQuery.error)
    return <ErrorState message="We could not load your loans." onRetry={() => appsQuery.refetch()} />;

  return (
    <div>
      <PageHeader
        title="Loans"
        description="Applications, offers and active loans — every status is live from the platform."
        action={
          <Button onClick={() => setApplyOpen(true)} className="min-h-11 bg-rfund-700 font-bold text-white hover:bg-rfund-800">
            <Plus className="mr-1.5 h-4 w-4" aria-hidden /> Apply for a loan
          </Button>
        }
      />

      {loans.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard
            label="Active loan balance"
            value={formatNaira(loans[0]?.totalOutstanding ?? "0", { decimals: false })}
            tone="dark"
          />
          <StatCard label="Active loans" value={String(loans.length)} tone="gold" />
          <StatCard label="Next repayment" value={loans[0] ? formatDate(new Date(Date.now() + 2592000000).toISOString()) : "—"} />
        </div>
      ) : null}

      <div className="mt-6 space-y-4">
        <h2 className="text-lg font-extrabold text-rfund-900">Your applications</h2>
        {applications.length === 0 ? (
          <EmptyState
            title="No loan applications yet."
            description="Check what you qualify for — eligibility is live before you fill any form."
            action={
              <Button onClick={() => setApplyOpen(true)} className="min-h-11 bg-rfund-gold font-extrabold text-rfund-900 hover:bg-rfund-gold-dark">
                Apply now
              </Button>
            }
          />
        ) : (
          applications.map((app: any) => (
            <div key={app.id} className="rounded-xl border border-rfund-line bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-extrabold text-rfund-900">{app.productName}</p>
                    <StatusBadge status={app.state} />
                  </div>
                  <p className="mt-0.5 font-mono text-xs text-muted-foreground">{app.reference}</p>
                </div>
                <div className="text-right">
                  <p className="text-lg font-extrabold text-rfund-900">
                    {formatNaira(app.amountRequested, { decimals: false })}
                  </p>
                  <p className="text-xs text-muted-foreground">{app.termMonths} months</p>
                </div>
              </div>
              {app.purpose ? <p className="mt-2 text-sm text-muted-foreground">“{app.purpose}”</p> : null}

              {app.state === "REJECTED" && app.rejectionReason ? (
                <Alert variant="destructive" className="mt-3">
                  <AlertDescription>{app.rejectionReason}</AlertDescription>
                </Alert>
              ) : null}

              {app.assessment ? (
                <div className="mt-3">
                  <Accordion type="single" collapsible>
                    <AccordionItem value="assessment" className="border-0">
                      <AccordionTrigger className="py-2 text-sm font-bold text-rfund-700">
                        How this application was assessed (score {app.assessment.score})
                      </AccordionTrigger>
                      <AccordionContent>
                        <ul className="space-y-1.5 text-sm text-muted-foreground">
                          {app.assessment.factors.map((f: any) => (
                            <li key={f.rule} className="flex justify-between gap-4">
                              <span>{f.name}: {f.explanation}</span>
                              <span className="shrink-0 font-bold text-rfund-900">{f.score}</span>
                            </li>
                          ))}
                        </ul>
                      </AccordionContent>
                    </AccordionItem>
                  </Accordion>
                </div>
              ) : null}

              {app.offer && app.state === "OFFERED" ? (
                <div className="mt-4 rounded-lg bg-rfund-100/70 p-4">
                  <p className="text-sm font-extrabold text-rfund-900">
                    Offer: {formatNaira(app.offer.amount, { decimals: false })} over {app.offer.termMonths} months
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Interest {app.offer.interestRate}% · total repayable{" "}
                    {formatNaira(app.offer.totalRepayable, { decimals: false })} · first payment{" "}
                    {formatDate(app.offer.firstPaymentDate)}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Valid until {formatDate(app.offer.expiresOn)}
                  </p>
                  <div className="mt-3 flex gap-2">
                    <Button
                      onClick={() => accept(app.id)}
                      className="min-h-10 bg-rfund-700 font-bold text-white hover:bg-rfund-800"
                    >
                      Accept offer
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          ))
        )}
      </div>

      <ApplyDialog open={applyOpen} onOpenChange={setApplyOpen} onApplied={() => appsQuery.refetch()} />
    </div>
  );
}
