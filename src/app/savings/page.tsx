"use client";

import { PublicPage, Prose } from "@/components/rfund/public-page";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { PiggyBank, CalendarCheck, Receipt, ShieldCheck } from "lucide-react";

export const metadata: Metadata = {
  title: "Digital Ajo Savings",
  description: "Digitized thrift savings with real calendar schedules, receipts and a proper ledger.",
};

export default function SavingsPage() {
  return (
    <PublicPage
      eyebrow="Savings"
      title="Digital Ajo — your thrift, digitized properly."
      intro="Traditional ajo works because it is simple and social. RFUND keeps both, and adds what paper systems can't: exact records, receipts and a ledger that never loses a naira."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {[
          {
            icon: <PiggyBank className="h-6 w-6" />,
            title: "Contribute your way",
            body: "Daily, weekly or monthly contributions from ₦100. Choose a payout term of 3 months, 6 months or a year.",
          },
          {
            icon: <CalendarCheck className="h-6 w-6" />,
            title: "Real calendar schedules",
            body: "Your plan shows every contribution date up front — computed on actual calendar months, including leap years. No guesswork.",
          },
          {
            icon: <Receipt className="h-6 w-6" />,
            title: "A receipt for everything",
            body: "Every payment gets a unique reference like RF-PAY-20260921-000001. Quote it to support and we trace it instantly.",
          },
          {
            icon: <ShieldCheck className="h-6 w-6" />,
            title: "Ledger-backed balances",
            body: "Your balance is never a number someone edited — it is the sum of balanced, double-entry ledger records.",
          },
        ].map((item) => (
          <Card key={item.title} className="border border-rfund-line">
            <CardContent className="p-5">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-rfund-100 text-rfund-700" aria-hidden>
                {item.icon}
              </div>
              <h2 className="mt-3 text-lg font-extrabold text-rfund-900">{item.title}</h2>
              <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{item.body}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Prose>
        <h2>Savings goals</h2>
        <p>
          Saving for school fees, farm inputs, business stock or a wedding? Create a goal, set a
          target amount and date, and fund it alongside your ajo plan. Your dashboard tracks
          progress with plain numbers.
        </p>
        <h2>Missing a contribution</h2>
        <p>
          Life happens. A missed due date is marked <Badge variant="warning">Missed</Badge> on
          your schedule — it never silently disappears, and you can catch up with the next
          payment. Plans only complete when all scheduled contributions are actually paid.
        </p>
        <h2>Payouts</h2>
        <p>
          Term plans pay out at the end of the tenure. Flexible savings can be withdrawn on
          request. Payout requests go through validation and finance approval before any money
          moves — that is how we protect the money you trusted us with.
        </p>
      </Prose>

      <div className="mt-10 rounded-xl bg-rfund-gold/15 p-6 sm:p-8">
        <h2 className="text-xl font-extrabold text-rfund-900">Start with ₦100</h2>
        <p className="mt-2 max-w-xl text-sm text-rfund-900/80">
          Your first contribution can be as small as ₦100. Open an account and pick your plan.
        </p>
        <Button asChild className="mt-4 min-h-12 bg-rfund-700 px-8 font-extrabold text-white hover:bg-rfund-800">
          <Link href="/signup">Open my savings account</Link>
        </Button>
      </div>
    </PublicPage>
  );
}
