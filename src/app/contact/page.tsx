"use client";

import { PublicPage } from "@/components/rfund/public-page";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Metadata } from "next";
import { useState } from "react";
import { Mail, MapPin, Phone } from "lucide-react";

export const metadata: Metadata = {
  title: "Contact",
  description: "Talk to the RFUND team about savings, loans, agents or cooperatives.",
};

export default function ContactPage() {
  const [submitted, setSubmitted] = useState(false);
  const [form, setForm] = useState({ name: "", phone: "", topic: "general", message: "" });

  return (
    <PublicPage
      eyebrow="Contact"
      title="Talk to a human."
      intro="Questions about savings, loans, agents or cooperatives — we answer every message."
    >
      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-4">
          {[
            { icon: <Phone className="h-5 w-5" />, title: "Call or WhatsApp", body: "+234 800 RFUND 1 (toll-free within Nigeria)" },
            { icon: <Mail className="h-5 w-5" />, title: "Email", body: "hello@rfund.example" },
            { icon: <MapPin className="h-5 w-5" />, title: "Head office", body: "Plot 14, Ahmadu Bello Way, Zaria, Kaduna State" },
          ].map((item) => (
            <div key={item.title} className="flex items-start gap-4 rounded-xl border border-rfund-line bg-white p-5">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-rfund-100 text-rfund-700" aria-hidden>
                {item.icon}
              </div>
              <div>
                <h2 className="text-base font-extrabold text-rfund-900">{item.title}</h2>
                <p className="mt-0.5 text-sm text-muted-foreground">{item.body}</p>
              </div>
            </div>
          ))}
          <div className="rounded-xl border border-rfund-line bg-rfund-soft p-5 text-sm text-muted-foreground">
            <p className="font-bold text-rfund-900">Existing customer?</p>
            <p className="mt-1">
              The fastest route is the Help section in your dashboard — tickets carry your account
              context and every transaction reference you quote.
            </p>
          </div>
        </div>

        <Card className="border border-rfund-line">
          <CardContent className="p-6">
            {submitted ? (
              <div className="py-8 text-center" role="status">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-rfund-100 text-2xl">✓</div>
                <h2 className="mt-4 text-lg font-extrabold text-rfund-900">Message received</h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Thank you {form.name || "friend"} — our team will reach out within one working day.
                </p>
              </div>
            ) : (
              <form
                className="space-y-4"
                onSubmit={(e) => {
                  e.preventDefault();
                  setSubmitted(true);
                }}
              >
                <h2 className="text-lg font-extrabold text-rfund-900">Send us a message</h2>
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="grid gap-1.5">
                    <Label htmlFor="contact-name">Your name</Label>
                    <Input
                      id="contact-name"
                      required
                      className="min-h-12"
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="contact-phone">Phone number</Label>
                    <Input
                      id="contact-phone"
                      type="tel"
                      required
                      placeholder="0803 000 0000"
                      className="min-h-12"
                      value={form.phone}
                      onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    />
                  </div>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="contact-topic">What is this about?</Label>
                  <Select value={form.topic} onValueChange={(v) => setForm({ ...form, topic: v })}>
                    <SelectTrigger id="contact-topic" className="min-h-12">
                      <SelectValue placeholder="Choose a topic" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="general">General question</SelectItem>
                      <SelectItem value="savings">Savings / Digital Ajo</SelectItem>
                      <SelectItem value="loan">Loans</SelectItem>
                      <SelectItem value="farmercash">FarmerCash</SelectItem>
                      <SelectItem value="agent">Becoming an agent</SelectItem>
                      <SelectItem value="cooperative">Registering a cooperative</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="contact-message">Your message</Label>
                  <Textarea
                    id="contact-message"
                    required
                    rows={5}
                    className="min-h-28"
                    value={form.message}
                    onChange={(e) => setForm({ ...form, message: e.target.value })}
                  />
                </div>
                <Button type="submit" className="min-h-12 w-full bg-rfund-700 font-bold text-white hover:bg-rfund-800">
                  Send message
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </PublicPage>
  );
}
