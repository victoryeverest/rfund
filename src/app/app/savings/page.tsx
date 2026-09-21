import type { Metadata } from "next";
import SavingsPage from "./page-view";

export const metadata: Metadata = { title: "Savings" };

export default function Page() {
  return <SavingsPage />;
}
