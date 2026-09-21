import type { Metadata } from "next";
import NotificationsPage from "./page-view";

export const metadata: Metadata = { title: "Notifications" };

export default function Page() {
  return <NotificationsPage />;
}
