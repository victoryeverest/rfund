import type { Metadata } from "next";
import AdminFraudPage from "./page-view";

export const metadata: Metadata = { title: "Fraud" };

export default function Page() {
  return <AdminFraudPage />;
}
