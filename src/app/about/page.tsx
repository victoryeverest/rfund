"use client";

import { PublicPage, Prose } from "@/components/rfund/public-page";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About RFUND",
  description: "Who we are, what we believe, and how RFUND serves underserved communities.",
};

export default function AboutPage() {
  return (
    <PublicPage
      eyebrow="About RFUND"
      title="Financial infrastructure built for the people banks forgot."
      intro="RFUND exists to bring structured, trustworthy financial services to rural and underserved communities across Nigeria."
    >
      <Prose>
        <h2>Our mission</h2>
        <p>
          Millions of Nigerians save daily through informal thrift collections (ajo/esusu), run
          small businesses without access to fair credit, and farm without financing for inputs.
          RFUND digitizes these proven traditions — without asking anyone to become a banker or
          learn financial jargon.
        </p>
        <p>
          We build the technology: savings plans with real calendars, a proper double-entry
          ledger behind every naira, transparent loan products, and an agent network that brings
          service to people without smartphones.
        </p>

        <h2>What we are — and what we are not</h2>
        <p>
          RFUND is a <strong>technology platform</strong>. We are not a bank and we do not hold a
          banking licence. Licensed financial partners perform regulated activities where
          required. Savings recorded on RFUND are platform records of customer contributions —
          they are not insured bank deposits unless your partner institution states otherwise.
        </p>
        <p>
          This separation is deliberate: it keeps RFUND honest about what it is, and it lets the
          platform connect to properly licensed institutions as it grows.
        </p>

        <h2>How we work</h2>
        <ul>
          <li><strong>Every naira is ledgered.</strong> No balance is ever a number someone typed — every figure derives from posted, balanced, double-entry transactions.</li>
          <li><strong>Every product is configurable.</strong> Interest rates, limits, penalties and schedules are product settings — never hard-coded promises.</li>
          <li><strong>Every action is audited.</strong> Approvals, reversals, settlements and configuration changes record who, what, when and why.</li>
          <li><strong>Every channel is equal.</strong> Web, mobile, agents and (in future) USSD all use the same backend — one source of truth.</li>
        </ul>

        <h2>Where we operate</h2>
        <p>
          RFUND launches with pilot communities in Kaduna, Kano, Oyo and Enugu states, expanding
          through cooperative societies and agent networks. If you organize a cooperative or
          serve rural communities, <a className="font-bold text-rfund-700 underline" href="/contact">talk to us</a>.
        </p>
      </Prose>
    </PublicPage>
  );
}
