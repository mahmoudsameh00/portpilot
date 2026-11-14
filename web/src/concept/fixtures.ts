// Sample data for the concept gate (D-FE-3). Shapes follow the API (answer_summary, packs, voyage watch, route
// advice) and the proposed F0 `numbers` spans. Week 23 billing is the real golden-set value (finance_qa q01); every
// other figure is illustrative. Removed when F2–F6 read the API.
import { spansFor, type NumberSpan } from "@/lib/receipts";

const n = (
  text: string,
  evidence_id: string,
  field: string,
  source: string,
  filter?: string,
): Omit<NumberSpan, "start" | "end" | "row"> => ({
  text,
  evidence_id,
  field,
  source,
  filter: filter ?? null,
  trust: "database",
});

const withSpans = (text: string, nums: ReturnType<typeof n>[]) => ({ text, numbers: spansFor(text, nums) });

const KPI = "finance.finance_kpi";
const W45 = "report_week = 45";
export const WEEKS = Array.from({ length: 12 }, (_, i) => `W${34 + i}`);

export const home = {
  user: { name: "Mona", role: "Finance manager", initial: "M" },
  today: "Thu 6 Nov 2025",
  lastRun: "10:30",
  kpis: [
    {
      label: "Billed this week",
      value: n("8.41M SDR", "kpi.weekly", "billed_sdr", KPI, W45),
      delta: "+3.2% vs budget",
      trend: "up" as const,
      series: [7.9, 8.1, 8.3, 7.6, 8.0, 8.4, 8.2, 7.8, 8.5, 8.3, 8.1, 8.41],
    },
    {
      label: "Collected",
      value: n("3.40M SDR", "kpi.weekly", "collected_sdr", KPI, W45),
      delta: "−4.1% vs W44",
      trend: "down" as const,
      series: [3.1, 3.4, 3.6, 3.2, 3.5, 3.7, 3.3, 3.6, 3.8, 3.5, 3.55, 3.4],
    },
    {
      label: "Overdue receivables",
      value: n("10.25M SDR", "kpi.weekly", "overdue_sdr", KPI, W45),
      delta: "+0.6M in 4 weeks",
      trend: "up" as const,
      series: [9.1, 9.0, 9.3, 9.4, 9.2, 9.5, 9.6, 9.7, 9.65, 9.9, 10.1, 10.25],
    },
    {
      label: "Suez transits per day",
      value: n("41", "kpi.suez", "mean_daily_transits", "external.portwatch", "last 7 days"),
      delta: "steady",
      trend: "flat" as const,
      series: [38, 40, 39, 41, 42, 40, 39, 41, 42, 41, 40, 41],
    },
  ],
  pack: {
    week: "2025-W45",
    line: withSpans("Billed 8,412,300.50 SDR against a budget of 8,150,000.00 SDR.", [
      n("8,412,300.50 SDR", "kpi.weekly", "billed_sdr", KPI, W45),
      n("8,150,000.00 SDR", "kpi.weekly", "budget_sdr", KPI, W45),
    ]),
    notes: 2,
    slides: 10,
  },
  alerts: [
    {
      vessel: "NG Aswan",
      text: "ETA to NLRTM +6.4 h over schedule",
      level: "high" as const,
      angle: 40,
      dist: 0.62,
    },
    {
      vessel: "NG Luxor",
      text: "Gale on the Bay of Biscay leg",
      level: "high" as const,
      angle: 155,
      dist: 0.48,
    },
    { vessel: "NG Karnak", text: "ETA to SGSIN +5.1 h", level: "high" as const, angle: 250, dist: 0.8 },
    {
      vessel: "NG Edfu",
      text: "Speed under plan for 12 h",
      level: "medium" as const,
      angle: 300,
      dist: 0.35,
    },
    {
      vessel: "NG Philae",
      text: "Berth window moved at EGPSD",
      level: "low" as const,
      angle: 95,
      dist: 0.25,
    },
  ],
  route: {
    origin: "EGPSD",
    destination: "NLRTM",
    suez: { days: 9.8, cost: 1.82, distance: 3110 },
    cape: { days: 21.6, cost: 2.37, distance: 9940 },
  },
  billing: {
    billed: [7.9, 8.1, 8.3, 7.6, 8.0, 8.4, 8.2, 7.8, 8.5, 8.3, 8.1, 8.41],
    budget: [8.0, 8.0, 8.05, 8.05, 8.1, 8.1, 8.1, 8.15, 8.15, 8.15, 8.15, 8.15],
  },
  ageing: [
    { bucket: "0–30 d", value: 4.1 },
    { bucket: "31–60 d", value: 2.9 },
    { bucket: "61–90 d", value: 1.8 },
    { bucket: "90+ d", value: 1.45 },
  ],
  starters: [
    "How much did PortPilot bill in week 23 of 2025?",
    "Which customers are most overdue?",
    "فوترنا كام في أسبوع 23 من 2025؟",
  ],
};

export const conversation = {
  turns: [
    {
      question:
        "How much did PortPilot bill in week 23 of 2025, and how does it compare with budget? And how many people work in HR?",
      understood: "billing and budget for 2025-W23",
      steps: ["Checked your access", "Read finance_kpi", "Bound every number", "Validated"],
      tools: [
        { name: "finance_kpi", state: "ok" as const },
        { name: "employee_directory", state: "refused" as const },
      ],
      answer: withSpans(
        "In week 23 of 2025 PortPilot billed 8,394,785.98 SDR, 3.4% above the week's budget of 8,120,000.00 SDR. Collections that week were 3,611,204.75 SDR.",
        [
          n("8,394,785.98 SDR", "kpi.weekly", "billed_sdr", KPI, "report_week = 23"),
          n("3.4%", "kpi.weekly", "billed_vs_budget_pct", KPI, "report_week = 23"),
          n("8,120,000.00 SDR", "kpi.weekly", "budget_sdr", KPI, "report_week = 23"),
          n("3,611,204.75 SDR", "kpi.weekly", "collected_sdr", KPI, "report_week = 23"),
        ],
      ),
      refused: "HR headcount is not part of your access, so that part was not answered.",
      evidence: [
        { id: "kpi.weekly", tool: "finance_kpi", status: "ok", source: KPI },
        { id: "hr.directory", tool: "employee_directory", status: "not_permitted", source: "hr.employees" },
      ],
      modelCalls: 2,
      seconds: 4.2,
    },
    {
      question: "وكام اتحصّل من الفواتير دي لحد دلوقتي؟",
      understood: "collections against 2025-W23 billing (follow-up)",
      steps: ["Checked your access", "Read finance_kpi", "Bound every number", "Validated"],
      tools: [{ name: "finance_kpi", state: "ok" as const }],
      answer: withSpans(
        "من فواتير أسبوع 23 اتحصّل لحد دلوقتي 6,912,440.10 SDR، يعني 82.3% من المبلغ، والباقي 1,482,345.88 SDR لسه مفتوح.",
        [
          n("6,912,440.10 SDR", "kpi.weekly", "collected_to_date_sdr", KPI, "billing_week = 23"),
          n("82.3%", "kpi.weekly", "collection_rate_pct", KPI, "billing_week = 23"),
          n("1,482,345.88 SDR", "kpi.weekly", "open_sdr", KPI, "billing_week = 23"),
        ],
      ),
      refused: null,
      evidence: [{ id: "kpi.weekly", tool: "finance_kpi", status: "ok", source: KPI }],
      modelCalls: 1,
      seconds: 2.9,
    },
  ],
};

export const pack = {
  week: "2025-W45",
  titles: [
    "Weekly finance pack — W45",
    "The week at a glance",
    "Billing against budget",
    "Collections",
    "Budget misses",
    "Receivables ageing",
    "Overdue customers",
    "Tariff checks",
    "Suez transits",
    "Appendix",
  ],
  current: 2,
  noteSlides: [2, 6],
  bullets: [
    withSpans("Billing reached 8,412,300.50 SDR, 262,300.50 SDR above budget.", [
      n("8,412,300.50 SDR", "kpi.weekly", "billed_sdr", KPI, W45),
      n("262,300.50 SDR", "kpi.weekly", "billed_vs_budget_sdr", KPI, W45),
    ]),
    withSpans("Year to date billing is 352,904,118.00 SDR, 101.8% of budget.", [
      n("352,904,118.00 SDR", "audit.ytd", "ytd_billed_sdr", "audit.ytd", "year = 2025"),
      n("101.8%", "audit.ytd", "ytd_vs_budget_pct", "audit.ytd", "year = 2025"),
    ]),
    withSpans("Only two of the last 12 weeks fell below budget.", []),
  ],
  noteBullet: 1,
  note: "Bullet 2 says “year to date” — check that week 53 is not counted in this year.",
  draftText:
    "Year to date billing is {audit.ytd:ytd_billed_sdr|sdr}, {audit.ytd:ytd_vs_budget_pct|%1} of budget.",
};
