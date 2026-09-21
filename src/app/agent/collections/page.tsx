import type { Metadata } from "next";
import AgentCollectionsPage from "./page-view";

export const metadata: Metadata = { title: "Agent collections" };

export default function Page() {
  return <AgentCollectionsPage />;
}
