import type { Metadata } from "next";
import AdminAuditPage from "./page-view";

export const metadata: Metadata = { title: "Audit" };

export default function Page() {
  return <AdminAuditPage />;
}
