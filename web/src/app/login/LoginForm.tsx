"use client";
// The sign-in form (plan §6.1): one message for every wrong login (the API gives the same 401 for both), a wait time
// for a lockout (Retry-After), a plain message when the API is down. No "remember me", no sign-up, no reset.
import { AlertCircle, Loader2 } from "lucide-react";
import { useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function messageFor(status: number, retryAfter: string | null): string {
  if (status === 401 || status === 422) return "Email or password is wrong.";
  if (status === 429) {
    const minutes = Math.max(1, Math.ceil(Number(retryAfter ?? "60") / 60));
    return `Too many attempts. Try again in ${minutes} minute${minutes === 1 ? "" : "s"}.`;
  }
  if (status === 502 || status === 503)
    return "The PortPilot API is not reachable right now. Try again shortly.";
  return "Sign-in failed. Try again.";
}

export function LoginForm({ next, apiDown }: { next: string; apiDown: boolean }) {
  const [error, setError] = useState<string | null>(
    apiDown ? "The PortPilot API is not reachable right now. Try again shortly." : null,
  );
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/bff/login", {
        method: "POST",
        headers: { "content-type": "application/json", accept: "application/json" },
        body: JSON.stringify({
          email: String(form.get("email") ?? "").trim(),
          password: String(form.get("password") ?? ""),
        }),
        credentials: "same-origin",
      });
      if (!res.ok) {
        setError(messageFor(res.status, res.headers.get("retry-after")));
        return;
      }
      window.location.assign(next); // a full load so the server reads the new session
    } catch {
      setError(messageFor(502, null));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="mt-8 flex flex-col gap-5" noValidate>
      {error ? (
        <Alert variant="destructive" role="alert">
          <AlertCircle aria-hidden />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}
      <div className="flex flex-col gap-2">
        <Label htmlFor="email">Work email</Label>
        <Input id="email" name="email" type="email" autoComplete="username" required className="h-11" />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          className="h-11"
        />
      </div>
      <Button type="submit" size="lg" className="h-11" disabled={busy}>
        {busy ? <Loader2 className="animate-spin" aria-hidden /> : null}
        {busy ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}
