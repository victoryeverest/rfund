import type { Metadata } from "next";
import AdminReconciliationPage from "./page-view";

export const metadata: Metadata = { title: "Reconciliation" };

export default function Page() {
  return <AdminReconciliationPage />;
}
