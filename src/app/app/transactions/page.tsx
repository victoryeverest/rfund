import type { Metadata } from "next";
import TransactionsPage from "./page-view";

export const metadata: Metadata = { title: "Transactions" };

export default function Page() {
  return <TransactionsPage />;
}
