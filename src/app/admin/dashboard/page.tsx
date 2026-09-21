import type { Metadata } from "next";
import AdminDashboardPage from "./page-view";

export const metadata: Metadata = { title: "Admin dashboard" };

export default function Page() {
  return <AdminDashboardPage />;
}
