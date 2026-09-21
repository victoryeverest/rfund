import type { Metadata } from "next";
import AgentProfilePage from "./page-view";

export const metadata: Metadata = { title: "Agent profile" };

export default function Page() {
  return <AgentProfilePage />;
}
