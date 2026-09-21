import type { Metadata } from "next";
import PaymentsPage from "./page-view";

export const metadata: Metadata = { title: "Payments" };

export default function Page() {
  return <PaymentsPage />;
}
