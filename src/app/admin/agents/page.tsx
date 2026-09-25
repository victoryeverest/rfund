import type { Metadata } from "next";
import AdminAgentsPage from "./page-view";

export const metadata: Metadata = { title: "Agents" };

export default function Page() {
  return <AdminAgentsPage />;
}
