import type { Metadata } from "next";
import ProfilePage from "./page-view";

export const metadata: Metadata = { title: "Profile" };

export default function Page() {
  return <ProfilePage />;
}
