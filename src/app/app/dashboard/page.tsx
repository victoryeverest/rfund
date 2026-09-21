import type { Metadata } from "next";
import CustomerDashboard from "./page-view";

export const metadata: Metadata = { title: "Dashboard" };

export default function Page() {
  return <CustomerDashboard />;
}
