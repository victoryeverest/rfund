import type { Metadata } from "next";
import LoanDetailPage from "./page-view";

export const metadata: Metadata = { title: "Loan" };

export default function Page() {
  return <LoanDetailPage />;
}
