import { redirect } from "next/navigation";

// Section root: land on the admin console dashboard. The shell's auth
// guard redirects unauthenticated visitors to /login.
export default function AdminAppIndex() {
  redirect("/admin/dashboard");
}
