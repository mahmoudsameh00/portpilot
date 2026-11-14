// Concept — Ask (plan §6.0 (2)–(5)): a conversation where every number carries its receipt, the work is shown as a
// short trace, refused parts sit in a quiet box, and the answer follows the language of the question (dir="auto").
import { Check, CircleSlash, Clock, Cpu, Database, Lock, Sparkles } from "lucide-react";
import { ReceiptText } from "@/components/receipt/ReceiptText";
import { TopBar } from "@/components/shell/TopBar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { conversation } from "@/concept/fixtures";
import { cn } from "@/lib/utils";

export default function ConceptAnswer() {
  const turns = conversation.turns;
  const evidence = turns
    .flatMap((t) => t.evidence)
    .filter((e, i, all) => all.findIndex((x) => x.id === e.id) === i);
  const numbers = turns.reduce((s, t) => s + t.answer.numbers.length, 0);

  return (
    <>
      <TopBar active="/concept/answer" />
      <main className="mx-auto grid max-w-7xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <section aria-label="Conversation" className="flex min-w-0 flex-col gap-8">
          {turns.map((t, i) => (
            <article key={i} className="flex flex-col gap-3">
              <div className="ms-auto max-w-[85%] rounded-2xl rounded-ee-sm bg-navy px-5 py-3.5 text-on-navy">
                <p dir="auto" className="text-[0.95rem]">
                  {t.question}
                </p>
              </div>
              <p className="flex items-center justify-end gap-1.5 text-xs text-muted-foreground">
                <Sparkles className="size-3.5 text-primary" aria-hidden /> Understood as{" "}
                <span className="font-medium text-foreground">{t.understood}</span>
              </p>

              <ol className="flex flex-wrap items-center gap-1.5" aria-label="What was done">
                {t.steps.map((s, k) => (
                  <li key={s} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="grid size-4 place-items-center rounded-full bg-primary text-primary-foreground">
                      <Check className="size-3" aria-hidden />
                    </span>
                    {s}
                    {k < t.steps.length - 1 ? <span className="mx-1 h-px w-4 bg-border" aria-hidden /> : null}
                  </li>
                ))}
              </ol>

              <Card className="gap-4 py-5">
                <CardContent className="flex flex-col gap-4 px-6">
                  <div className="flex flex-wrap gap-1.5">
                    {t.tools.map((tool) => (
                      <span
                        key={tool.name}
                        className={cn(
                          "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-xs",
                          tool.state === "ok"
                            ? "border-primary/25 bg-accent text-primary"
                            : "text-muted-foreground",
                        )}
                      >
                        {tool.state === "ok" ? (
                          <Database className="size-3" aria-hidden />
                        ) : (
                          <CircleSlash className="size-3" aria-hidden />
                        )}
                        {tool.name}
                        {tool.state === "refused" ? (
                          <span className="font-sans">· not part of your access</span>
                        ) : null}
                      </span>
                    ))}
                  </div>
                  <p dir="auto" className="max-w-[68ch] text-[1.05rem] leading-8">
                    <ReceiptText text={t.answer.text} numbers={t.answer.numbers} />
                  </p>
                  {t.refused ? (
                    <div className="flex gap-3 rounded-lg border border-dashed px-4 py-3">
                      <Lock className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                      <p className="text-sm text-muted-foreground">{t.refused}</p>
                    </div>
                  ) : null}
                  <Separator />
                  <p className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Cpu className="size-3.5" aria-hidden /> {t.modelCalls} model calls
                    </span>
                    <span className="flex items-center gap-1">
                      <Clock className="size-3.5" aria-hidden /> {t.seconds.toFixed(1)} s
                    </span>
                    <span>Hover or tap an underlined number to see its source.</span>
                  </p>
                </CardContent>
              </Card>
            </article>
          ))}

          <form className="sticky bottom-4 flex gap-2 rounded-xl border bg-card p-1.5 shadow-float">
            <label htmlFor="follow" className="sr-only">
              Ask a follow-up
            </label>
            <input
              id="follow"
              dir="auto"
              placeholder="Ask a follow-up, in English or Arabic"
              className="h-11 min-w-0 flex-1 bg-transparent px-3 text-sm outline-none"
            />
            <Button type="button" size="lg" className="h-11">
              Ask
            </Button>
          </form>
        </section>

        <aside className="flex flex-col gap-4 lg:sticky lg:top-6 lg:self-start" aria-label="How we know">
          <Card className="gap-4">
            <CardHeader>
              <CardTitle className="text-base">How we know</CardTitle>
              <CardDescription>
                {numbers} numbers in this conversation, each bound to one of these sources by code.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-3">
              {evidence.map((e) => (
                <div key={e.id} className="rounded-lg border p-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-sm font-semibold">{e.id}</span>
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-[0.7rem] font-semibold",
                        e.status === "ok"
                          ? "bg-approved-wash text-approved-ink"
                          : "bg-muted text-muted-foreground",
                      )}
                    >
                      {e.status === "ok" ? "read" : "not permitted"}
                    </span>
                  </div>
                  <p className="mt-1 font-mono text-xs text-muted-foreground">
                    {e.tool} → {e.source}
                  </p>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card className="gap-3 bg-navy text-on-navy">
            <CardContent className="text-sm text-on-navy-muted">
              Answers follow the language of the question. The interface stays in English.
            </CardContent>
          </Card>
        </aside>
      </main>
    </>
  );
}
