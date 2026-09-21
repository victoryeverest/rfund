import type { Metadata } from "next";
import AdminKycPage from "./page-view";

export const metadata: Metadata = { title: "KYC review" };

export default function Page() {
  return <AdminKycPage />;
}
