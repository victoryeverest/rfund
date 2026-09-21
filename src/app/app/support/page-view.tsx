"use client";

import { useState } from "react";
import { useMutation, useQuery } from "@apollo/client/react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  PageHeader, LoadingState, ErrorState, EmptyState, StatusBadge, SectionCard,
} from "@/components/rfund/primitives";
import { SUPPORT_TICKETS_QUERY, CREATE_TICKET_MUTATION, REPLY_TICKET_MUTATION } from "@/graphql/operations";
import { extractErrorMessage } from "@/lib/graphql";
import { formatDate, titleize } from "@/lib/money";
import { AlertCircle, LifeBuoy, Send } from "lucide-react";

const CATEGORIES = [
  ["MISSING_PAYMENT", "A payment is missing"],
  ["INCORRECT_BALANCE", "My balance looks wrong"],
  ["FAILED_LOAN", "Loan problem"],
  ["ACCOUNT_PROBLEM", "Account problem"],
  ["AGENT_COMPLAINT", "Agent complaint"],
  ["TRANSACTION_ISSUE", "Transaction issue"],
  ["OTHER", "Something else"],
];

export default function SupportPage() {
  const { data, loading, error, refetch } = useQuery(SUPPORT_TICKETS_QUERY);
  const [form, setForm] = useState({ category: "MISSING_PAYMENT", subject: "", body: "" });
  const [ticketError, setTicketError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [replying, setReplying] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState("");
  const [createTicket] = useMutation(CREATE_TICKET_MUTATION);
  const [replyTicket] = useMutation(REPLY_TICKET_MUTATION);

  const tickets = data?.supportTickets?.items ?? [];

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTicketError(null);
    setBusy(true);
    try {
      const result = await createTicket({ variables: { input: form } });
      if (result.errors?.length) {
        setTicketError(extractErrorMessage(result.errors));
        return;
      }
      setForm({ category: "MISSING_PAYMENT", subject: "", body: "" });
      await refetch();
    } catch {
      setTicketError("RFUND is not reachable right now.");
    } finally {
      setBusy(false);
    }
  };

  const sendReply = async (ticketId: string) => {
    if (!replyBody.trim()) return;
    const result = await replyTicket({ variables: { input: { ticketId, body: replyBody } } });
    if (!result.errors?.length) {
      setReplying(null);
      setReplyBody("");
      await refetch();
    }
  };

  return (
    <div>
      <PageHeader
        title="Help & Support"
        description="Report a problem and track it to resolution. Quote transaction references where you can."
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard title="Open a new ticket">
          <form onSubmit={submit} className="space-y-4">
            {ticketError ? (
              <Alert variant="destructive">
                <AlertCircle className="h-4 w-4" aria-hidden />
                <AlertDescription>{ticketError}</AlertDescription>
              </Alert>
            ) : null}
            <div className="grid gap-1.5">
              <Label>What happened?</Label>
              <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                <SelectTrigger className="min-h-12"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map(([value, label]) => (
                    <SelectItem key={value} value={value}>{label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ticket-subject">In a few words</Label>
              <Input
                id="ticket-subject"
                required
                className="min-h-12"
                placeholder="e.g. Payment on Monday not showing"
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="ticket-body">Tell us more</Label>
              <Textarea
                id="ticket-body"
                required
                rows={5}
                className="min-h-28"
                placeholder="Include references like RF-PAY-20260921-000001 if you have them."
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
              />
            </div>
            <Button type="submit" disabled={busy} className="min-h-12 w-full bg-rfund-700 font-bold text-white hover:bg-rfund-800">
              {busy ? "Sending…" : "Submit ticket"}
            </Button>
          </form>
        </SectionCard>

        <SectionCard title="Your tickets">
          {loading && !data ? (
            <LoadingState />
          ) : error ? (
            <ErrorState message="We could not load your tickets." onRetry={() => refetch()} />
          ) : tickets.length === 0 ? (
            <EmptyState
              title="No tickets yet."
              description="We hope it stays that way — but we are here when you need us."
            />
          ) : (
            <div className="space-y-3">
              {tickets.map((t: any) => (
                <div key={t.id} className="rounded-lg border border-rfund-line bg-white p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-sm font-bold text-rfund-900">{t.subject}</p>
                      <p className="mt-0.5 font-mono text-xs text-muted-foreground">{t.reference}</p>
                    </div>
                    <StatusBadge status={t.status} />
                  </div>
                  <p className="mt-1.5 text-xs text-muted-foreground">
                    {titleize(t.category)} · opened {formatDate(t.createdAt)} · {t.messageCount} message{t.messageCount === 1 ? "" : "s"}
                  </p>
                  {["OPEN", "IN_PROGRESS", "WAITING_CUSTOMER"].includes(t.status) ? (
                    replying === t.id ? (
                      <div className="mt-3 space-y-2">
                        <Textarea
                          rows={3}
                          className="min-h-20"
                          placeholder="Write your reply…"
                          value={replyBody}
                          onChange={(e) => setReplyBody(e.target.value)}
                        />
                        <div className="flex gap-2">
                          <Button size="sm" className="min-h-10 bg-rfund-700 font-bold text-white" onClick={() => sendReply(t.id)}>
                            <Send className="mr-1 h-3.5 w-3.5" aria-hidden /> Send
                          </Button>
                          <Button size="sm" variant="outline" className="min-h-10" onClick={() => { setReplying(null); setReplyBody(""); }}>
                            Cancel
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <Button size="sm" variant="outline" className="mt-2 min-h-10 font-bold" onClick={() => setReplying(t.id)}>
                        Reply
                      </Button>
                    )
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
