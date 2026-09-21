import type { Metadata } from "next";
import LoansPage from "./page-view";

export const metadata: Metadata = {
  title: "Rural Loans",
  description: "Collateral-free business financing for traders and artisans, with transparent repayment schedules.",
};

export default function Page() {
  return <LoansPage />;
}
