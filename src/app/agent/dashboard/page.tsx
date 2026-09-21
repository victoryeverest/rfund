import type { Metadata } from "next";
import AgentDashboardPage from "./page-view";

export const metadata: Metadata = { title: "Agent dashboard" };

export default function Page() {
  return <AgentDashboardPage />;
}
