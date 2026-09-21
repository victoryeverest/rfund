"use client";

import { AppShell } from "@/components/rfund/app-shell";

export default function CustomerAppLayout({ children }: { children: React.ReactNode }) {
  return <AppShell area="app">{children}</AppShell>;
}
