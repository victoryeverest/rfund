import type { Metadata } from "next";
import AgentSettlementsPage from "./page-view";

export const metadata: Metadata = { title: "Agent settlements" };

export default function Page() {
  return <AgentSettlementsPage />;
}
