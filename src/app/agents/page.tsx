import type { Metadata } from "next";
import AgentsPage from "./page-view";

export const metadata: Metadata = {
  title: "Agent Network",
  description: "Local RFUND agents bring cash collection, payouts and onboarding to communities without bank branches.",
};

export default function Page() {
  return <AgentsPage />;
}
