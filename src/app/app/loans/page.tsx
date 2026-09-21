import type { Metadata } from "next";
import LoansPage from "./page-view";

export const metadata: Metadata = { title: "Loans" };

export default function Page() {
  return <LoansPage />;
}
