"use client";

import { PublicPage, Prose } from "@/components/rfund/public-page";
import { Card, CardContent } from "@/components/ui/card";
import type { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Sprout, MapPin, CalendarDays, Package } from "lucide-react";

export const metadata: Metadata = {
  title: "FarmerCash",
  description: "Seasonal, collateral-free financing for smallholder farmers — from land preparation to harvest.",
};

const INPUTS = [
  "Seeds", "Fertilizer", "Labour", "Transport", "Storage", "Irrigation", "Agrochemicals",
];

export default function FarmerCashPage() {
  return (
    <PublicPage
      eyebrow="FarmerCash"
      title="Farm financing that follows the season — not the calendar."
      intro="FarmerCash provides collateral-free seasonal loans for smallholder farmers, verified through field visits and cooperative membership, with repayment timed to your harvest."
    >
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { icon: <Sprout className="h-6 w-6" />, title: "Season-based", body: "Applications capture your farm, crop, season, expected yield and harvest date." },
          { icon: <MapPin className="h-6 w-6" />, title: "Field-verified", body: "Field officers visit the farm, verify location and crops, and document what they see." },
          { icon: <CalendarDays className="h-6 w-6" />, title: "Harvest-timed", body: "Repayment schedules are built around your expected harvest date, not arbitrary months." },
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
        <h2>What FarmerCash covers</h2>
        <p>Every part of the production cycle that needs money before harvest:</p>
      </Prose>
      <div className="mt-4 flex flex-wrap gap-2">
        {INPUTS.map((input) => (
          <span key={input} className="rounded-full border border-rfund-line bg-rfund-soft px-4 py-2 text-sm font-semibold text-rfund-800">
            <Package className="mr-1.5 inline h-3.5 w-3.5" aria-hidden />
            {input}
          </span>
        ))}
      </div>

      <Prose>
        <h2>Verification you can trust — and that trusts you</h2>
        <p>
          A field officer visits your farm with the RFUND app: GPS location, farm size, the crop
          in the ground, photos for the file. Cooperative membership strengthens your
          application. The risk assessment shows every factor it used — no black boxes.
        </p>
        <h2>In-kind support (where available)</h2>
        <p>
          In some programs, instead of cash, approved financing pays an input supplier directly —
          seeds and fertilizer go straight to your farm. This keeps financing tied to production
          and reduces what can be diverted.
        </p>
        <h2>Cooperative advantage</h2>
        <p>
          Farmers who belong to a cooperative get stronger assessments and group verification.
          Ask your cooperative leader about joining RFUND as a group.
        </p>
      </Prose>

      <div className="mt-10 rounded-xl bg-rfund-gold/15 p-6 sm:p-8">
        <h2 className="text-xl font-extrabold text-rfund-900">Prepare for next season</h2>
        <p className="mt-2 max-w-xl text-sm text-rfund-900/80">
          Open an account, verify your identity, and apply when your season planning starts.
        </p>
        <Button asChild className="mt-4 min-h-12 bg-rfund-700 px-8 font-extrabold text-white hover:bg-rfund-800">
          <Link href="/signup">Apply for FarmerCash</Link>
        </Button>
      </div>
    </PublicPage>
  );
}
