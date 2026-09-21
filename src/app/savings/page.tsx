import type { Metadata } from "next";
import SavingsPage from "./page-view";

export const metadata: Metadata = {
  title: "Digital Ajo Savings",
  description: "Digitized thrift savings with real calendar schedules, receipts and a proper ledger.",
};

export default function Page() {
  return <SavingsPage />;
}
