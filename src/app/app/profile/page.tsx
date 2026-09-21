"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@apollo/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  PageHeader, LoadingState, ErrorState, SectionCard, StatusBadge,
} from "@/components/rfund/primitives";
import { ME_QUERY, UPDATE_PROFILE_MUTATION, SUBMIT_KYC_MUTATION } from "@/graphql/operations";
import { extractErrorMessage } from "@/lib/graphql";
import { formatDate, titleize } from "@/lib/money";
import { AlertCircle, ShieldCheck } from "lucide-react";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Profile" };

const STATES = ["", "Abia", "Anambra", "Bauchi", "Bayelsa", "Benue", "Borno", "Cross River", "Delta",
  "Ebonyi", "Edo", "Ekiti", "Enugu", "FCT Abuja", "Gombe", "Imo", "Jigawa", "Kaduna", "Kano",
  "Katsina", "Kebbi", "Kogi", "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun",
  "Oyo", "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara"];

export default function ProfilePage() {
  const { data, loading, error, refetch } = useQuery(ME_QUERY);
  const [form, setForm] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [updateProfile] = useMutation(UPDATE_PROFILE_MUTATION);

  useEffect(() => {
    if (data?.me) {
      const me = data.me;
      setForm({
        firstName: me.firstName ?? "",
        lastName: me.lastName ?? "",
        email: me.email ?? "",
        dateOfBirth: me.dateOfBirth ?? "",
        occupation: me.occupation ?? "",
        address: me.address ?? "",
        state: me.state ?? "",
        lga: me.lga ?? "",
        community: me.community ?? "",
        preferredLanguage: me.preferredLanguage ?? "en",
      });
    }
  }, [data]);

  if (loading && !data) return <LoadingState label="Loading your profile…" />;
  if (error) return <ErrorState message="We could not load your profile." onRetry={() => refetch()} />;

  const me = data?.me;
  const kyc = data?.kycStatus;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setSaved(false);
    setSaveError(null);
    try {
      const input: Record<string, string> = {};
      for (const [key, value] of Object.entries(form)) {
        if (value) input[key] = value;
      }
      const result = await updateProfile({ variables: { input } });
      if (result.errors?.length) {
        setSaveError(extractErrorMessage(result.errors));
        return;
      }
      setSaved(true);
      await refetch();
    } catch {
      setSaveError("RFUND is not reachable right now.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <PageHeader
        title="Profile"
        description="Your details and identity verification. We only ask for what a service needs."
      />

      <div className="mb-6 rounded-xl border border-rfund-line bg-white p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Customer reference</p>
            <p className="mt-0.5 font-mono text-lg font-bold text-rfund-900">{me?.customerReference}</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-xs font-bold uppercase tracking-wide text-muted-foreground">Identity (KYC)</p>
              <p className="mt-0.5 flex items-center gap-2 text-sm font-bold text-rfund-900">
                <StatusBadge status={kyc?.status ?? "NOT_STARTED"} /> {kyc?.level ? titleize(kyc.level) : ""}
              </p>
            </div>
            <ShieldCheck className="h-8 w-8 text-rfund-500" aria-hidden />
          </div>
        </div>
        {kyc?.failureReason ? (
          <p className="mt-3 rounded-md bg-destructive/10 p-2 text-sm text-destructive">{kyc.failureReason}</p>
        ) : null}
      </div>

      <SectionCard title="Your details">
        <form onSubmit={save} className="space-y-4">
          {saveError ? (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" aria-hidden />
              <AlertDescription>{saveError}</AlertDescription>
            </Alert>
          ) : null}
          {saved ? (
            <Alert className="border-rfund-500/40 bg-rfund-100">
              <AlertDescription className="font-semibold text-rfund-900">Profile saved.</AlertDescription>
            </Alert>
          ) : null}
          <div className="grid gap-4 sm:grid-cols-2">
            {[
              ["firstName", "First name", "text"],
              ["lastName", "Last name", "text"],
              ["email", "Email (optional)", "email"],
              ["dateOfBirth", "Date of birth", "date"],
              ["occupation", "Occupation", "text"],
            ].map(([key, label, type]) => (
              <div key={key} className="grid gap-1.5">
                <Label htmlFor={`profile-${key}`}>{label}</Label>
                <Input
                  id={`profile-${key}`}
                  type={type}
                  className="min-h-12"
                  value={form[key] ?? ""}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                />
              </div>
            ))}
            <div className="grid gap-1.5">
              <Label>State</Label>
              <Select value={form.state ?? ""} onValueChange={(v) => setForm({ ...form, state: v })}>
                <SelectTrigger className="min-h-12"><SelectValue placeholder="Select state" /></SelectTrigger>
                <SelectContent>
                  {STATES.filter(Boolean).map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="profile-lga">Local government area</Label>
              <Input id="profile-lga" className="min-h-12" value={form.lga ?? ""}
                onChange={(e) => setForm({ ...form, lga: e.target.value })} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="profile-community">Community</Label>
              <Input id="profile-community" className="min-h-12" value={form.community ?? ""}
                onChange={(e) => setForm({ ...form, community: e.target.value })} />
            </div>
            <div className="grid gap-1.5">
              <Label>Preferred language</Label>
              <Select value={form.preferredLanguage ?? "en"} onValueChange={(v) => setForm({ ...form, preferredLanguage: v })}>
                <SelectTrigger className="min-h-12"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="ha">Hausa</SelectItem>
                  <SelectItem value="yo">Yoruba</SelectItem>
                  <SelectItem value="ig">Igbo</SelectItem>
                  <SelectItem value="pcm">Nigerian Pidgin</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5 sm:col-span-2">
              <Label htmlFor="profile-address">Address</Label>
              <Input id="profile-address" className="min-h-12" value={form.address ?? ""}
                onChange={(e) => setForm({ ...form, address: e.target.value })} />
            </div>
          </div>
          <Button type="submit" disabled={busy} className="min-h-12 bg-rfund-700 font-bold text-white hover:bg-rfund-800">
            {busy ? "Saving…" : "Save changes"}
          </Button>
        </form>
      </SectionCard>
    </div>
  );
}
