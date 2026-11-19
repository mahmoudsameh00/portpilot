"use client";
// Who you are (from /me) and sign out (plan §4.1 (3)): the BFF revokes the token at the API and clears both cookies.
import { LogOut, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { Me } from "@/lib/api-types";
import { useRouter } from "next/navigation";
import { bffFetch } from "@/lib/bff/client";
import { cn } from "@/lib/utils";
import { setRecoveryOwner } from "@/lib/run-recovery";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function UserMenu({ me, dark = false }: { me: Me; dark?: boolean }) {
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  async function signOut() {
    setBusy(true);
    await bffFetch("/logout", { method: "POST" }).catch(() => undefined);
    setRecoveryOwner(null);
    router.replace("/login");
    router.refresh();
  }
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="rounded-full focus-visible:outline-2"
        aria-label={`Account: employee ${me.employee_id}, ${me.role}, ${me.department}`}
      >
        <Avatar className="size-9">
          <AvatarFallback
            className={cn("text-sm font-semibold", dark ? "bg-white text-navy" : "bg-navy text-white")}
          >
            {me.department.charAt(0)}
          </AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="flex flex-col gap-0.5">
          <span className="font-semibold">Employee {me.employee_id}</span>
          <span className="text-xs font-normal text-muted-foreground">
            {cap(me.role)}, {me.department}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <div className="flex items-center gap-2 px-2 py-1.5 text-xs text-muted-foreground">
          <ShieldCheck className="size-3.5" aria-hidden /> Reads up to sensitivity level {me.ceiling}
        </div>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={signOut} disabled={busy}>
          <LogOut aria-hidden /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
