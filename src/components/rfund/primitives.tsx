"use client";

/**
 * RFUND shared design system (spec §73): consistent, reusable primitives.
 * Rural-first: large touch targets, strong contrast, simple language (§137).
 */

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { AlertTriangle, RefreshCw, Inbox, WifiOff } from "lucide-react";
import { statusTone, titleize } from "@/lib/money";

export function StatusBadge({ status }: { status: string }) {
  return <Badge variant={statusTone(status)}>{titleize(status)}</Badge>;
}

export function StatCard({
  label,
  value,
  hint,
  icon,
  tone = "default",
}: {
  label: string;
  value: string;
  hint?: string;
  icon?: React.ReactNode;
  tone?: "default" | "gold" | "dark";
}) {
  return (
    <Card
      className={cn(
        "border border-rfund-line shadow-sm",
        tone === "gold" && "border-rfund-gold/60 bg-rfund-gold/10",
        tone === "dark" && "border-rfund-900 bg-rfund-900 text-white"
      )}
    >
      <CardContent className="p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p
              className={cn(
                "text-xs font-semibold uppercase tracking-wide",
                tone === "dark" ? "text-white/70" : "text-muted-foreground"
              )}
            >
              {label}
            </p>
            <p
              className={cn(
                "mt-1.5 truncate text-xl font-extrabold sm:text-2xl",
                tone === "dark" ? "text-white" : "text-rfund-900"
              )}
              title={value}
            >
              {value}
            </p>
            {hint ? (
              <p className={cn("mt-1 text-xs", tone === "dark" ? "text-white/70" : "text-muted-foreground")}>
                {hint}
              </p>
            ) : null}
          </div>
          {icon ? (
            <div
              className={cn(
                "shrink-0 rounded-lg p-2",
                tone === "dark" ? "bg-white/10 text-rfund-gold" : "bg-rfund-100 text-rfund-700"
              )}
              aria-hidden
            >
              {icon}
            </div>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-rfund-900 sm:text-3xl">
          {title}
        </h1>
        {description ? (
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground sm:text-base">
            {description}
          </p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="space-y-3" role="status" aria-live="polite">
      <p className="text-sm text-muted-foreground">{label}</p>
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-16 w-full" />
    </div>
  );
}

export function FullPageLoader({ label = "Loading RFUND…" }: { label?: string }) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-3" role="status">
      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-rfund-700 text-lg font-extrabold text-white">
        R
      </div>
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-rfund-line bg-rfund-soft/60 px-6 py-12 text-center">
      <Inbox className="h-10 w-10 text-rfund-300" aria-hidden />
      <p className="mt-3 text-base font-bold text-rfund-900">{title}</p>
      {description ? (
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  reference,
  onRetry,
}: {
  title?: string;
  message?: string;
  reference?: string;
  onRetry?: () => void;
}) {
  return (
    <div
      className="flex flex-col items-center justify-center rounded-lg border border-destructive/30 bg-destructive/5 px-6 py-10 text-center"
      role="alert"
    >
      <AlertTriangle className="h-10 w-10 text-destructive" aria-hidden />
      <p className="mt-3 text-base font-bold text-rfund-900">{title}</p>
      {message ? <p className="mt-1 max-w-md text-sm text-muted-foreground">{message}</p> : null}
      {reference ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Reference: <span className="font-mono">{reference}</span>
        </p>
      ) : null}
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        {onRetry ? (
          <Button onClick={onRetry} variant="outline" className="min-h-11">
            <RefreshCw className="mr-2 h-4 w-4" aria-hidden /> Try again
          </Button>
        ) : null}
        <Button variant="ghost" className="min-h-11" asChild>
          <a href="/app/support">Contact support</a>
        </Button>
      </div>
    </div>
  );
}

export function OfflineBanner() {
  return (
    <div
      className="flex items-center gap-2 rounded-md border border-rfund-gold/50 bg-rfund-gold/15 px-4 py-2 text-sm font-semibold text-rfund-900"
      role="status"
    >
      <WifiOff className="h-4 w-4" aria-hidden />
      You are offline. Some information may be out of date.
    </div>
  );
}

export function TransactionItem({
  reference,
  title,
  subtitle,
  amount,
  status,
  date,
  negative = false,
  onClick,
}: {
  reference: string;
  title: string;
  subtitle?: string;
  amount: string;
  status: string;
  date: string;
  negative?: boolean;
  onClick?: () => void;
}) {
  const content = (
    <>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="truncate text-sm font-bold text-rfund-900">{title}</p>
          <StatusBadge status={status} />
        </div>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {date}
          {subtitle ? ` · ${subtitle}` : ""}
        </p>
        <p className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground/80">
          {reference}
        </p>
      </div>
      <p
        className={cn(
          "shrink-0 text-sm font-extrabold",
          negative ? "text-destructive" : "text-rfund-700"
        )}
      >
        {negative ? "−" : "+"}
        {amount}
      </p>
    </>
  );
  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="flex w-full items-center gap-3 rounded-lg border border-rfund-line bg-white p-3 text-left transition hover:border-rfund-400 focus-visible:outline-2 focus-visible:outline-rfund-700"
      >
        {content}
      </button>
    );
  }
  return (
    <div className="flex items-center gap-3 rounded-lg border border-rfund-line bg-white p-3">
      {content}
    </div>
  );
}

export function SectionCard({
  title,
  action,
  children,
  className,
}: {
  title: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <Card className={cn("border border-rfund-line shadow-sm", className)}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-3">
        <CardTitle className="text-base font-bold text-rfund-900">{title}</CardTitle>
        {action}
      </CardHeader>
      <CardContent className="pt-0">{children}</CardContent>
    </Card>
  );
}
