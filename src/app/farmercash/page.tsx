import type { Metadata } from "next";
import FarmerCashPage from "./page-view";

export const metadata: Metadata = {
  title: "FarmerCash",
  description: "Seasonal, collateral-free financing for smallholder farmers — from land preparation to harvest.",
};

export default function Page() {
  return <FarmerCashPage />;
}
