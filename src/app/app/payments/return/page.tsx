import type { Metadata } from "next";
import { Suspense } from "react";
import PaymentReturnView from "./page-view";

export const metadata: Metadata = {
  title: "Payment status | RFUND",
};

export default function PaymentReturnPage() {
  return (
    <Suspense fallback={null}>
      <PaymentReturnView />
    </Suspense>
  );
}
