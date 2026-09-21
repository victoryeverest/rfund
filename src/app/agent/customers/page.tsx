import type { Metadata } from "next";
import AgentCustomersPage from "./page-view";

export const metadata: Metadata = { title: "Agent customers" };

export default function Page() {
  return <AgentCustomersPage />;
}
