import type { Metadata } from "next";
import SupportPage from "./page-view";

export const metadata: Metadata = { title: "Help & Support" };

export default function Page() {
  return <SupportPage />;
}
