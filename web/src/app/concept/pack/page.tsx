// Concept — the weekly pack reviewed like slides (plan §6.0 (6)): a filmstrip, the current slide as a replica of the
// PPTX (the deck's own colours), the Validator note pinned to its bullet, and a decision panel with one primary action.
import { Download, PencilLine, RotateCcw, ShieldCheck, TriangleAlert, XCircle } from "lucide-react";
import Link from "next/link";
import { StatusBadge } from "@/components/concept/StatusBadge";
import { ReceiptText } from "@/components/receipt/ReceiptText";
import { TopBar } from "@/components/shell/TopBar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { BillingChart } from "@/components/viz/charts";
import { home, pack, WEEKS } from "@/concept/fixtures";
import { cn } from "@/lib/utils";

export default function ConceptPack() {
  const total = pack.titles.length;
  const checked = total - pack.noteSlides.length;

  return (
    <>
      <TopBar active="/concept/pack" />
      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <div className="flex flex-wrap items-center gap-3">
          <div className="me-auto">
            <p className="text-sm text-muted-foreground">Weekly finance pack</p>
            <h1 className="font-mono text-2xl font-semibold">{pack.week}</h1>
          </div>
          <StatusBadge kind="draft" />
          <Button variant="ghost" asChild>
            <Link href="#">
              <Download aria-hidden /> Download PowerPoint
            </Link>
          </Button>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-[13rem_minmax(0,1fr)_21rem]">
          <nav aria-label="Slides" className="order-2 min-w-0 lg:order-none">
            <div className="mb-3 hidden lg:block">
              <p className="text-xs text-muted-foreground">
                {checked} of {total} slides clean
              </p>
              <Progress
                value={(checked / total) * 100}
                className="mt-1.5 h-1.5"
                aria-label={`${checked} of ${total} slides clean`}
              />
            </div>
            <ol className="flex gap-2 overflow-x-auto pb-2 lg:flex-col lg:overflow-visible lg:pb-0">
              {pack.titles.map((title, i) => (
                <li key={title} className="shrink-0">
                  <a
                    href="#"
                    aria-current={i === pack.current ? "true" : undefined}
                    className={cn(
                      "flex w-44 items-start gap-2 rounded-lg border px-2.5 py-2 text-sm transition-colors lg:w-full",
                      i === pack.current
                        ? "border-primary bg-card font-medium shadow-sm"
                        : "border-transparent text-muted-foreground hover:bg-card",
                    )}
                  >
                    <span className="num w-5 shrink-0 font-mono text-xs text-muted-foreground">{i + 1}</span>
                    <span className="flex-1 leading-snug">{title}</span>
                    {pack.noteSlides.includes(i) ? (
                      <TriangleAlert className="size-4 shrink-0 text-waiting" aria-label="Validator note" />
                    ) : null}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          <section className="min-w-0" aria-label={`Slide ${pack.current + 1} of ${total}`}>
            {/* The replica keeps the deck's colours: it shows what the PPTX will look like. */}
            <div className="w-full overflow-hidden rounded-xl border bg-white p-[4%] text-navy shadow-float sm:aspect-[16/9]">
              <div className="flex h-full flex-col">
                <h2 className="text-[clamp(1.1rem,2.2vw,1.6rem)] font-bold">{pack.titles[pack.current]}</h2>
                <div className="mt-3 grid min-h-0 flex-1 grid-cols-1 gap-4 sm:mt-[2%] sm:grid-cols-[0.85fr_1.25fr] sm:gap-[4%]">
                  <ul className="flex flex-col gap-3 text-sm sm:gap-[6%] sm:text-[clamp(0.72rem,1.15vw,0.95rem)]">
                    {pack.bullets.map((b, i) => (
                      <li
                        key={i}
                        className={cn(
                          "border-s-2 ps-3 leading-relaxed",
                          i === pack.noteBullet ? "border-waiting bg-waiting-wash/70" : "border-chart-1",
                        )}
                      >
                        <ReceiptText text={b.text} numbers={b.numbers} />
                      </li>
                    ))}
                  </ul>
                  <div className="flex items-center">
                    <BillingChart weeks={WEEKS} billed={home.billing.billed} budget={home.billing.budget} />
                  </div>
                </div>
                <p className="num text-end font-mono text-[0.65rem] text-muted-foreground">
                  {pack.current + 1} / {total}
                </p>
              </div>
            </div>
            <div className="mt-4 flex gap-3 rounded-lg border border-waiting/40 bg-waiting-wash px-4 py-3 text-waiting-ink">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
              <p className="text-sm">
                <span className="font-semibold">Validator:</span> {pack.note}
              </p>
            </div>
          </section>

          <Card className="order-3 self-start lg:order-none">
            <CardHeader>
              <CardTitle className="text-base">Your decision</CardTitle>
              <CardDescription>Edits are checked again before the deck is rebuilt.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <Tabs defaultValue="text">
                <TabsList className="w-full">
                  <TabsTrigger value="text">Text</TabsTrigger>
                  <TabsTrigger value="add">Add slide</TabsTrigger>
                  <TabsTrigger value="chart">Chart</TabsTrigger>
                  <TabsTrigger value="note">Note</TabsTrigger>
                </TabsList>
                <TabsContent value="text" className="mt-3">
                  <label htmlFor="bullet" className="text-xs text-muted-foreground">
                    Bullet 2 — numbers are filled from the evidence by code
                  </label>
                  <textarea
                    id="bullet"
                    defaultValue={pack.draftText}
                    rows={4}
                    className="mt-1.5 w-full resize-y rounded-md border bg-background p-3 font-mono text-xs leading-relaxed focus-visible:border-primary"
                  />
                  <Button variant="outline" size="sm" className="mt-2">
                    <PencilLine aria-hidden /> Save and check again
                  </Button>
                </TabsContent>
                <TabsContent value="add" className="mt-3 text-sm text-muted-foreground">
                  Add one slide from the chart catalogue.
                </TabsContent>
                <TabsContent value="chart" className="mt-3 text-sm text-muted-foreground">
                  Pick another view of this slide&apos;s data.
                </TabsContent>
                <TabsContent value="note" className="mt-3 text-sm text-muted-foreground">
                  Write the approver&apos;s note for the cover slide.
                </TabsContent>
              </Tabs>
              <Separator />
              <Button size="lg" className="h-11 w-full">
                <ShieldCheck aria-hidden /> Approve the pack
              </Button>
              <div className="flex gap-2">
                <Button variant="outline" className="flex-1">
                  <RotateCcw aria-hidden /> Ask for a rewrite
                </Button>
                <Button
                  variant="ghost"
                  className="text-destructive hover:bg-alert-wash hover:text-destructive"
                >
                  <XCircle aria-hidden /> Reject
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </main>
    </>
  );
}
