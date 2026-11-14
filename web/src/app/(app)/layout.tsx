// Every signed-in page goes through here (plan §4.1): no session → sign in, with a same-origin return path.
// Who the user is comes only from GET /me at the API; the products menu is built from it.
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { getSession, safeNext } from "@/lib/session";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const session = await getSession();
  if (session.kind !== "signed-in") {
    const here = safeNext((await headers()).get("x-portpilot-path"));
    redirect(here === "/" ? "/login" : `/login?next=${encodeURIComponent(here)}`);
  }
  return <QueryProvider>{children}</QueryProvider>;
}
