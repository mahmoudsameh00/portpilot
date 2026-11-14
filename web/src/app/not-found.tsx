// "Not found or not yours" (plan §6.2): the API never says that something exists but is hidden (IDOR rule).
import { Compass } from "lucide-react";
import Link from "next/link";
import { Logo } from "@/components/shell/Brand";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <main className="night-ops flex min-h-dvh flex-col items-center justify-center px-6 text-center text-on-navy">
      <Logo dark />
      <Compass className="mt-10 size-10 text-lane" aria-hidden />
      <h1 className="mt-4 text-3xl font-semibold tracking-tight">This page is not on the chart.</h1>
      <p className="mt-2 max-w-md text-on-navy-muted">
        It does not exist, or it is not part of your access. Check the address, or go back to the home page.
      </p>
      <Button asChild size="lg" className="mt-8 bg-white text-navy hover:bg-white/90">
        <Link href="/">Back to home</Link>
      </Button>
    </main>
  );
}
