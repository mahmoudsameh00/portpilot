# PortPilot web — design system (MASTER)

Brand update approved 2026-11-11: PortPilot replaces the former product name. The logo is a P-shaped port with
an outbound navigation arrow (`src/components/shell/Brand.tsx`), with a matching `app/icon.svg` and reusable
`docs/brand/portpilot-logo.svg`. The existing blue/white palette and Geist typography remain the design system.

Status: **APPROVED (owner 2026-11-06, "موافق على v2")** — the concept gate of the Frontend plan (§6.0, D-FE-3, D-FE-6).
The source of truth for every page; later changes only through a note in the plan's Progress / deviations.

Owner, 2026-11-06 (after v1): keep the colours — **blue and white**; the look must carry **logistics business +
technology + analysis**; the **interface is English** (smart and elegant); only answers follow the language of the
question (Arabic or English). The owner picked all three directions offered (night-ops hero, control tower, bento)
and the **Geist** typeface.

How this was made (plan §9a): **UI UX Pro Max** `--design-system "logistics control tower analytics AI enterprise"`
(variance 7, motion 5, density 7) → pattern "Real-Time / Operations", Swiss minimal style, a blue / white palette,
status colours, "data-dense but scannable"; its typography and chart searches; **Frontend Design** for the one bold
element and restraint; **dataviz** for the chart rules and its palette validator (categorical blue / teal / amber /
violet: all six checks pass on white; teal and amber below 3:1 → always labelled); **shadcn/ui** (`radix-nova`
preset, official registry) for the components.

## 1. The idea: a control tower over the trade lanes

The first screen is the business itself: a **night-ops band** (deep navy) with a dot-matrix map of the land between
the North Sea and the China Sea, PortPilot's two lanes — via Suez (solid, glowing) and via the Cape (dotted, the
long way) — vessels moving along them and Port Said pulsing as home. Under it, on white, the **control tower**: the
four numbers of the week with sparklines, then a **bento** of services, one tile per product, one action per tile.
Inside every tile the signature stays: **each number has a receipt** (field, view, filter, evidence id).

## 2. Colour (tokens in `src/app/globals.css`, shadcn names + ours)

| Token                       | Value                                                                           | Use                                                                           |
| --------------------------- | ------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- |
| `background` / `card`       | `#F6F8FB` / `#FFFFFF`                                                           | page / panels                                                                 |
| `foreground` / `navy`       | `#0B2545`                                                                       | text, the night-ops band, the question bubble                                 |
| `navy-deep`                 | `#06162B`                                                                       | top of the band gradient                                                      |
| `primary`                   | `#1F66C9`                                                                       | actions, links, focus ring (5.5:1 on white)                                   |
| `muted-foreground`          | `#5A6B82`                                                                       | secondary text (5.4:1)                                                        |
| `border` / `input`          | `#E3E9F2` / `#D5DEEA`                                                           | hairlines                                                                     |
| `accent` / `secondary`      | `#EEF4FD`                                                                       | hover, chips, the receipt highlight                                           |
| `lane`                      | `#6FB1FF`                                                                       | lanes, vessels, live dots on navy                                             |
| `on-navy` / `on-navy-muted` | `#FFFFFF` / `#B8C7DB`                                                           | text on navy (10:1)                                                           |
| `chart-1`                   | `#2A78D6`                                                                       | billed (the deck's series colour)                                             |
| `chart-2`                   | `#A3A29C` dashed                                                                | budget                                                                        |
| `marker`                    | `#EB6834`                                                                       | the report week, the oldest debt                                              |
| status                      | amber `#EDA100` / green `#1BAF7A` / orange `#EB6834` with their washes and inks | draft / approved / high alert — always icon + text                            |
| `chart-muted`               | `#C5D1E0`                                                                       | emphasis: the marks that are context (dashboards amendment 1)                 |
| `chart-compare`             | `#9EC5F4`                                                                       | the compare week beside the shown week                                        |
| `ramp-1…4`                  | `#86B6EF` / `#5598E7` / `#2A78D6` / `#184F95`                                   | receivables by age, older = darker (validator: ordinal pass); 90+ in `marker` |

Light only (the band is the one dark surface). Raw hex only in `globals.css`; the slide replica keeps the deck's
own colours because it shows what the PPTX will look like.

## 3. Type

- **Geist** (interface, OFL, Vercel) and **Geist Mono** (codes and ids: UN/LOCODEs, weeks, evidence ids, tool names,
  slots). **IBM Plex Sans Arabic** is only a fallback in the font stack: it draws Arabic answers and questions.
- Self-hosted by `next/font` at build time (CSP `font-src 'self'`).
- Headings tight (−0.02em), sentence case; no all-caps labels. Numbers `tabular-nums`.

## 4. Layout

- Max width 80 rem; the hero is a two-column grid (text + map) that stacks on mobile; KPI cards overlap the band's
  lower edge; the bento is a 6-column grid (pack 3 + watch 3, billing 4 + route 2, ageing 3 + charts 3).
- Radius from shadcn (`--radius` 0.75 rem); shadows only on what floats (KPI cards over the band, the slip).
- Logical spacing utilities in our code (answers can be RTL inside the LTR interface).

## 5. Visuals that carry the idea

- **LaneMap** — dot-matrix land (coarse outlines, schematic, not navigation), the two lanes, nine ports, six vessels
  (`animateMotion`), Port Said pulsing. No tiles, no third-party request.
- **KPI tile** — label, the number as a receipt chip, the change, a 2 px sparkline with an end dot.
- **Radar** — voyage alerts as blips by severity under a slow sweep; the list beside it says the same in words.
- **Container rows** — overdue receivables by age, one container = 0.5M SDR, the oldest bucket in `marker` orange.
- **Route compare** — Suez against the Cape on one shared scale per measure, then one sentence with the saving.
- **Billing chart** — billed bars (4 px rounded ends, 2 px gaps), budget dashed, the report week underlined.
- **Receipt slip** — perforated top edge; field, source, filter, evidence id, trust line.

## 6. Motion

The lanes draw once, vessels move slowly, Port Said and high alerts pulse, the radar sweeps. Everything stops for
`prefers-reduced-motion` (CSS animations by media query, SVG animations paused by `MotionGuard`).

## 7. Accessibility floor

Text contrast ≥ 4.5, focus ring 2 px `primary`, targets ≥ 44 px for primary actions, every chart has an accessible
name and a text equivalent beside it, axe 0 serious / critical on every page (Playwright).

## 8. Words

English, plain verbs, the user's words: "Review the pack", "Open the watch", "Not part of your access". Arabic
appears only where the user wrote Arabic (questions, answers, starter questions).
