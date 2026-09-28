import { redirect } from "next/navigation";

// Section root: land authenticated users on the customer dashboard.
// Unauthenticated visitors are bounced to it, where the shell's auth
// guard sends them to /login instead.
export default function CustomerAppIndex() {
  redirect("/app/dashboard");
}
