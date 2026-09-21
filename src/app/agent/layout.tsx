"use client";

import { AppShell } from "@/components/rfund/app-shell";

export default function AgentLayout({ children }: { children: React.ReactNode }) {
  return <AppShell area="agent">{children}</AppShell>;
}
