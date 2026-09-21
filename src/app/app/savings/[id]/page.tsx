import type { Metadata } from "next";
import SavingsPlanDetailPage from "./page-view";

export const metadata: Metadata = { title: "Savings plan" };

export default function Page() {
  return <SavingsPlanDetailPage />;
}
