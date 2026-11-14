// The deck's own status badges (plan §6.0 (6)): amber "Draft for approval", green "Approved". Never colour alone.
import { CircleCheck, CircleDashed } from "lucide-react";
import { cn } from "@/lib/utils";

export function StatusBadge({ kind }: { kind: "draft" | "approved" }) {
  const Icon = kind === "draft" ? CircleDashed : CircleCheck;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold",
        kind === "draft" ? "bg-waiting-wash text-waiting-ink" : "bg-approved-wash text-approved-ink",
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      {kind === "draft" ? "Draft for approval" : "Approved"}
    </span>
  );
}
