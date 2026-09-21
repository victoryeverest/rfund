import type { Metadata } from "next";
import AdminCustomersPage from "./page-view";

export const metadata: Metadata = { title: "Customers" };

export default function Page() {
  return <AdminCustomersPage />;
}
