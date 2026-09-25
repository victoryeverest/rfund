import type { Metadata } from "next";
import AdminReportsPage from "./page-view";

export const metadata: Metadata = { title: "Reports" };

export default function Page() {
  return <AdminReportsPage />;
}
