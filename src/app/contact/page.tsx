import type { Metadata } from "next";
import ContactPage from "./page-view";

export const metadata: Metadata = {
  title: "Contact",
  description: "Talk to the RFUND team about savings, loans, agents or cooperatives.",
};

export default function Page() {
  return <ContactPage />;
}
