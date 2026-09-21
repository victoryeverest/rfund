"use client";

import { PublicPage, Prose } from "@/components/rfund/public-page";
import { Card, CardContent } from "@/components/ui/card";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { HandCoins, MapPinned, ShieldCheck, Percent } from "lucide-react";

export default function AgentsPage() {
  return (
    <PublicPage
      eyebrow="Agents"
      title="A trusted neighbour, powered by RFUND."
      intro="RFUND agents are local shopkeepers and community members who collect savings, process payouts and help customers without smartphones — every transaction recorded in the same ledger as the app."
    >
      <div className="grid gap-4 sm:grid-cols-2">
        {[
          { icon: <HandCoins className="h-6 w-6" />, title: "Cash collection", body: "Agents accept cash savings contributions and issue receipt references instantly by SMS." },
          { icon: <MapPinned className="h-6 w-6" />, title: "Territory-based", body: "Each agent serves a defined territory — states, LGAs and communities they know personally." },
          { icon: <ShieldCheck className="h-6 w-6" />, title: "Device-secured", body: "Agent devices are registered and fingerprinted; compromised devices are disabled instantly." },
          { icon: <Percent className="h-6 w-6" />, title: "Commission-earning", body: "Agents earn configured commissions on transactions, paid through the ledger — never under the table." },
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
        <h2>For customers: what an agent can and cannot do</h2>
        <ul>
          <li><strong>Can:</strong> open your account, collect cash savings, process payouts, and help you apply for loans.</li>
          <li><strong>Cannot:</strong> change your balance, approve loans, or reverse transactions — those require platform staff with audited permissions.</li>
          <li><strong>Always:</strong> gives you a receipt reference for every cash transaction. If you do not get one, contact support immediately.</li>
        </ul>
        <h2>For prospective agents</h2>
        <p>
          Agents operate under transaction limits (per transaction, daily, monthly), settle
          collected funds to RFUND through a reviewed settlement workflow, and earn commissions
          per configured rules. Agent supervisors monitor activity, and unusual patterns raise
          fraud alerts for review — protecting both customers and honest agents.
        </p>
      </Prose>

      <div className="mt-10 rounded-xl bg-rfund-900 p-6 text-white sm:p-8">
        <h2 className="text-xl font-extrabold">Become an RFUND agent</h2>
        <p className="mt-2 max-w-xl text-sm text-white/80">
          Serve your community and earn commission. Tell us about your business and territory.
        </p>
        <Button asChild className="mt-4 min-h-12 bg-rfund-gold px-8 font-extrabold text-rfund-900 hover:bg-rfund-gold-dark">
          <Link href="/contact?topic=agent">Apply to become an agent</Link>
        </Button>
      </div>
    </PublicPage>
  );
}
