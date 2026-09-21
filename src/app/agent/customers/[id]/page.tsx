import type { Metadata } from "next";
import AgentCustomerPage from "./page-view";

export const metadata: Metadata = { title: "Customer" };

export default function Page() {
  return <AgentCustomerPage />;
}
