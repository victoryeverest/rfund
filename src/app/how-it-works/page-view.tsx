"use client";

import { PublicPage, Prose } from "@/components/rfund/public-page";
import { Card, CardContent } from "@/components/ui/card";
import Link from "next/link";
import { Button } from "@/components/ui/button";

const STEPS = [
  {
    title: "1. Open your account",
    body: "Sign up with your phone number and a password. No long forms — we collect other details only when a service needs them.",
  },
  {
    title: "2. Verify your identity",
    body: "Submit your NIN, BVN, voter's card or other ID. Verification unlocks loans and higher limits. Your documents stay private.",
  },
  {
    title: "3. Choose how to save",
    body: "Pick Digital Ajo (daily, weekly or monthly contributions with a fixed payout term) or flexible savings for any goal.",
  },
  {
    title: "4. Fund your plan",
    body: "Pay by card or bank transfer through our payment partner, or hand cash to a local RFUND agent. Every payment gets a receipt reference.",
  },
  {
    title: "5. Watch it grow",
    body: "Your dashboard shows money saved, next contribution date and full transaction history — all computed by the RFUND ledger.",
  },
  {
    title: "6. Get your payout",
    body: "At the end of your term (or on demand for flexible savings), request your payout. Approvals and payments are processed through the ledger.",
  },
];

export default function HowItWorksPage() {
  return (
    <PublicPage
      eyebrow="How it works"
      title="From phone number to first payout — in plain steps."
      intro="RFUND is designed for first-time digital finance users. Every screen uses simple language and every step has a clear outcome."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {STEPS.map((step) => (
          <Card key={step.title} className="border border-rfund-line">
            <CardContent className="p-5">
              <h2 className="text-base font-extrabold text-rfund-900">{step.title}</h2>
              <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{step.body}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Prose>
        <h2>For borrowers</h2>
        <p>
          Loan applications follow a transparent journey: choose a product, check your
          eligibility, submit business or farm details, then a loan officer reviews and makes a
          decision you can see on your dashboard. Approved offers show the exact repayment
          schedule — every installment date, principal and interest — before you accept.
        </p>
        <h2>For agent-assisted customers</h2>
        <p>
          No smartphone? A local RFUND agent can open your account, collect your cash
          contributions and process payouts. You get an SMS receipt for every transaction, and
          you can confirm your balance anytime through support.
        </p>
      </Prose>

      <div className="mt-10 rounded-xl bg-rfund-900 p-6 text-white sm:p-8">
        <h2 className="text-xl font-extrabold">Ready to start?</h2>
        <p className="mt-2 max-w-xl text-sm text-white/80">
          Opening an account takes less than two minutes — just your phone number to begin.
        </p>
        <Button asChild className="mt-4 min-h-12 bg-rfund-gold px-8 font-extrabold text-rfund-900 hover:bg-rfund-gold-dark">
          <Link href="/signup">Create your account</Link>
        </Button>
      </div>
    </PublicPage>
  );
}
