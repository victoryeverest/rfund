import { redirect } from "next/navigation";

// Section root: land on the agent console dashboard. The shell's auth
// guard redirects unauthenticated visitors to /login.
export default function AgentAppIndex() {
  redirect("/agent/dashboard");
}
