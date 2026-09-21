import type { Metadata } from "next";
import AgentTransactionsPage from "./page-view";

export const metadata: Metadata = { title: "Agent transactions" };

export default function Page() {
  return <AgentTransactionsPage />;
}
