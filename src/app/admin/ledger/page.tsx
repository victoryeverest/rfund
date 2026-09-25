import type { Metadata } from "next";
import AdminLedgerPage from "./page-view";

export const metadata: Metadata = { title: "Ledger" };

export default function Page() {
  return <AdminLedgerPage />;
}
