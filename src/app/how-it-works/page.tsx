import type { Metadata } from "next";
import HowItWorksPage from "./page-view";

export const metadata: Metadata = {
  title: "How It Works",
  description: "Step-by-step guides for RFUND savings, loans, payouts and agent-assisted onboarding.",
};

export default function Page() {
  return <HowItWorksPage />;
}
