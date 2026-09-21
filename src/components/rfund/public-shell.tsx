"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Menu, X, LogIn } from "lucide-react";

const NAV = [
  { href: "/how-it-works", label: "How It Works" },
  { href: "/savings", label: "Savings" },
  { href: "/loans", label: "Loans" },
  { href: "/farmercash", label: "FarmerCash" },
  { href: "/agents", label: "Agents" },
  { href: "/cooperatives", label: "Cooperatives" },
  { href: "/about", label: "About" },
  { href: "/contact", label: "Contact" },
];

export function PublicHeader() {
  const { status } = useAuth();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-rfund-line bg-white/95 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-extrabold text-rfund-900" aria-label="RFUND home">
          <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-rfund-700 text-white">R</span>
          <span className="text-lg">RFUND</span>
        </Link>

        <nav className="hidden items-center gap-5 lg:flex" aria-label="Main navigation">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-sm font-semibold text-muted-foreground transition hover:text-rfund-700"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-2 lg:flex">
          {status === "authenticated" ? (
            <Button asChild className="bg-rfund-gold font-extrabold text-rfund-900 hover:bg-rfund-gold-dark">
              <Link href="/app/dashboard">My RFUND</Link>
            </Button>
          ) : (
            <>
              <Button asChild variant="outline" className="min-h-11 border-rfund-700 font-bold text-rfund-900">
                <Link href="/login">
                  <LogIn className="mr-1 h-4 w-4" aria-hidden /> Login
                </Link>
              </Button>
              <Button asChild className="min-h-11 bg-rfund-gold font-extrabold text-rfund-900 hover:bg-rfund-gold-dark">
                <Link href="/signup">Get started</Link>
              </Button>
            </>
          )}
        </div>

        <button
          type="button"
          className="inline-flex h-11 w-11 items-center justify-center rounded-lg border border-rfund-line lg:hidden"
          aria-expanded={open}
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open ? (
        <nav className="border-t border-rfund-line bg-white px-4 pb-4 lg:hidden" aria-label="Mobile navigation">
          <div className="flex flex-col gap-1 pt-2">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-3 py-3 text-sm font-semibold text-rfund-900 hover:bg-rfund-100"
              >
                {item.label}
              </Link>
            ))}
            <div className="mt-2 flex gap-2">
              {status === "authenticated" ? (
                <Button asChild className="flex-1 bg-rfund-gold font-extrabold text-rfund-900 hover:bg-rfund-gold-dark">
                  <Link href="/app/dashboard">My RFUND</Link>
                </Button>
              ) : (
                <>
                  <Button asChild variant="outline" className="min-h-11 flex-1 border-rfund-700 font-bold">
                    <Link href="/login">Login</Link>
                  </Button>
                  <Button asChild className="min-h-11 flex-1 bg-rfund-gold font-extrabold text-rfund-900 hover:bg-rfund-gold-dark">
                    <Link href="/signup">Get started</Link>
                  </Button>
                </>
              )}
            </div>
          </div>
        </nav>
      ) : null}
    </header>
  );
}

export function PublicFooter() {
  return (
    <footer className="bg-rfund-900 text-white/85">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:grid-cols-2 sm:px-6 lg:grid-cols-4">
        <div>
          <div className="flex items-center gap-2 font-extrabold text-white">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-rfund-gold text-rfund-900">R</span>
            RFUND
          </div>
          <p className="mt-3 text-sm text-white/70">
            Digital financial infrastructure for underserved communities.
            Save. Build. Grow.
          </p>
        </div>
        <div>
          <p className="text-sm font-bold uppercase tracking-wide text-rfund-gold">Products</p>
          <ul className="mt-3 space-y-2 text-sm">
            <li><Link href="/savings" className="hover:text-white">Digital Ajo savings</Link></li>
            <li><Link href="/loans" className="hover:text-white">Rural loans</Link></li>
            <li><Link href="/farmercash" className="hover:text-white">FarmerCash</Link></li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-bold uppercase tracking-wide text-rfund-gold">Access</p>
          <ul className="mt-3 space-y-2 text-sm">
            <li><Link href="/agents" className="hover:text-white">Agent network</Link></li>
            <li><Link href="/cooperatives" className="hover:text-white">Cooperatives</Link></li>
            <li>USSD — coming with our partner network</li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-bold uppercase tracking-wide text-rfund-gold">Company</p>
          <ul className="mt-3 space-y-2 text-sm">
            <li><Link href="/about" className="hover:text-white">About RFUND</Link></li>
            <li><Link href="/how-it-works" className="hover:text-white">How it works</Link></li>
            <li><Link href="/contact" className="hover:text-white">Contact</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-white/10 px-4 py-4 text-center text-xs text-white/60">
        RFUND provides technology infrastructure. Financial services are delivered with licensed partners.
        Savings balances are not bank deposits unless stated by your partner institution.
      </div>
    </footer>
  );
}
