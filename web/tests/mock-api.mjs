// A tiny stand-in for the PortPilot API (FastAPI, ADR-064) so the E2E tests run without databases or LLMs
// (Frontend plan §10.3). Only what F2 needs: login / logout / me / health. Bound to 127.0.0.1.
// Test hooks under /__mock/* (never proxied by the BFF: not in the OpenAPI allow-list).
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { createServer } from "node:http";

const PORT = Number(process.env.MOCK_API_PORT ?? 8765);
const { users } = JSON.parse(readFileSync(new URL("./fixtures/users.json", import.meta.url), "utf8"));
const tokens = new Map(); // token -> me
const failures = new Map(); // email -> count
let health = "ready";
const lastByToken = new Map(); // token -> its last /api/v1 request (the "no cookies forwarded" test)

// --- F3: conversations, questions as runs with SSE events, uploads (shapes = the OpenAPI snapshot) ---------------
const conversations = new Map(); // id -> {conversation_id, employee_id, created_at, last_turn_at, closed_at, turns}
const runsById = new Map(); // run_id -> {events: [], result, owner}
const questions = new Map(); // thread_id -> QuestionDetail
const uploads = new Map(); // conversation_id -> [UploadSummary]
const now = () => new Date().toISOString();
const summary = (c) => ({
  conversation_id: c.conversation_id,
  employee_id: c.employee_id,
  created_at: c.created_at,
  last_turn_at: c.last_turn_at,
  closed_at: c.closed_at,
});
const EN = "PortPilot billed 8,394,785.98 SDR in week 23 of 2025, 3.4% above the budget of 8,120,000.00 SDR.";
const AR = "فوترت PortPilot مبلغ 8,394,785.98 SDR في أسبوع 23 من 2025، أعلى من الموازنة 8,120,000.00 SDR.";
const u16 = (s) => s.length; // BMP only in these fixtures: UTF-16 units = JS string length
function spans(text) {
  const out = [];
  for (const [num, field] of [
    ["8,394,785.98 SDR", "billed_sdr"],
    ["8,120,000.00 SDR", "budget_sdr"],
  ]) {
    const start = u16(text.slice(0, text.indexOf(num)));
    out.push({
      text: num,
      start,
      end: start + num.length,
      evidence_id: "insight.c1",
      field,
      source: "finance.kpi_weekly",
      filter: "report_week = 23",
      row: 0,
    });
  }
  return out;
}
function answerFor(me, question) {
  const finance = me.tools.includes("finance_kpi");
  const arabic = /[؀-ۿ]/.test(question);
  const base = {
    thread: null,
    not_permitted: [],
    evidence: {},
    problems: [],
    stop_reason: null,
    model_calls: 0,
    cached: 0,
    view: null,
    numbers: [],
  };
  // §10.5: model text carrying markup must render inert (the shapes the plan names)
  if (/render test/i.test(question))
    return {
      ...base,
      status: "answered",
      answer:
        'Done <script>window.__pwned = 1</script> and <img src=x onerror="window.__pwned = 2"> ' +
        "[open](javascript:window.__pwned=3) ![chart](https://evil.example/pixel.png) " +
        '<a href="https://evil.example/">site</a>',
    };
  if (!finance)
    return {
      ...base,
      status: "not_permitted",
      answer: "This question is about Finance data, which is not part of your access.",
      not_permitted: ["finance figures"],
    };
  const text = arabic ? AR : EN;
  return {
    ...base,
    status: "answered",
    answer: text,
    numbers: spans(text),
    model_calls: 2,
    evidence: { "insight.c1": { tool: "finance_kpi", status: "ok", source: "finance.kpi_weekly" } },
  };
}
function sse(res, events) {
  res.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-store" });
  let i = 0;
  const tick = () => {
    if (i >= events.length) return res.end();
    const e = events[i++];
    res.write(`id: ${e.id}
event: ${e.event}
data: ${JSON.stringify(e.data)}

`);
    setTimeout(tick, 120);
  };
  tick();
}
// --- F4: one weekly pack waiting for a decision (shapes = PackView, PackRow, ApprovalReport) -----------------------
const TITLES = [
  "Weekly finance pack — W45",
  "The week at a glance",
  "Billing beat the budget by 3.2%",
  "Collections slowed",
  "Two budget misses",
  "Receivables ageing",
  "Overdue customers",
  "Tariff checks",
  "Suez transits",
  "Appendix",
];
function freshPack() {
  return {
    thread_id: "weekly_pack:live:2025-W45:1",
    week: 45,
    sha: 1,
    published: false,
    rejected: false,
    log: [],
    bullets: [
      { slide: 2, text: "Billing reached 8,412,300.50 SDR.", evidence_ids: ["kpi.weekly"] },
      { slide: 2, text: "Collections were 3,402,118.20 SDR.", evidence_ids: ["kpi.weekly"] },
      { slide: 3, text: "Billing was 262,300.50 SDR above budget.", evidence_ids: ["kpi.weekly"] },
      { slide: 3, text: "Year to date billing is 101.8% of budget.", evidence_ids: ["audit.ytd"] },
      { slide: 4, text: "Collections fell 4.1% week on week.", evidence_ids: ["kpi.weekly"] },
    ],
  };
}
let pack = freshPack();
const packStatus = () => (pack.rejected ? "rejected" : pack.published ? "published" : "awaiting_approval");
const packView = (me) => ({
  draft_sha: SHA(),
  thread_id: pack.thread_id,
  status: packStatus(),
  next: pack.published || pack.rejected ? [] : ["approval"],
  week: pack.week,
  readiness: [],
  validator_problems:
    pack.published || pack.rejected
      ? []
      : [
          {
            rule: "V2",
            slide: 3,
            bullet: 3,
            token: "101.8%",
            message: "check that week 53 is not counted in this year",
          },
        ],
  degraded: false,
  draft: {
    title: "PortPilot Weekly Finance Pack — W45 — Draft for approval",
    slide_titles: TITLES.map((title, i) => ({ slide: i + 1, title })),
    bullets: pack.bullets,
  },
  has_preview: !pack.rejected,
  decisions: pack.published || pack.rejected ? [] : ["approve", "edit", "reject"],
  approval_log: pack.log,
  form_fixes: 0,
  published: pack.published,
  publication_sync: "synced",
  insight: {
    summary: [
      { text: "Billing beat the budget for the third week running." },
      { text: "Collections slowed." },
    ],
    drivers: [],
    context: [],
    caveats: [],
  },
  charts: {},
  redrafted: false,
  revision: null,
  allowed: {
    decide: me.products.packs_decide && !pack.published && !pack.rejected,
    addition_slides: [3, 4, 5, 6, 7, 8, 9],
    max_additions: 2,
    max_chart_changes: 3,
    max_analysis_edits: 10,
    max_steer_chars: 300,
    revise_left: 2,
  },
  charts_drawn: {
    3: [
      {
        name: "chart:trend",
        type: "line",
        categories: ["W40", "W41", "W42", "W43", "W44", "W45"],
        series: [
          { name: "Billed", values: [8.2, 7.8, 8.5, 8.3, 8.1, 8.41] },
          { name: "Budget", values: [8.1, 8.15, 8.15, 8.15, 8.15, 8.15] },
        ],
        fmt: "M",
        highlight: null,
      },
    ],
  },
});
function applyStep(step) {
  for (const e of step.edits ?? [])
    if (pack.bullets[e.bullet]) pack.bullets[e.bullet] = { ...pack.bullets[e.bullet], text: e.text };
  for (const a of step.additions ?? [])
    pack.bullets.push({ slide: a.slide, text: a.text, evidence_ids: [], origin: "approver" });
  const outcome = { approve: "approved", reject: "rejected", edit: "edited", revise: "revised" }[
    step.decision
  ];
  if (step.decision === "approve") pack.published = true;
  if (step.decision === "reject") pack.rejected = true;
  pack.sha += 1;
  pack.log.push({ at: now(), outcome, decision: step.decision });
}
function packRun(res, me, answer, steps = []) {
  const runId = randomUUID();
  const events = [
    { event: "started", data: { thread_id: pack.thread_id, graph: "weekly_pack" } },
    { event: "node", data: { name: "validator", phase: "start" } },
    ...(steps.some((s) => s.decision === "edit")
      ? [
          {
            event: "approval_needed",
            data: { thread_id: pack.thread_id, decisions: ["approve", "edit", "reject"] },
          },
        ]
      : []),
    {
      event: "answer",
      data: {
        thread: pack.thread_id,
        status: "ok",
        answer,
        not_permitted: [],
        evidence: {},
        problems: [],
        stop_reason: null,
        model_calls: 0,
        cached: 0,
        view: null,
        numbers: [],
      },
    },
    { event: "done", data: { status: "ok" } },
  ].map((e, i) => ({ id: i + 1, ...e }));
  runsById.set(runId, {
    events,
    owner: me.employee_id,
    result: events.at(-2).data,
    thread: pack.thread_id,
    kind: answer ? "pack_request" : "pack_decision",
  });
  send(res, 202, {
    run_id: runId,
    thread_id: pack.thread_id,
    events_url: `/api/v1/runs/${runId}/events`,
    run_url: `/api/v1/runs/${runId}`,
  });
}
const SHA = () => String(pack.sha).padStart(16, "0");

async function packRoutes(req, res, url, me) {
  const p = url.pathname.replace("/api/v1", "");
  if (!p.startsWith("/packs")) return false;
  if (!me.products.packs_read) {
    send(res, 403, { title: "the weekly finance pack is Finance data (level 2)" });
    return true;
  }
  if (p === "/packs") {
    send(res, 200, [
      {
        thread_id: pack.thread_id,
        week: pack.week,
        attempt: 1,
        state: pack.published || pack.rejected ? "ended" : "pending",
        status: packStatus(),
        last_at: now(),
      },
    ]);
    return true;
  }
  if (p === "/packs/report") {
    const edited = pack.log.filter((l) => l.outcome === "edited").length;
    send(res, 200, {
      packs_decided: pack.published || pack.rejected ? 1 : 0,
      published: pack.published ? 1 : 0,
      rejected: pack.rejected ? 1 : 0,
      packs_edited: edited ? 1 : 0,
      edit_rate: pack.published || pack.rejected ? (edited ? 1 : 0) : null,
      decisions: {},
      edited_slides: {},
      changes: {
        text_edits: edited,
        additions: 0,
        chart_changes: 0,
        analysis_edits: 0,
        steers: 0,
        revises: 0,
        revises_restored: 0,
      },
      form_fixes: { packs: 0, fixes: 0 },
      degraded: 0,
      threads: [pack.thread_id],
    });
    return true;
  }
  const m = /^\/packs\/([^/]+)(\/.*)?$/.exec(p);
  if (!m || decodeURIComponent(m[1]) !== pack.thread_id) {
    send(res, 404, { title: "no such pack" });
    return true;
  }
  const rest = m[2] ?? "";
  if (rest === "" && req.method === "GET") {
    send(res, 200, packView(me));
    return true;
  }
  if (rest === "/preview") {
    res.writeHead(200, {
      "content-type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
      "content-disposition": 'attachment; filename="preview.pptx"',
    });
    res.end("PK mock pptx");
    return true;
  }
  if (req.method !== "POST") {
    send(res, 405, { title: "method not allowed" });
    return true;
  }
  if (!me.products.packs_decide) {
    send(res, 403, { title: "a Finance manager or the CEO" });
    return true;
  }
  if (pack.published || pack.rejected) {
    send(res, 409, { title: "the pack no longer waits for a decision" });
    return true;
  }
  const body = await readJson(req);
  if (rest === "/decision") {
    if (body?.draft_sha !== SHA()) {
      send(res, 409, { title: "stale: the pack changed; reload and review it" });
      return true;
    }
    applyStep(body);
    packRun(res, me, null, [body]);
    return true;
  }
  if (rest === "/request") {
    packRun(res, me, {
      understood: `Change bullet 3 as you asked: “${body.request}”`,
      steps: [
        {
          decision: "edit",
          edits: [{ bullet: 3, text: "Year to date billing is 101.8% of budget (weeks 1–45)." }],
        },
      ],
      ask_back: null,
      draft_sha: SHA(),
      reread_text: false,
      model_calls: 1,
    });
    return true;
  }
  if (rest === "/request/confirm") {
    if (body?.proposal?.draft_sha !== SHA()) {
      send(res, 409, { title: "stale: the draft changed since the request was understood" });
      return true;
    }
    for (const step of body.proposal.steps) applyStep(step);
    packRun(res, me, null, body.proposal.steps);
    return true;
  }
  send(res, 404, { title: "not found" });
  return true;
}

// --- F5: the chart catalogue, the finance weeks, the views (shapes = ChartCatalogue, FinanceWeek, ViewSpec) ---------
const CATALOGUE = {
  pack: {
    charts: ["trend", "variance"],
    fixed: ["aging", "overdue_flow", "suez"],
    defaults: {},
    trend: {
      series: {
        billed_sdr: { name: "Billed", unit: "SDR" },
        budget_sdr: { name: "Budget", unit: "SDR" },
        collected_sdr: { name: "Collected", unit: "SDR" },
        dso_days: { name: "DSO", unit: "days" },
      },
      weeks: [4, 8, 13, 26],
      max_series: 3,
    },
    variance: {
      measure: {
        budget_variance_sdr: { name: "Billed − budget", unit: "SDR" },
        budget_variance_pct: { name: "Billed vs budget %", unit: "%" },
      },
      rows: ["all", "top5", "bottom5"],
    },
  },
  views: {
    kinds: ["trend", "category", "aging", "customers"],
    options: {
      trend: ["series", "weeks"],
      category: ["measure", "rows", "compare_week"],
      aging: ["compare_week"],
      customers: ["measure"],
    },
    category: {
      billed_sdr: { name: "Billed", unit: "SDR" },
      budget_variance_pct: { name: "Billed vs budget %", unit: "%" },
    },
    aging: [
      { field: "aging_current_sdr", name: "Current" },
      { field: "aging_1_30_sdr", name: "1–30 days" },
    ],
    customers: { share_13w_pct: { name: "Share of billing", unit: "%" } },
  },
};
const WEEKS = Array.from({ length: 45 }, (_, i) => ({
  report_week: i + 1,
  iso_week_label: `2025-W${String(i + 1).padStart(2, "0")}`,
  week_end: "2025-01-05",
  is_warmup: i < 4,
}));
function viewFor(choice) {
  if (choice.kind === "trend") {
    const n = choice.weeks ?? 13;
    const cats = Array.from(
      { length: n },
      (_, i) => `2025-W${String(choice.week - n + 1 + i).padStart(2, "0")}`,
    );
    const series = (choice.series ?? ["billed_sdr"]).map((s, k) => ({
      name: CATALOGUE.pack.trend.series[s]?.name ?? s,
      values: cats.map((_, i) => (i === 2 ? null : 8_000_000 + k * 150_000 + i * 20_000)),
    }));
    return {
      choice,
      categories: cats,
      series,
      unit: "SDR",
      caption: `${series.map((s) => s.name).join(" and ")}, ${n} weeks to 2025-W${choice.week}`,
      sources: [{ view: "finance.kpi_weekly_trend", filter: `report_week = ${choice.week}` }],
    };
  }
  return {
    choice,
    categories: ["Container", "Tanker", "Bulk", "Ro-Ro", "Cruise"],
    series: [
      {
        name: choice.measure === "budget_variance_pct" ? "Billed vs budget %" : "Billed",
        values: [4.2, -1.3, 2.8, 0.6, -3.1],
      },
    ],
    unit: choice.measure === "billed_sdr" ? "SDR" : "%",
    caption: `By vessel category, 2025-W${choice.week}`,
    sources: [{ view: "finance.kpi_weekly_category", filter: `report_week = ${choice.week}` }],
  };
}

async function viewRoutes(req, res, url, me) {
  const p = url.pathname.replace("/api/v1", "");
  if (p === "/charts/catalogue") {
    send(res, 200, CATALOGUE);
    return true;
  }
  if (p === "/finance/weeks") {
    if (!me.tools.includes("finance_kpi"))
      send(res, 403, { title: "the finance dashboard is Finance data (level 2)" });
    else send(res, 200, WEEKS);
    return true;
  }
  if (p !== "/views" || req.method !== "POST") return false;
  if (!me.tools.includes("finance_kpi")) {
    send(res, 403, { title: "views are Finance data (level 2)" });
    return true;
  }
  const body = await readJson(req);
  if (body?.choice) {
    send(res, 200, viewFor(body.choice));
    return true;
  }
  const q = String(body?.question ?? "");
  const m = /(?:week|W|أسبوع)\s*(\d{1,2})/i.exec(q);
  const view = m
    ? viewFor({ kind: "category", week: Number(m[1]), measure: "budget_variance_pct", rows: "top5" })
    : null;
  const runId = randomUUID();
  const answer = {
    thread: null,
    status: view ? "answered" : "ask_back",
    answer: view ? view.caption : "Which week of 2025 should the chart show?",
    not_permitted: [],
    evidence: {},
    problems: [],
    stop_reason: null,
    model_calls: 1,
    cached: 0,
    view,
    numbers: [],
  };
  const events = [
    { event: "started", data: { thread_id: null, graph: "view" } },
    { event: "answer", data: answer },
    { event: "done", data: { status: answer.status } },
  ].map((e, i) => ({ id: i + 1, ...e }));
  runsById.set(runId, { events, owner: me.employee_id, result: answer, thread: null, kind: "view" });
  send(res, 202, {
    run_id: runId,
    thread_id: null,
    events_url: `/api/v1/runs/${runId}/events`,
    run_url: `/api/v1/runs/${runId}`,
  });
  return true;
}

// --- F5b: the finance dashboard reads (shapes = FinanceRows, AuditRows, PackDashboard) -----------------------------
function financeRows(dataset, week) {
  const src = (view) => ({ kind: "view", name: view, filter: `report_week = ${week}` });
  if (dataset === "weekly")
    return {
      dataset,
      status: "ok",
      note: null,
      source: src("finance.kpi_weekly"),
      rows: [
        {
          report_week: week,
          iso_week_label: `2025-W${week}`,
          is_warmup: false,
          billed_sdr: 8394785.98,
          collected_sdr: 3611204.75,
          ar_sdr: 38674926.1,
          overdue_sdr: 10250856.93,
          dso_days: 41.2,
          budget_variance_pct: 3.4,
          billed_wow_pct: 2.1,
          collected_wow_pct: -4.1,
          ar_wow_pct: 0.8,
          overdue_wow_pct: 6.3,
          dso_wow_days: 0.4,
          aging_current_sdr: 20100000,
          aging_1_30_sdr: 8300000,
          aging_31_60_sdr: 5100000,
          aging_61_90_sdr: 3200000,
          aging_90_plus_sdr: 1974926.1,
          overdue_new_sdr: 1200000,
          overdue_paid_sdr: 600000,
          billed_13w_sdr: 104000000,
          budget_variance_13w_pct: 1.8,
          ontime_13w_pct: 71.5,
        },
      ],
    };
  if (dataset === "category")
    return {
      dataset,
      status: "ok",
      note: null,
      source: src("finance.kpi_weekly_category"),
      rows: [
        ["Container", 3100000, 2900000, 200000, 310000],
        ["Tanker", 2200000, 2300000, -100000, -150000],
        ["Bulk", 1500000, 1450000, 50000, 90000],
      ].map(([c, b, bud, v, ch]) => ({
        report_week: week,
        vessel_category: c,
        billed_sdr: b,
        budget_sdr: bud,
        budget_variance_sdr: v,
        billed_wow_change_sdr: ch,
      })),
    };
  if (dataset === "customers")
    return {
      dataset,
      status: "ok",
      note: null,
      source: src("finance.kpi_customer_13w"),
      rows: [
        {
          customer_id: 34,
          customer_name: "Delta Lines",
          share_13w_pct: 12.4,
          rank_13w: 1,
          ar_sdr: 4100000,
          overdue_sdr: 900000,
          is_watchlist: false,
        },
        {
          customer_id: 12,
          customer_name: "Red Sea Shipping",
          share_13w_pct: 9.8,
          rank_13w: 2,
          ar_sdr: 3300000,
          overdue_sdr: 1500000,
          is_watchlist: true,
        },
      ],
    };
  if (dataset === "overdue")
    return {
      dataset,
      status: "ok",
      note: null,
      source: src("finance.kpi_overdue_list"),
      rows: [
        {
          invoice_number: "INV-0004512",
          customer_name: "Red Sea Shipping",
          amount_sdr: 410000,
          days_past_due: 64,
        },
        {
          invoice_number: "INV-0004480",
          customer_name: "Delta Lines",
          amount_sdr: 220000,
          days_past_due: 31,
        },
      ],
    };
  return {
    dataset: "trend",
    status: "ok",
    note: null,
    source: src("finance.kpi_weekly_trend"),
    rows: Array.from({ length: 13 }, (_, i) => ({
      trend_week: week - 12 + i,
      trend_week_label: `2025-W${String(week - 12 + i).padStart(2, "0")}`,
      billed_sdr: 7800000 + i * 50000,
      budget_sdr: 8000000,
      collected_sdr: 3400000 + i * 20000,
    })),
  };
}

async function financeRoutes(req, res, url, me) {
  const p = url.pathname.replace("/api/v1", "");
  if (!p.startsWith("/finance/") || p === "/finance/weeks") return false;
  if (!me.tools.includes("finance_kpi")) {
    send(res, 403, { title: "the finance dashboard is Finance data (level 2)" });
    return true;
  }
  const week = Number(url.searchParams.get("week"));
  if (!(week >= 1 && week <= 52)) {
    send(res, 422, { title: "week is 1 to 52" });
    return true;
  }
  if (p === "/finance/pack") {
    if (week !== 45) send(res, 404, { title: "no published pack for that week" });
    else
      send(res, 200, {
        week,
        thread_id: "weekly_pack:live:2025-W45:1",
        approved_at: "2025-11-10T09:12:00+00:00",
        publication_sync: "synced",
        approver_employee_id: 6,
        summary: ["Billing reached 8,412,300.50 SDR.", "Collections were 3,402,118.20 SDR."],
        charts: [
          {
            choice: { kind: "trend", week: 45, series: ["billed_sdr", "budget_sdr"], weeks: 13 },
            categories: ["2025-W43", "2025-W44", "2025-W45"],
            series: [
              { name: "Billed", values: [8.3e6, 8.1e6, 8.41e6] },
              { name: "Budget", values: [8.15e6, 8.15e6, 8.15e6] },
            ],
            unit: "SDR",
            caption: "Billed and budget, 13 weeks to 2025-W45",
            sources: [],
          },
        ],
        degraded: false,
      });
    return true;
  }
  if (p === "/finance/invoice-audit") {
    send(res, 200, {
      status: "ok",
      note: "41 invoices checked, 2 flagged",
      source: { kind: "view", name: "finance.invoice_audit", filter: `report_week = ${week}` },
      rows: [
        {
          invoice_number: "INV-0004601",
          check_code: "TOLL_BAND",
          probable_cause: "billed on the wrong toll band",
          difference_sdr: 1200.5,
        },
        {
          invoice_number: "INV-0004633",
          check_code: "DUPLICATE",
          probable_cause: "same vessel and date billed twice",
          difference_sdr: 8800,
        },
      ],
      invoices_checked: 41,
      invoices_flagged: 2,
      amount_at_stake_sdr: 10000.5,
      findings_by_check: { TOLL_BAND: 1, DUPLICATE: 1 },
      invoices_manual_review: 1,
    });
    return true;
  }
  const dataset = p.slice("/finance/".length);
  if (!["weekly", "category", "customers", "overdue", "trend"].includes(dataset)) {
    send(res, 422, { title: "unknown dataset" });
    return true;
  }
  send(res, 200, financeRows(dataset, week));
  return true;
}

async function chatRoutes(req, res, url, me) {
  const p = url.pathname.replace("/api/v1", "");
  if (p === "/conversations" && req.method === "POST") {
    const c = {
      conversation_id: randomUUID(),
      employee_id: me.employee_id,
      created_at: now(),
      last_turn_at: null,
      closed_at: null,
      turns: [],
    };
    conversations.set(c.conversation_id, c);
    send(res, 201, summary(c));
    return true;
  }
  if (p === "/conversations" && req.method === "GET") {
    send(res, 200, [...conversations.values()].filter((c) => c.employee_id === me.employee_id).map(summary));
    return true;
  }
  let m = /^\/conversations\/([^/]+)$/.exec(p);
  if (m && req.method === "GET") {
    const c = conversations.get(m[1]);
    if (!c || c.employee_id !== me.employee_id)
      return (send(res, 404, { title: "no such conversation" }), true);
    send(res, 200, c);
    return true;
  }
  m = /^\/conversations\/([^/]+)\/questions$/.exec(p);
  if (m && req.method === "POST") {
    const c = conversations.get(m[1]);
    if (!c || c.employee_id !== me.employee_id)
      return (send(res, 404, { title: "no such conversation" }), true);
    const body = await readJson(req);
    const question = String(body?.question ?? "");
    const runId = randomUUID();
    const thread = `ask:${me.employee_id}:${runId.slice(0, 8)}`;
    const answer = { ...answerFor(me, question), thread };
    const finance = me.tools.includes("finance_kpi");
    const events = [
      { event: "started", data: { thread_id: thread, graph: "ask" } },
      { event: "understood", data: { standalone_question: question, used_entities: {}, by: "code" } },
      ...(finance
        ? [
            { event: "node", data: { name: "model", phase: "start" } },
            { event: "tool_called", data: { name: "finance_kpi" } },
          ]
        : [{ event: "tool_refused", data: { name: "finance_kpi", part: "finance figures" } }]),
      { event: "answer", data: answer },
      { event: "done", data: { status: answer.status } },
    ].map((e, i) => ({ id: i + 1, ...e }));
    runsById.set(runId, { events, owner: me.employee_id, result: answer, thread });
    questions.set(thread, { ...answer, question });
    c.turns.push({
      turn_no: c.turns.length + 1,
      question,
      standalone_question: question,
      resolved_by: "none",
      lang: /[؀-ۿ]/.test(question) ? "ar" : "en",
      as_of: now(),
      status: answer.status,
      thread_id: thread,
    });
    c.last_turn_at = now();
    send(res, 202, {
      run_id: runId,
      thread_id: thread,
      events_url: `/api/v1/runs/${runId}/events`,
      run_url: `/api/v1/runs/${runId}`,
    });
    return true;
  }
  m = /^\/runs\/([^/]+)\/events$/.exec(p);
  if (m) {
    const r = runsById.get(m[1]);
    if (!r || r.owner !== me.employee_id) return (send(res, 404, { title: "no such run" }), true);
    const after = Number(req.headers["last-event-id"] ?? 0);
    sse(
      res,
      r.events.filter((e) => e.id > after),
    );
    return true;
  }
  m = /^\/runs\/([^/]+)$/.exec(p);
  if (m) {
    const r = runsById.get(m[1]);
    if (!r || r.owner !== me.employee_id) return (send(res, 404, { title: "no such run" }), true);
    send(res, 200, {
      run_id: m[1],
      kind: r.kind ?? "ask",
      state: "done",
      thread_id: r.thread,
      conversation_id: null,
      created_at: now(),
      finished_at: now(),
      result: r.result,
      error: null,
      events: r.events,
    });
    return true;
  }
  m = /^\/questions\/([^/]+)$/.exec(p);
  if (m) {
    const q = questions.get(decodeURIComponent(m[1]));
    if (!q || !q.thread.startsWith(`ask:${me.employee_id}:`))
      return (send(res, 404, { title: "no such question" }), true);
    send(res, 200, q);
    return true;
  }
  m = /^\/conversations\/([^/]+)\/uploads$/.exec(p);
  if (m && req.method === "GET") {
    send(res, 200, uploads.get(m[1]) ?? []);
    return true;
  }
  if (m && req.method === "POST") {
    await new Promise((resolve) => req.resume().on("end", resolve)); // drain the multipart body
    const doc = {
      document_id: randomUUID(),
      document_code: "UPL-0001",
      title: "Berth schedule",
      filename: "berth.pdf",
      chunks: 4,
      removed: 0,
    };
    uploads.set(m[1], [...(uploads.get(m[1]) ?? []), doc]);
    send(res, 201, {
      accepted: true,
      filename: doc.filename,
      document_id: doc.document_id,
      document_code: doc.document_code,
      title: doc.title,
      chunks: 4,
      reasons: [],
      removed: [],
      notes: [],
      message: "Accepted: 4 passages are searchable in this conversation.",
    });
    return true;
  }
  return false;
}

// --- F6: route advice (runs + stored threads) and the voyage watch (two saved runs) -------------------------------
// Shapes = RouteAdviceDetail, ThreadRow, WatchAlerts, WatchRunDetail, WatchRunRow (docs/api/openapi.json).
function spansAt(text, items) {
  // fixtures only: each number's first place after the previous one (the real API returns the slots' offsets)
  let from = 0;
  return items.map(([num, field, evidence_id, source = evidence_id, filter = null, row = 0]) => {
    const start = text.indexOf(num, from);
    if (start < 0) throw new Error(`fixture: ${num} not in ${text}`);
    from = start + num.length;
    return { text: num, start, end: from, evidence_id, field, source, filter, row };
  });
}
const ROUTE_ROWS = {
  suez: {
    route: "suez",
    passages: ["Suez Canal", "Bab-el-Mandeb"],
    distance_nm: 10525,
    speed_kn: 14,
    sea_days: 31.32,
    fuel_t_per_day: 38.5,
    fuel_t: 1205.8,
    fuel_sdr: 512465.0,
    suez_dues_sdr: 98412.36,
    total_sdr: 610877.36,
  },
  cape: {
    route: "cape",
    passages: ["Cape of Good Hope"],
    distance_nm: 13892,
    speed_kn: 14,
    sea_days: 41.35,
    fuel_t_per_day: 38.5,
    fuel_t: 1592.0,
    fuel_sdr: 676600.0,
    suez_dues_sdr: 0,
    total_sdr: 676600.0,
  },
  difference: {
    route: "difference",
    change_distance_nm: 3367,
    change_sea_days: 10.03,
    change_fuel_t: 386.2,
    change_fuel_sdr: 164135.0,
    change_total_sdr: 65722.64,
    change_dues_sdr: -98412.36,
    cheaper_route: "suez",
  },
};
function adviceFor(body) {
  const base = {
    model_calls: 1,
    cached: 0,
    sources: [
      "route.suez: sea_route ok — searoute (via Suez)",
      "route.cape: sea_route ok — searoute (via the Cape)",
      "route.dues: suez_toll ok — Suez Canal tariff 2025 (Containerships, Laden)",
    ],
    problems: [],
  };
  if (body.origin === "GRPIR")
    return {
      ...base,
      status: "no_suez_on_route",
      recommendation: null,
      headline: `The Suez Canal is not on the voyage ${body.origin} → ${body.destination}.`,
      comparison: [{ ...ROUTE_ROWS.suez, route: "direct", passages: [], suez_dues_sdr: 0 }],
      reasons: null,
      risks: null,
      assumptions: ["Sea distance by the searoute network."],
      numbers: { headline: [], reasons: [], risks: [] },
      model_calls: 0,
    };
  const headline = "Via Suez saves 65,722.64 SDR and 10.03 days on this voyage.";
  const reasons = [
    "The Suez route is 3,367 nm shorter, so it burns 386.2 t less fuel.",
    "Suez dues of 98,412.36 SDR are smaller than the 164,135.00 SDR of extra fuel via the Cape.",
  ];
  const risks = ["Suez transits are 2.7 % above a year earlier; no closure is in the news."];
  return {
    ...base,
    status: "ok",
    recommendation: "suez",
    headline,
    comparison: [ROUTE_ROWS.suez, ROUTE_ROWS.cape, ROUTE_ROWS.difference],
    reasons,
    risks,
    assumptions: [
      "Speed 14.0 kn (the vessel's service speed); fuel 38.5 t per sea day.",
      "Fuel priced at 425.00 SDR per tonne (bunker_prices, the clock's month).",
    ],
    numbers: {
      headline: spansAt(headline, [
        ["65,722.64 SDR", "change_total_sdr", "route.difference"],
        ["10.03", "change_sea_days", "route.difference"],
      ]),
      reasons: [
        spansAt(reasons[0], [
          ["3,367 nm", "change_distance_nm", "route.difference"],
          ["386.2 t", "change_fuel_t", "route.difference"],
        ]),
        spansAt(reasons[1], [
          ["98,412.36 SDR", "suez_dues_sdr", "route.compare", "route.compare", "route = suez", 0],
          ["164,135.00 SDR", "change_fuel_sdr", "route.difference"],
        ]),
      ],
      risks: [spansAt(risks[0], [["2.7 %", "change_transits_pct", "route.traffic"]])],
    },
  };
}
const advice = new Map(); // thread -> {owner, last_at, detail}
function seedAdvice() {
  advice.clear();
  const t = "route_advice:41:2026-09-13:CNSHA-NLRTM:1";
  advice.set(t, { owner: 41, last_at: "2026-09-13T08:00:00Z", detail: { thread_id: t, ...adviceFor({}) } });
}
seedAdvice();

const WATCH_ALERTS = [
  [
    "234/weather",
    234,
    "Cruise Voyager 234",
    "NOFRK",
    "2026-09-21T08:19Z",
    "weather",
    "high",
    "waves 7.58 m ≥ 4.0 m; wind 40.2 kn ≥ 34.0 kn",
  ],
  [
    "339/weather",
    339,
    "Petroleum Voyager 339",
    "AOSZA",
    "2026-10-01T22:02Z",
    "weather",
    "high",
    "waves 6.26 m ≥ 4.0 m",
  ],
  [
    "420/weather",
    420,
    "Containerships Voyager 420",
    "WSAPW",
    "2026-09-29T12:01Z",
    "weather",
    "high",
    "waves 6.80 m ≥ 4.0 m",
  ],
  [
    "118/suez_traffic",
    118,
    "Dry Bulk Voyager 118",
    "ITGOA",
    "2026-09-18T03:40Z",
    "suez_traffic",
    "moderate",
    "Suez Canal ahead; transits -21.4 % vs a year earlier ≤ -20 %",
  ],
  [
    "205/customer",
    205,
    "Containerships Voyager 205",
    "EGPSD",
    "2026-09-15T14:10Z",
    "customer",
    "moderate",
    "a customer with overdue invoices has cargo on board",
  ],
].map(([alert_id, vessel_id, vessel_name, destination, eta_utc, kind, severity, reason]) => ({
  alert_id,
  vessel_id,
  vessel_name,
  destination,
  eta_utc,
  kind,
  severity,
  reason,
  customer_id: kind === "customer" ? 7 : null,
}));
const WATCH_HEADLINE =
  "5 alerts on the next legs, 3 high: Cruise Voyager 234 meets waves of 7.6 m on 2026-09-16.";
const WATCH_ITEMS = [
  "Cruise Voyager 234 (to NOFRK, ETA 2026-09-21T08:19Z) meets waves of 7.6 m and wind of 40.2 kn on 2026-09-16.",
  "Petroleum Voyager 339 (to AOSZA, ETA 2026-10-01T22:02Z) meets waves of 6.3 m on 2026-09-15.",
];
const watchRuns = {
  "voyage_watch:20260913T0000Z:1": {
    as_of: "2026-09-13T00:00Z",
    last_at: "2026-09-13T00:04:00Z",
    alerts: WATCH_ALERTS,
    brief_status: "ok",
    headline: WATCH_HEADLINE,
    items: WATCH_ITEMS,
    numbers: {
      headline: spansAt(WATCH_HEADLINE, [
        ["5", "alerts_total", "watch.fleet"],
        ["3", "alerts_high", "watch.fleet"],
        ["7.6", "wave_height_max_m", "watch.alerts", "watch.alerts", "alert = 234/weather", 0],
      ]),
      items: [
        spansAt(WATCH_ITEMS[0], [
          ["7.6", "wave_height_max_m", "watch.alerts", "watch.alerts", "alert = 234/weather", 0],
          ["40.2", "wind_speed_10m_max_kn", "watch.alerts", "watch.alerts", "alert = 234/weather", 0],
        ]),
        spansAt(WATCH_ITEMS[1], [
          ["6.3", "wave_height_max_m", "watch.alerts", "watch.alerts", "alert = 339/weather", 1],
        ]),
      ],
    },
    fleet: {
      vessels_watched: 297,
      in_transit: 219,
      anchored: 78,
      alerts_total: 5,
      alerts_high: 3,
      alerts_moderate: 2,
      suez_ahead_vessels: 40,
      weather_points: 810,
      weather_unknown_points: 5,
      change_transits_pct: 2.7,
    },
  },
  "voyage_watch:20260912T1200Z:1": {
    as_of: "2026-09-12T12:00Z",
    last_at: "2026-09-12T12:03:00Z",
    alerts: WATCH_ALERTS.slice(3),
    brief_status: "skipped_no_high",
    headline: null,
    items: [],
    numbers: { headline: [], items: [] },
    fleet: {
      vessels_watched: 295,
      in_transit: 216,
      anchored: 79,
      alerts_total: 2,
      alerts_high: 0,
      alerts_moderate: 2,
      suez_ahead_vessels: 38,
      weather_points: 804,
      weather_unknown_points: 3,
      change_transits_pct: 2.5,
    },
  },
};
// the run's ETA table (rule R): the five alerted vessels + nine more at sea, one at port (no ETA)
const ETAS = [
  [234, "Cruise Voyager 234", "ISREY", "NOFRK", "2026-09-21T08:19Z", 200.3, 3120.4, 15.6, false],
  [339, "Petroleum Voyager 339", "MUPLU", "AOSZA", "2026-10-01T22:02Z", 454.0, 5902.0, 13.0, false],
  [420, "Containerships Voyager 420", "FJSUV", "WSAPW", "2026-09-29T12:01Z", 396.0, 6732.0, 17.0, false],
  [118, "Dry Bulk Voyager 118", "EGSUZ", "ITGOA", "2026-09-18T03:40Z", 123.7, 1608.1, 13.0, true],
  [205, "Containerships Voyager 205", "EGPSD", "EGPSD", "2026-09-15T14:10Z", 62.2, 932.5, 15.0, false],
  ...Array.from({ length: 9 }, (_, i) => [
    501 + i,
    `Dry Bulk Voyager ${501 + i}`,
    "SGSIN",
    "NLRTM",
    `2026-09-${String(14 + i).padStart(2, "0")}T06:00Z`,
    30 + i * 24,
    360 + i * 300,
    12.5,
    false,
  ]),
].map(
  ([
    vessel_id,
    vessel_name,
    next_port,
    destination,
    eta_utc,
    eta_in_h,
    distance_left_nm,
    speed_kn,
    suez_ahead,
  ]) => ({
    vessel_id,
    vessel_name,
    status: "In Transit",
    destination,
    next_port,
    eta_utc,
    eta_in_h,
    distance_left_nm,
    speed_kn,
    suez_ahead,
    last_fix_ts: "2026-09-12T23:50:04Z",
    note: null,
  }),
);
ETAS.push({
  ...ETAS[13],
  vessel_id: 600,
  vessel_name: "Cruise Voyager 600",
  status: "At Port",
  eta_utc: null,
  eta_in_h: null,
});
const LATEST_WATCH = "voyage_watch:20260913T0000Z:1";

function routeRun(res, me, thread, detail) {
  const graph = [
    "inputs",
    "routes",
    "costs",
    "context",
    ...(detail.status === "ok" ? ["advisor", "validator"] : []),
    "render",
  ];
  const events = [
    { event: "started", data: { thread_id: thread, graph: "route_advice" } },
    ...graph.flatMap((name) => [
      { event: "node", data: { name, phase: "start" } },
      { event: "node", data: { name, phase: "end" } },
    ]),
    {
      event: "answer",
      data: {
        thread,
        status: detail.status,
        answer: detail,
        not_permitted: [],
        evidence: {},
        problems: [],
        stop_reason: null,
        model_calls: detail.model_calls,
        cached: 0,
        view: null,
        numbers: [],
      },
    },
    { event: "done", data: { status: detail.status } },
  ].map((e, i) => ({ id: i + 1, ...e }));
  const runId = randomUUID();
  runsById.set(runId, {
    events,
    owner: me.employee_id,
    result: events.at(-2).data,
    thread,
    kind: "route_advice",
  });
  send(res, 202, {
    run_id: runId,
    thread_id: thread,
    events_url: `/api/v1/runs/${runId}/events`,
    run_url: `/api/v1/runs/${runId}`,
  });
}

async function operationsRoutes(req, res, url, me) {
  const p = url.pathname.replace("/api/v1", "");
  if (p === "/route-advice" || p.startsWith("/route-advice/")) {
    if (!me.products.route_advice) return (send(res, 403, { title: "route advice is not permitted" }), true);
    const mine = (t) => me.role === "ceo" || t.owner === me.employee_id;
    if (p === "/route-advice" && req.method === "GET") {
      const rows = [...advice.entries()]
        .filter(([, t]) => mine(t))
        .map(([thread_id, t]) => ({
          thread_id,
          state: "ended",
          status: t.detail.status,
          last_at: t.last_at,
        }));
      return (send(res, 200, rows), true);
    }
    if (p === "/route-advice" && req.method === "POST") {
      const body = await readJson(req);
      const code = /^[A-Z]{2}[A-Z2-9]{3}$/;
      const vessel = body?.vessel_id != null || (body?.vessel_type && body?.condition && body?.scnt_tons);
      if (!body || !code.test(body.origin ?? "") || !code.test(body.destination ?? "") || !vessel)
        return (send(res, 422, { title: "Invalid request" }), true);
      const pair = `:${me.employee_id}:2026-09-13:${body.origin}-${body.destination}:`;
      const n = [...advice.keys()].filter((k) => k.includes(pair)).length + 1;
      const thread = `route_advice${pair}${n}`;
      const detail = { thread_id: thread, ...adviceFor(body) };
      advice.set(thread, { owner: me.employee_id, last_at: now(), detail });
      routeRun(res, me, thread, detail);
      return true;
    }
    const m = /^\/route-advice\/([^/]+)$/.exec(p);
    if (m && req.method === "GET") {
      const t = advice.get(decodeURIComponent(m[1]));
      if (!t || !mine(t)) return (send(res, 404, { title: "no such route advice" }), true);
      return (send(res, 200, t.detail), true);
    }
    return false;
  }
  if (!p.startsWith("/voyage-watch/")) return false;
  if (p === "/voyage-watch/alerts" && req.method === "GET") {
    if (!me.products.voyage_watch)
      return (
        send(res, 200, { status: "not_permitted", note: "not permitted for this user (ADR-006)" }),
        true
      );
    const thread = url.searchParams.get("thread") ?? LATEST_WATCH;
    const r = watchRuns[thread];
    if (!r) return (send(res, 200, { status: "no_data", note: `no saved watch run for ${thread}` }), true);
    const high = url.searchParams.get("high") === "true";
    const vessel = url.searchParams.get("vessel");
    const alerts = r.alerts.filter(
      (a) => (!high || a.severity === "high") && (vessel === null || String(a.vessel_id) === vessel),
    );
    return (
      send(res, 200, {
        status: "ok",
        thread_id: thread,
        as_of: r.as_of,
        brief_status: r.brief_status,
        headline: r.headline,
        alerts,
        of: r.alerts.length,
      }),
      true
    );
  }
  if (p === "/voyage-watch/runs" && req.method === "GET") {
    const rows = Object.entries(watchRuns).map(([thread_id, r]) => ({
      thread_id,
      state: "ended",
      status: "ok",
      last_at: r.last_at,
      run_as: null,
    }));
    return (send(res, 200, rows), true);
  }
  const m = /^\/voyage-watch\/runs\/([^/]+)$/.exec(p);
  if (m && req.method === "GET") {
    const thread = decodeURIComponent(m[1]);
    const r = watchRuns[thread];
    if (!r) return (send(res, 404, { title: "no such watch run" }), true);
    return (
      send(res, 200, {
        thread_id: thread,
        status: "ok",
        as_of: r.as_of,
        brief_status: r.brief_status,
        fleet: r.fleet,
        headline: r.headline,
        items: r.items,
        alerts: r.alerts.map(
          (a) =>
            `${a.alert_id} ${a.severity} ${a.vessel_name} → ${a.destination} ETA ${a.eta_utc}: ${a.reason}`,
        ),
        assumptions: ["ETA by rule R: the leg's remaining distance at the vessel's recent speed."],
        problems: [],
        run_file: `reports/voyage_watch/${thread.replaceAll(":", "_")}.json`,
        model_calls: r.brief_status === "ok" ? 1 : 0,
        cached: 0,
        numbers: r.numbers,
        etas: ETAS,
      }),
      true
    );
  }
  return false;
}

const send = (res, status, body, headers = {}) => {
  res.writeHead(status, { "content-type": "application/json", ...headers });
  res.end(body === undefined ? "" : JSON.stringify(body));
};
const readJson = (req) =>
  new Promise((resolve) => {
    let raw = "";
    req.on("data", (c) => (raw += c));
    req.on("end", () => {
      try {
        resolve(JSON.parse(raw || "{}"));
      } catch {
        resolve(null);
      }
    });
  });
const bearer = (req) => /^Bearer (.+)$/.exec(req.headers.authorization ?? "")?.[1];

createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (url.pathname.startsWith("/api/v1/") && bearer(req))
    lastByToken.set(`${bearer(req)} ${url.pathname}`, { path: url.pathname, headers: req.headers });

  if (url.pathname === "/__mock/last")
    return send(
      res,
      200,
      lastByToken.get(`${url.searchParams.get("token")} ${url.searchParams.get("path")}`) ?? null,
    );
  if (url.pathname === "/__mock/health" && req.method === "POST") {
    health = (await readJson(req))?.status ?? "ready";
    return send(res, 200, { health });
  }
  if (url.pathname === "/__mock/routes-reset" && req.method === "POST") {
    seedAdvice();
    return send(res, 200, { ok: true });
  }
  if (url.pathname === "/__mock/pack-reset" && req.method === "POST") {
    pack = freshPack();
    return send(res, 200, { ok: true });
  }
  if (url.pathname === "/__mock/reset" && req.method === "POST") {
    failures.clear();
    health = "ready";
    return send(res, 200, { ok: true });
  }

  if (url.pathname === "/api/v1/auth/login" && req.method === "POST") {
    const body = await readJson(req);
    const email = String(body?.email ?? "").toLowerCase();
    if ((failures.get(email) ?? 0) >= 3)
      return send(res, 429, { title: "Too many attempts" }, { "retry-after": "120" });
    const user = users.find((u) => u.email === email && u.password === body?.password);
    if (!user) {
      failures.set(email, (failures.get(email) ?? 0) + 1);
      return send(res, 401, { title: "Email or password is wrong" });
    }
    failures.delete(email);
    const token = `mock_${randomUUID()}`;
    tokens.set(token, user.me);
    return send(res, 200, {
      token,
      token_type: "bearer",
      expires_at: new Date(Date.now() + 8 * 3600_000).toISOString(),
      me: user.me,
    });
  }
  if (url.pathname === "/api/v1/auth/logout" && req.method === "POST") {
    tokens.delete(bearer(req));
    return send(res, 204);
  }
  if (url.pathname === "/api/v1/health/live") return send(res, 200, { status: "live" });

  const me = tokens.get(bearer(req));
  if (!me) return send(res, 401, { title: "Sign in required" });
  if (await packRoutes(req, res, url, me)) return;
  if (await viewRoutes(req, res, url, me)) return;
  if (await financeRoutes(req, res, url, me)) return;
  if (await operationsRoutes(req, res, url, me)) return;
  const chat = await chatRoutes(req, res, url, me);
  if (chat) return;
  if (url.pathname === "/api/v1/me" && req.method === "GET") return send(res, 200, me);
  if (url.pathname === "/api/v1/health/ready" && req.method === "GET") {
    const ok = health === "ready";
    return send(res, ok ? 200 : 503, {
      status: ok ? "ready" : "degraded",
      components: [
        { name: "postgres", ok: true },
        { name: "mongo", ok },
        { name: "qdrant", ok: true },
      ],
      llm_requests_today: { "gemini-3.5-flash-lite": 12 },
    });
  }
  return send(res, 404, { title: "Not found" });
}).listen(PORT, "127.0.0.1", () => console.log(`mock API on http://127.0.0.1:${PORT}`));
