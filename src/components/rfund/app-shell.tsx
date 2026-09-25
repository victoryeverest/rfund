"use client";

/**
 * Authenticated application shell (spec §128–§130): role-aware navigation,
 * sticky footer behaviour, large touch targets, responsive sidebar.
 */

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { FullPageLoader } from "@/components/rfund/primitives";
import {
  LayoutDashboard, PiggyBank, Target, Landmark, Receipt, Bell, User,
  LifeBuoy, LogOut, Menu, X, Users, HandCoins, Wallet, ArrowLeftRight,
  BookOpen, Scale, CreditCard, ShieldAlert, BarChart3, ScrollText, BadgeCheck,
} from "lucide-react";

export type NavItem = { href: string; label: string; icon: React.ReactNode };

const CUSTOMER_NAV: NavItem[] = [
  { href: "/app/dashboard", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" /> },
  { href: "/app/savings", label: "Savings", icon: <PiggyBank className="h-4 w-4" /> },
  { href: "/app/goals", label: "Goals", icon: <Target className="h-4 w-4" /> },
  { href: "/app/loans", label: "Loans", icon: <Landmark className="h-4 w-4" /> },
  { href: "/app/transactions", label: "Transactions", icon: <Receipt className="h-4 w-4" /> },
  { href: "/app/payments", label: "Payments", icon: <ArrowLeftRight className="h-4 w-4" /> },
  { href: "/app/notifications", label: "Notifications", icon: <Bell className="h-4 w-4" /> },
  { href: "/app/profile", label: "Profile", icon: <User className="h-4 w-4" /> },
  { href: "/app/support", label: "Help", icon: <LifeBuoy className="h-4 w-4" /> },
];

const AGENT_NAV: NavItem[] = [
  { href: "/agent/dashboard", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" /> },
  { href: "/agent/customers", label: "Customers", icon: <Users className="h-4 w-4" /> },
  { href: "/agent/collections", label: "Collections", icon: <HandCoins className="h-4 w-4" /> },
  { href: "/agent/transactions", label: "Transactions", icon: <Receipt className="h-4 w-4" /> },
  { href: "/agent/settlements", label: "Settlements", icon: <Wallet className="h-4 w-4" /> },
  { href: "/agent/profile", label: "Profile", icon: <User className="h-4 w-4" /> },
];

const ADMIN_NAV: NavItem[] = [
  { href: "/admin/dashboard", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" /> },
  { href: "/admin/customers", label: "Customers", icon: <Users className="h-4 w-4" /> },
  { href: "/admin/kyc", label: "KYC", icon: <BadgeCheck className="h-4 w-4" /> },
  { href: "/admin/loans", label: "Loans", icon: <Landmark className="h-4 w-4" /> },
  { href: "/admin/payments", label: "Payments", icon: <CreditCard className="h-4 w-4" /> },
  { href: "/admin/ledger", label: "Ledger", icon: <BookOpen className="h-4 w-4" /> },
  { href: "/admin/reconciliation", label: "Reconciliation", icon: <Scale className="h-4 w-4" /> },
  { href: "/admin/agents", label: "Agents", icon: <Users className="h-4 w-4" /> },
  { href: "/admin/fraud", label: "Fraud", icon: <ShieldAlert className="h-4 w-4" /> },
  { href: "/admin/support", label: "Support", icon: <LifeBuoy className="h-4 w-4" /> },
  { href: "/admin/reports", label: "Reports", icon: <BarChart3 className="h-4 w-4" /> },
  { href: "/admin/audit", label: "Audit", icon: <ScrollText className="h-4 w-4" /> },
];

export function AppShell({
  area,
  children,
}: {
  area: "app" | "agent" | "admin";
  children: React.ReactNode;
}) {
  const { status, user, signOut } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const nav = area === "app" ? CUSTOMER_NAV : area === "agent" ? AGENT_NAV : ADMIN_NAV;
  const brandHref = area === "app" ? "/app/dashboard" : area === "agent" ? "/agent/dashboard" : "/admin/dashboard";
  const brandLabel = area === "app" ? "My RFUND" : area === "agent" ? "Agent" : "Admin";

  if (status === "loading") {
    return <FullPageLoader label="Checking your session…" />;
  }
  if (status === "anonymous") {
    if (typeof window !== "undefined") {
      const dest =
        area === "app" ? "/login?next=/app/dashboard" : area === "agent" ? "/login?next=/agent/dashboard" : "/login?next=/admin/dashboard";
      router.replace(dest);
    }
    return <FullPageLoader label="Redirecting to login…" />;
  }

  const handleSignOut = async () => {
    await signOut();
    router.replace("/login");
  };

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-4 py-4">
        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-rfund-700 text-white">R</span>
        <div>
          <p className="text-sm font-extrabold text-rfund-900">RFUND</p>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-rfund-gold-dark">{brandLabel}</p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-2 pb-4" aria-label={`${brandLabel} navigation`}>
        {nav.map((item) => {
          const active = pathname === item.href || (item.href !== brandHref && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              aria-current={active ? "page" : undefined}
              className={cn(
                "flex min-h-11 items-center gap-3 rounded-lg px-3 text-sm font-semibold transition",
                active
                  ? "bg-rfund-700 text-white"
                  : "text-rfund-900/80 hover:bg-rfund-100 hover:text-rfund-900"
              )}
            >
              {item.icon}
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-rfund-line p-3">
        <p className="truncate px-1 text-xs text-muted-foreground">
          {user ? `${user.firstName || user.phone}` : ""}
        </p>
        <Button
          variant="ghost"
          className="mt-1 w-full min-h-11 justify-start text-muted-foreground hover:text-destructive"
          onClick={handleSignOut}
        >
          <LogOut className="mr-2 h-4 w-4" aria-hidden /> Sign out
        </Button>
      </div>
    </div>
  );

  return (
    <div className="flex min-h-screen flex-col bg-rfund-soft/50">
      {/* Mobile top bar */}
      <div className="flex items-center justify-between border-b border-rfund-line bg-white px-4 py-3 lg:hidden">
        <Link href={brandHref} className="flex items-center gap-2 font-extrabold text-rfund-900">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-rfund-700 text-white">R</span>
          RFUND
        </Link>
        <button
          type="button"
          className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-rfund-line"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open ? (
        <div className="border-b border-rfund-line bg-white lg:hidden">{sidebar}</div>
      ) : null}

      <div className="mx-auto flex w-full max-w-7xl flex-1 gap-6 px-4 py-6 sm:px-6">
        <aside className="hidden w-60 shrink-0 rounded-xl border border-rfund-line bg-white lg:block">
          {sidebar}
        </aside>
        <main className="min-w-0 flex-1" id="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}
