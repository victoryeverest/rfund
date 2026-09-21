"use client";

/**
 * Shared marketing page layout for public content pages.
 */

import { PublicHeader, PublicFooter } from "@/components/rfund/public-shell";

export function PublicPage({
  eyebrow,
  title,
  intro,
  children,
}: {
  eyebrow: string;
  title: string;
  intro?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <PublicHeader />
      <main className="flex-1">
        <section className="bg-rfund-900 py-12 text-white sm:py-16">
          <div className="mx-auto max-w-4xl px-4 sm:px-6">
            <p className="text-xs font-extrabold uppercase tracking-widest text-rfund-gold">{eyebrow}</p>
            <h1 className="mt-3 text-3xl font-extrabold leading-tight sm:text-4xl">{title}</h1>
            {intro ? <p className="mt-4 max-w-2xl text-lg text-white/85">{intro}</p> : null}
          </div>
        </section>
        <div className="mx-auto max-w-4xl px-4 py-10 sm:px-6 sm:py-14">{children}</div>
      </main>
      <PublicFooter />
    </div>
  );
}

export function Prose({ children }: { children: React.ReactNode }) {
  return (
    <div className="space-y-5 text-base leading-relaxed text-muted-foreground [&_h2]:mt-10 [&_h2]:text-xl [&_h2]:font-extrabold [&_h2]:text-rfund-900 [&_h3]:mt-6 [&_h3]:text-lg [&_h3]:font-bold [&_h3]:text-rfund-900 [&_strong]:text-rfund-900 [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-6">
      {children}
    </div>
  );
}
