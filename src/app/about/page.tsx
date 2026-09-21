import type { Metadata } from "next";
import AboutPage from "./page-view";

export const metadata: Metadata = {
  title: "About RFUND",
  description: "Who we are, what we believe, and how RFUND serves underserved communities.",
};

export default function Page() {
  return <AboutPage />;
}
