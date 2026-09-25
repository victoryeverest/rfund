import type { Metadata } from "next";
import AdminSupportPage from "./page-view";

export const metadata: Metadata = { title: "Support" };

export default function Page() {
  return <AdminSupportPage />;
}
