import type { Metadata } from "next";
import AdminLoansPage from "./page-view";

export const metadata: Metadata = { title: "Loans" };

export default function Page() {
  return <AdminLoansPage />;
}
