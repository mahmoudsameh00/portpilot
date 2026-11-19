"use client";
// A number bound to its evidence (MASTER §5): dotted Nile underline; hover / focus / tap opens the tally slip.
import { Popover } from "radix-ui";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";
import type { NumberSpan } from "@/lib/receipts";
import { cn } from "@/lib/utils";

export function NumberChip({ span }: { span: NumberSpan }) {
  const t = useTranslations("receipt");
  const [open, setOpen] = useState(false);
  const closeTimer = useRef<number | undefined>(undefined);
  const hover = (next: boolean) => {
    window.clearTimeout(closeTimer.current);
    if (next) setOpen(true);
    else closeTimer.current = window.setTimeout(() => setOpen(false), 120);
  };
  const untrusted = span.trust === "untrusted_upload" || span.trust === "web";

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          onClick={(e) => {
            // a click opens (never toggles): with a mouse, hovering has already opened it; Esc / outside closes
            e.preventDefault();
            hover(true);
          }}
          onPointerEnter={(e) => e.pointerType === "mouse" && hover(true)}
          onPointerLeave={(e) => e.pointerType === "mouse" && hover(false)}
          className={cn(
            "num rounded-[3px] font-semibold underline decoration-dotted decoration-2 underline-offset-[6px]",
            "decoration-primary hover:bg-accent data-[state=open]:bg-accent",
            untrusted && "decoration-waiting",
          )}
          aria-label={t("open", { value: span.text })}
        >
          <bdi>{span.text}</bdi>
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="top"
          align="center"
          sideOffset={10}
          collisionPadding={16}
          onPointerEnter={() => hover(true)}
          onPointerLeave={() => hover(false)}
          className={cn(
            "slip-perforated z-50 w-72 rounded-md bg-popover text-popover-foreground px-4 pt-4 pb-3 text-sm shadow-float",
            "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
            "data-[state=closed]:animate-out data-[state=closed]:fade-out-0",
          )}
        >
          <p className="text-xs text-muted-foreground">{t("title")}</p>
          <p className="num mt-1 font-mono text-lg font-semibold">
            <bdi>{span.text}</bdi>
          </p>
          <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 border-t border-dashed border-border pt-3">
            <dt className="text-muted-foreground">{t("field")}</dt>
            <dd>
              <bdi className="font-medium">{span.field}</bdi>
            </dd>
            <dt className="text-muted-foreground">{t("source")}</dt>
            <dd>
              <bdi className="font-medium">{span.source}</bdi>
            </dd>
            {span.filter ? (
              <>
                <dt className="text-muted-foreground">{t("filter")}</dt>
                <dd>
                  <bdi className="font-medium">{span.filter}</bdi>
                </dd>
              </>
            ) : null}
            <dt className="text-muted-foreground">{t("evidence")}</dt>
            <dd>
              <bdi className="font-medium">{span.evidence_id}</bdi>
            </dd>
          </dl>
          <p
            className={cn(
              "mt-3 rounded-[4px] px-2 py-1 text-xs",
              untrusted ? "bg-waiting-wash text-waiting-ink" : "bg-accent text-primary",
            )}
          >
            {untrusted ? t("trust_untrusted") : t("trust_checked")}
          </p>
          <Popover.Arrow className="fill-popover" width={14} height={7} />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
