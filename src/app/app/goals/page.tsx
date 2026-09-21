import type { Metadata } from "next";
import GoalsPage from "./page-view";

export const metadata: Metadata = { title: "Savings goals" };

export default function Page() {
  return <GoalsPage />;
}
