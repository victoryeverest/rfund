import type { Metadata } from "next";
import CooperativesPage from "./page-view";

export const metadata: Metadata = {
  title: "Cooperatives",
  description: "RFUND gives cooperative societies digital records, transparent ledgers and stronger loan assessments for members.",
};

export default function Page() {
  return <CooperativesPage />;
}
