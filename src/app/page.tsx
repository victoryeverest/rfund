"use client";

import Link from "next/link";
import { useQuery } from "@apollo/client/react";
import { PublicHeader, PublicFooter } from "@/components/rfund/public-shell";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { SAVINGS_PROJECTION_QUERY } from "@/graphql/operations";
import { formatNaira, formatDate } from "@/lib/money";
import { PiggyBank, Landmark, Sprout, Users, Smartphone, ShieldCheck } from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useEffect, useState } from "react";

const PRODUCTS = [
  {
    icon: <PiggyBank className="h-6 w-6" />,
    title: "Digital Ajo",
    description:
      "A modern version of traditional thrift savings. Contribute daily, weekly or monthly and receive your payout at the end of your term.",
    points: ["Daily, weekly or monthly contributions", "Quarterly, bi-yearly or yearly payout tenure", "Every payment gets a receipt reference"],
    href: "/savings",
  },
  {
    icon: <Landmark className="h-6 w-6" />,
    title: "Rural Loans",
    description:
      "Responsible, collateral-free financing for village shops, tailoring, food processing and petty trading businesses.",
    points: ["Simple loan application", "Business-purpose review", "Repayment plans matched to income"],
    href: "/loans",
  },
  {
    icon: <Sprout className="h-6 w-6" />,
    title: "FarmerCash",
    description:
      "Seasonal financing for smallholder farmers covering seeds, fertilizer, labour, transport and storage until harvest.",
    points: ["Farm-cycle repayment options", "Cooperative and agent verification", "Production-focused support"],
    href: "/farmercash",
  },
];

function SavingsCalculator() {
  const [amount, setAmount] = useState(1000);
  const [frequency, setFrequency] = useState("DAILY");
  const [tenure, setTenure] = useState("QUARTERLY");
  const [projection, setProjection] = useState<{
    contributionCount: number;
    totalAmount: string;
    firstDue: string;
    lastDue: string;
  } | null>(null);
  const [loading, setLoading] = useState(false);

  const { refetch } = useQuery(SAVINGS_PROJECTION_QUERY, {
    skip: true,
    fetchPolicy: "no-cache",
  });

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      setLoading(true);
      try {
        const start = new Date();
        const end = new Date();
        if (tenure === "QUARTERLY") end.setMonth(end.getMonth() + 3);
        else if (tenure === "BIYEARLY") end.setMonth(end.getMonth() + 6);
        else end.setFullYear(end.getFullYear() + 1);
        const result = await refetch({
          amount: String(amount),
          frequency,
          startDate: start.toISOString().slice(0, 10),
          endDate: end.toISOString().slice(0, 10),
        });
        if (!cancelled && !result.errors?.length) {
          setProjection(result.data.savingsProjection);
        }
      } catch {
        // Network problems must not break the page (§78)
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    const timer = setTimeout(run, 400);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [amount, frequency, tenure, refetch]);

  return (
    <Card className="border border-rfund-line shadow-lg">
      <CardContent className="p-5 sm:p-7">
        <p className="text-xs font-extrabold uppercase tracking-wide text-rfund-gold-dark">
          Savings planner
        </p>
        <h2 className="mt-1 text-xl font-extrabold text-rfund-900 sm:text-2xl">
          Plan your Digital Ajo contribution
        </h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <label className="grid gap-1.5 text-sm font-bold text-rfund-900">
            Contribution amount (₦)
            <input
              type="number"
              min={100}
              step={100}
              value={amount}
              onChange={(e) => setAmount(Math.max(0, Number(e.target.value)))}
              className="min-h-12 rounded-lg border border-rfund-line bg-white px-3 text-base font-normal text-foreground focus-visible:outline-2 focus-visible:outline-rfund-700"
            />
          </label>
          <label className="grid gap-1.5 text-sm font-bold text-rfund-900">
            How often?
            <select
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              className="min-h-12 rounded-lg border border-rfund-line bg-white px-3 text-base font-normal text-foreground focus-visible:outline-2 focus-visible:outline-rfund-700"
            >
              <option value="DAILY">Every day</option>
              <option value="WEEKLY">Every week</option>
              <option value="MONTHLY">Every month</option>
            </select>
          </label>
          <label className="grid gap-1.5 text-sm font-bold text-rfund-900">
            Payout tenure
            <select
              value={tenure}
              onChange={(e) => setTenure(e.target.value)}
              className="min-h-12 rounded-lg border border-rfund-line bg-white px-3 text-base font-normal text-foreground focus-visible:outline-2 focus-visible:outline-rfund-700"
            >
              <option value="QUARTERLY">Every 3 months</option>
              <option value="BIYEARLY">Every 6 months</option>
              <option value="YEARLY">Every year</option>
            </select>
          </label>
        </div>
        <div className="mt-5 rounded-xl bg-rfund-900 p-5 text-white" aria-live="polite">
          <p className="text-xs font-bold uppercase tracking-wide text-white/60">
            Estimated payout at term
          </p>
          <p className="mt-1 text-3xl font-extrabold sm:text-4xl">
            {loading ? "Calculating…" : formatNaira(projection?.totalAmount ?? "0", { decimals: false })}
          </p>
          <p className="mt-1 text-sm text-white/75">
            {projection
              ? `${projection.contributionCount} contributions · first ${formatDate(projection.firstDue)} · last ${formatDate(projection.lastDue)}`
              : "Based on real calendar dates — not estimates."}
          </p>
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Projections are calculated on the RFUND server using actual calendar dates. Your savings
          balance is always recorded by the platform ledger.
        </p>
        <Button
          asChild
          className="mt-4 w-full min-h-12 bg-rfund-gold text-base font-extrabold text-rfund-900 hover:bg-rfund-gold-dark sm:w-auto sm:px-8"
        >
          <Link href="/signup">Start saving today</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

export default function HomePage() {
  const { status } = useAuth();
  return (
    <div className="flex min-h-screen flex-col">
      <PublicHeader />
      <main className="flex-1">
        {/* Hero */}
        <section className="relative overflow-hidden bg-rfund-900 text-white">
          <div
            className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,rgba(47,138,99,0.35),transparent_55%)]"
            aria-hidden
          />
          <div className="relative mx-auto grid max-w-7xl gap-10 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:py-24">
            <div className="rfund-fade-up">
              <p className="text-xs font-extrabold uppercase tracking-widest text-rfund-gold">
                Rural business financing platform
              </p>
              <h1 className="mt-3 text-4xl font-extrabold leading-tight sm:text-5xl lg:text-6xl">
                Save. Build. Grow.
              </h1>
              <p className="mt-4 max-w-xl text-lg text-white/85">
                Digital savings, small business loans and farmer cash support for rural traders,
                artisans, cooperatives and smallholder farmers.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                {status === "authenticated" ? (
                  <Button asChild size="lg" className="min-h-12 bg-rfund-gold px-8 text-base font-extrabold text-rfund-900 hover:bg-rfund-gold-dark">
                    <Link href="/app/dashboard">Open my dashboard</Link>
                  </Button>
                ) : (
                  <>
                    <Button asChild size="lg" className="min-h-12 bg-rfund-gold px-8 text-base font-extrabold text-rfund-900 hover:bg-rfund-gold-dark">
                      <Link href="/signup">Start saving</Link>
                    </Button>
                    <Button asChild size="lg" variant="outline" className="min-h-12 border-white/60 px-8 text-base font-bold text-white hover:bg-white/10">
                      <Link href="/how-it-works">How it works</Link>
                    </Button>
                  </>
                )}
              </div>
              <dl className="mt-10 grid max-w-lg grid-cols-3 gap-3" aria-label="Platform highlights">
                {[
                  ["Daily", "thrift collection"],
                  ["Agents", "local support"],
                  ["Secure", "verified payments"],
                ].map(([term, def]) => (
                  <div key={term} className="rounded-lg border border-white/20 bg-white/10 p-3">
                    <dt className="text-lg font-extrabold">{term}</dt>
                    <dd className="mt-0.5 text-xs text-white/75">{def}</dd>
                  </div>
                ))}
              </dl>
            </div>
            <div className="rfund-fade-up self-center">
              <SavingsCalculator />
            </div>
          </div>
        </section>

        {/* Intro */}
        <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <div>
              <p className="text-xs font-extrabold uppercase tracking-widest text-rfund-gold-dark">
                Built for rural finance
              </p>
              <h2 className="mt-2 text-2xl font-extrabold text-rfund-900 sm:text-4xl">
                Simple enough for daily use. Structured enough for real growth.
              </h2>
            </div>
            <p className="text-base leading-relaxed text-muted-foreground">
              RFUND helps people save daily, weekly or monthly, then withdraw at the end of a
              quarterly, bi-yearly or yearly tenure. It also gives rural entrepreneurs and
              smallholder farmers a clear path to apply for responsible, collateral-free
              financing — with every naira recorded in a proper double-entry ledger.
            </p>
          </div>
        </section>

        {/* Products */}
        <section className="bg-rfund-soft py-14" aria-label="RFUND services">
          <div className="mx-auto max-w-7xl px-4 sm:px-6">
            <div className="grid gap-5 md:grid-cols-3">
              {PRODUCTS.map((product) => (
                <Card key={product.title} className="border border-rfund-line shadow-sm transition hover:shadow-md">
                  <CardContent className="p-6">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-rfund-100 text-rfund-700" aria-hidden>
                      {product.icon}
                    </div>
                    <h3 className="mt-4 text-xl font-extrabold text-rfund-900">{product.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                      {product.description}
                    </p>
                    <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                      {product.points.map((point) => (
                        <li key={point} className="flex gap-2">
                          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-rfund-500" aria-hidden />
                          {point}
                        </li>
                      ))}
                    </ul>
                    <Button asChild variant="link" className="mt-4 min-h-11 px-0 font-bold text-rfund-700">
                      <Link href={product.href}>Learn more →</Link>
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        </section>

        {/* Access channels */}
        <section className="mx-auto max-w-7xl px-4 py-14 sm:px-6">
          <p className="text-xs font-extrabold uppercase tracking-widest text-rfund-gold-dark">
            Many ways to reach us
          </p>
          <h2 className="mt-2 text-2xl font-extrabold text-rfund-900 sm:text-3xl">
            Works with or without a smartphone.
          </h2>
          <div className="mt-8 grid gap-5 sm:grid-cols-3">
            {[
              { icon: <Smartphone className="h-6 w-6" />, title: "Web & mobile browser", text: "Use RFUND on any phone browser — built to work on low-bandwidth connections and inexpensive Android devices." },
              { icon: <Users className="h-6 w-6" />, title: "Agent network", text: "Local agents collect savings in cash and help customers without smartphones open accounts and receive payouts." },
              { icon: <ShieldCheck className="h-6 w-6" />, title: "Verified payments", text: "Payments are verified server-side before anything is recorded. Every transaction carries a receipt reference you can quote to support." },
            ].map((item) => (
              <div key={item.title} className="rounded-xl border border-rfund-line bg-white p-6">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-rfund-100 text-rfund-700" aria-hidden>
                  {item.icon}
                </div>
                <h3 className="mt-4 text-lg font-extrabold text-rfund-900">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{item.text}</p>
              </div>
            ))}
          </div>
        </section>
      </main>
      <PublicFooter />
    </div>
  );
}
