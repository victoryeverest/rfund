import type { Metadata } from "next";
import AdminPaymentsPage from "./page-view";

export const metadata: Metadata = { title: "Payments" };

export default function Page() {
  return <AdminPaymentsPage />;
}
