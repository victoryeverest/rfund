"use client";

import { PublicPage, Prose } from "@/components/rfund/public-page";
import { Card, CardContent } from "@/components/ui/card";
import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Users, FileCheck, TrendingUp, ShieldCheck } from "lucide-react";

export const metadata: Metadata = {
  title: "Cooperatives",
  description: "RFUND gives cooperative societies digital records, transparent ledgers and stronger loan assessments for members.",
};

export default function CooperativesPage() {
  return (
    <PublicPage
      eyebrow="Cooperatives"
      title="Your society, on a proper ledger."
      intro="Cooperative societies have kept communities saving and borrowing for decades. RFUND digitizes the records — member registers, contributions, and member loans — without changing how the society governs itself."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { icon: <Users className="h-6 w-6" />, title: "Member registers", body: "Members, leaders (president, treasurer, secretary), meeting places — all recorded." },
          { icon: <FileCheck className="h-6 w-6" />, title: "Registration details", body: "Society registration numbers and structure stored for verification and reporting." },
          { icon: <TrendingUp className="h-6 w-6" />, title: "Stronger assessments", body: "Members of registered cooperatives score better in loan risk assessments — fairly and transparently." },
          { icon: <ShieldCheck className="h-6 w-6" />, title: "One money system", body: "Cooperative savings and loans run on the same RFUND ledger as everything else. No parallel books." },
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
        <h2>How onboarding works</h2>
        <p>
          A cooperative registers on RFUND with its official details. The society's admin invites
          members, who each hold their own RFUND customer profile linked to the cooperative.
          Savings plans, loan applications and repayments can reference the cooperative, giving
          officers visibility (with permission) into group activity.
        </p>
        <h2>Why it matters</h2>
        <p>
          Digitized records mean fewer disputes, cleaner handovers when leaders change, and
          reports your members can trust. And when the cooperative needs institutional funding,
          its contribution history is already structured evidence.
        </p>
      </Prose>

      <div className="mt-10 rounded-xl bg-rfund-gold/15 p-6 sm:p-8">
        <h2 className="text-xl font-extrabold text-rfund-900">Register your society</h2>
        <p className="mt-2 max-w-xl text-sm text-rfund-900/80">
          Tell us about your cooperative and we will get you set up with member onboarding.
        </p>
        <Button asChild className="mt-4 min-h-12 bg-rfund-700 px-8 font-extrabold text-white hover:bg-rfund-800">
          <Link href="/contact?topic=cooperative">Register your cooperative</Link>
        </Button>
      </div>
    </PublicPage>
  );
}
