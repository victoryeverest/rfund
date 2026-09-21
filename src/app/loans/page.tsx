"use client";

import { PublicPage, Prose } from "@/components/rfund/public-page";
import { Card, CardContent } from "@/components/ui/card";
import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Store, Hammer, CheckCircle2 } from "lucide-react";

export const metadata: Metadata = {
  title: "Rural Loans",
  description: "Collateral-free business financing for traders and artisans, with transparent repayment schedules.",
};

export default function LoansPage() {
  return (
    <PublicPage
      eyebrow="Rural loans"
      title="Financing that respects your hustle."
      intro="Small, responsible loans for income-generating work — with the full repayment schedule shown before you accept a single naira."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {[
          {
            icon: <Store className="h-6 w-6" />,
            title: "Trader Loan",
            body: "Restock your shop before market season, buy inventory in bulk, or cover working capital while sales cycle.",
            points: ["For market traders and provision sellers", "Inventory, stock and shop needs", "Repayment matched to your trade cycle"],
          },
          {
            icon: <Hammer className="h-6 w-6" />,
            title: "Artisan Loan",
            body: "Buy the tools, equipment or raw materials that turn your skill into steadier income.",
            points: ["For tailors, welders, carpenters, food processors", "Tools and equipment financing", "Fixed, predictable installments"],
          },
        ].map((item) => (
          <Card key={item.title} className="border border-rfund-line">
            <CardContent className="p-6">
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-rfund-100 text-rfund-700" aria-hidden>
                {item.icon}
              </div>
              <h2 className="mt-4 text-xl font-extrabold text-rfund-900">{item.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{item.body}</p>
              <ul className="mt-4 space-y-2 text-sm text-muted-foreground">
                {item.points.map((point) => (
                  <li key={point} className="flex gap-2">
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-rfund-500" aria-hidden />
                    {point}
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        ))}
      </div>

      <Prose>
        <h2>How decisions are made</h2>
        <p>
          RFUND does not judge you by a credit bureau file you were never part of. Our assessment
          engine looks at what you actually do: your savings consistency, repayment history,
          cooperative membership and verified identity. Every decision is explainable — you can
          see the factors that influenced it.
        </p>
        <h2>What you see before accepting</h2>
        <ul>
          <li>The exact approved amount and term.</li>
          <li>Every installment date with principal and interest broken down.</li>
          <li>The total you will repay — no hidden charges.</li>
        </ul>
        <h2>If repayment falls behind</h2>
        <p>
          Late installments attract a fixed penalty after a grace period, and our team reaches
          out early to restructure before things get hard. We would rather re-plan a loan than
          punish a borrower.
        </p>
        <h2>Responsible lending</h2>
        <p>
          Loan limits, interest rates and penalty rules are product configurations — published
          and versioned. RFUND staff cannot invent a rate for you at the counter, and every
          approval is recorded with its reason and approver.
        </p>
      </Prose>

      <div className="mt-10 rounded-xl bg-rfund-900 p-6 text-white sm:p-8">
        <h2 className="text-xl font-extrabold">Check your eligibility</h2>
        <p className="mt-2 max-w-xl text-sm text-white/80">
          Sign up, verify your identity, and see live eligibility for every loan product on your
          dashboard — before you fill any long form.
        </p>
        <Button asChild className="mt-4 min-h-12 bg-rfund-gold px-8 font-extrabold text-rfund-900 hover:bg-rfund-gold-dark">
          <Link href="/signup">See what I qualify for</Link>
        </Button>
      </div>
    </PublicPage>
  );
}
