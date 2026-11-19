"""Synthetic port-call messages: the Requested Time of Arrival (RTA) each destination port sends (JIT arrival plan D-J1).

Plan:    dev/history/archive/2026-11-15_JIT_arrival_plan.md §2a D-J1 (approved 2026-11-15, migration 030 approved by the owner).
Run:     uv run python dev/tools/run.py dev/build/synthetic/Port_call_generator.py  (project root)

Reads:   Data/processed/semi-structured/synthetic/voyages_synthetic.parquet (departure, route_nm, service speed only).
Writes:  Data/processed/synthetic/port_calls/port_call_messages.csv + manifest.json, and
         db/migrations/030_port_call_messages.sql (the table + the same rows); never overwrites a file with different
         content.
Re-run:  safe; fixed seed (numpy default_rng([42, 30])).

Why this shape: a real RTA is a port-call message (IMO's Just In Time Arrival Guide; IHO S-211 / DCSA JIT port-call
timestamps): the port (or the agent) tells the vessel when its berth will be ready, the message has a send time, and
it can be revised or cancelled later. The tools read "the latest message sent at or before the clock" — the same rule
for these synthetic rows and for real ones later (`real_or_synthetic = 'real'`), so no code changes for real data.

Phases
1. Inputs: the 500 voyages; the port's view of each = the declared schedule (departure + route / service speed).
   Never `arrival_ts` (the ETA answer key, P9-7).
2. The berth plan: one scenario per port call (on time, berth later, berth much later, berth earlier, cancelled)
   → the RTA, the first message 72–120 h before the scheduled arrival, revisions and cancellations.
3. Save the CSV + manifest (the scenario per call: ground truth for checks only, never a column) + render migration 030.
"""
# %% Setup
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "pyproject.toml").exists() and (p / "Data").is_dir())
sys.path.insert(0, str(ROOT))

VOYAGES = ROOT / "Data" / "processed" / "semi-structured" / "synthetic" / "voyages_synthetic.parquet"
OUT = ROOT / "Data" / "processed" / "synthetic" / "port_calls"
MIGRATION = ROOT / "db" / "migrations" / "030_port_call_messages.sql"
SOURCE = "synthetic: pipelines/scripts/synthetic/Port_call_generator.py (seed 42)"

# scenario → (probability, RTA offset range in hours from the declared scheduled arrival)
SCENARIOS = {"on_time": (0.33, (-1.0, 1.0)), "berth_later": (0.33, (6.0, 72.0)),
             "berth_much_later": (0.10, (96.0, 240.0)), "berth_earlier": (0.20, (-24.0, -3.0)),
             "cancelled": (0.04, (-1.0, 1.0))}
FIRST_LEAD_H = (72.0, 120.0)        # the first RTA reaches the vessel 3–5 days before its scheduled arrival
REVISION_P = 0.30                   # a second message revises the RTA …
REVISION_AFTER_H = (12.0, 36.0)     # … this long after the first,
REVISION_SHIFT_H = (-12.0, 24.0)    # … moving it by this much,
REVISION_LAST_H = 6.0               # … unless it would come later than 6 h before the scheduled arrival
CANCEL_AFTER_H = (6.0, 24.0)
AGENT_P = 0.30                      # the agent, not the port, relays the RTA

# %% Phase 1 — Inputs: the voyages and the declared schedule (the port's view)
voy = pd.read_parquet(VOYAGES).sort_values("vessel_id").reset_index(drop=True)
assert len(voy) == 500 and voy.vessel_id.is_unique
sched = voy.departure_ts + pd.to_timedelta(voy.route_nm / voy.service_kn, unit="h")
print(f"voyages {len(voy)}; scheduled arrivals {sched.min():%Y-%m-%d} … {sched.max():%Y-%m-%d}")
print("✅ Phase 1 validation passed: 500 voyages, one port call each (destination), schedule from route / speed")


# %% Phase 2 — The berth plan → messages
def round_to(t: pd.Timestamp, minutes: int) -> pd.Timestamp:
    return t.round(f"{minutes}min")


rng = np.random.default_rng([42, 30])
names, probs = list(SCENARIOS), [p for p, _ in SCENARIOS.values()]
rows, truth = [], {}
for (_, v), s in zip(voy.iterrows(), sched):
    scen = str(rng.choice(names, p=probs))
    lo, hi = SCENARIOS[scen][1]
    rta = round_to(s + pd.Timedelta(hours=float(rng.uniform(lo, hi))), 30)
    sent = max(v.departure_ts + pd.Timedelta(hours=1),
               s - pd.Timedelta(hours=float(rng.uniform(*FIRST_LEAD_H)))).ceil("1min")
    sender = "agent" if rng.random() < AGENT_P else "port"
    base = {"vessel_id": int(v.vessel_id), "voyage_no": v.voyage_no, "port_locode": v.destination_locode,
            "time_type": "RTA", "location": "berth", "sender": sender, "real_or_synthetic": "synthetic",
            "source": SOURCE}
    msgs = [base | {"requested_time": rta, "sent_at": sent, "message_status": "requested"}]
    revise = rng.random() < REVISION_P
    r_after, r_shift = rng.uniform(*REVISION_AFTER_H), rng.uniform(*REVISION_SHIFT_H)
    c_after = rng.uniform(*CANCEL_AFTER_H)
    if scen == "cancelled":
        msgs.append(base | {"requested_time": rta, "sent_at": round_to(sent + pd.Timedelta(hours=float(c_after)), 1),
                            "message_status": "cancelled"})
    elif revise and sent + pd.Timedelta(hours=float(r_after)) < s - pd.Timedelta(hours=REVISION_LAST_H):
        msgs.append(base | {"requested_time": round_to(rta + pd.Timedelta(hours=float(r_shift)), 30),
                            "sent_at": round_to(sent + pd.Timedelta(hours=float(r_after)), 1),
                            "message_status": "requested"})
    for n, msg in enumerate(msgs, 1):
        rows.append({"message_id": f"PCM-{int(v.vessel_id):03d}-{v.voyage_no}-{n}", **msg})
    truth[int(v.vessel_id)] = scen

msg = pd.DataFrame(rows)[["message_id", "vessel_id", "voyage_no", "port_locode", "time_type", "location",
                          "requested_time", "sent_at", "message_status", "sender", "real_or_synthetic", "source"]]
counts = pd.Series(truth).value_counts().to_dict()
print(f"messages {len(msg)}; calls by scenario {counts}; revised "
      f"{int((msg.groupby('vessel_id').size() == 2).sum() - counts.get('cancelled', 0))}; "
      f"cancelled {int((msg.message_status == 'cancelled').sum())}")
assert msg.message_id.is_unique
assert (msg.sent_at < msg.requested_time).all(), "a message sent after the time it requests"
first = msg.groupby("vessel_id").sent_at.min()
assert (first.values >= (voy.set_index("vessel_id").departure_ts.loc[first.index] + pd.Timedelta(hours=1)).values).all()
assert set(msg.port_locode) <= set(voy.destination_locode)
print("✅ Phase 2 validation passed: unique ids, every message sent before its requested time and after departure")


# %% Phase 3 — Save + the migration (030)
def write_or_verify(path: Path, text: str) -> str:
    data = text.encode("utf-8")
    if path.exists():
        assert path.read_bytes() == data, f"{path.name}: regenerated content differs from the saved file (not written)"
        print(f"{path.relative_to(ROOT).as_posix()}: identical, nothing written")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        print(f"{path.relative_to(ROOT).as_posix()}: written")
    return hashlib.sha256(data).hexdigest()


def iso(t: pd.Timestamp) -> str:
    return t.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


out = msg.copy()
for c in ("requested_time", "sent_at"):
    out[c] = out[c].map(iso)
csv_sha = write_or_verify(OUT / "port_call_messages.csv", out.to_csv(index=False, lineterminator="\n"))


def q(x) -> str:
    return str(x) if isinstance(x, (int, np.integer)) else "'" + str(x).replace("'", "''") + "'"


def lit(r) -> str:
    vals = [q(r.message_id), q(r.vessel_id), q(r.voyage_no), q(r.port_locode), q(r.time_type), q(r.location),
            f"TIMESTAMPTZ '{r.requested_time}'", f"TIMESTAMPTZ '{r.sent_at}'", q(r.message_status), q(r.sender),
            q(r.real_or_synthetic), q(r.source)]
    return "    (" + ", ".join(vals) + ")"


sql = f"""-- =====================================================================
-- 030 — Port-call messages: the Requested Time of Arrival (RTA) a port sends a vessel (JIT arrival plan D-J1)
-- One row per message, the shape of a real port-call message (IMO Just In Time Arrival Guide; IHO S-211 / DCSA JIT
-- port-call timestamps): vessel, port call (vessel + voyage number + port), the time type (RTA), where it applies
-- (berth or pilot boarding place), the requested time, when the message was sent, requested / cancelled, who sent
-- it, real or synthetic, and its source. The RTA known at a clock = the latest message with sent_at <= the clock
-- for that port call; a cancelled latest message = no RTA. A revision is a new row (never an UPDATE).
-- The {len(out)} synthetic rows are generated by pipelines/scripts/synthetic/Port_call_generator.py (seed 42) from
-- each voyage's declared schedule (departure + route / service speed), never from its true arrival (P9-7); real
-- messages later are new rows with real_or_synthetic = 'real'. Never edited after applying.
-- SELECT for the tools through ports_readonly's default privileges (migration 007); not visible to finance_bi.
-- Level 1 / Operations (docs/rbac_mapping.md §2).
-- =====================================================================
BEGIN;

CREATE TABLE public.port_call_messages (
    message_id        text        NOT NULL,
    vessel_id         integer     NOT NULL,
    voyage_no         text        NOT NULL,
    port_locode       varchar(5)  NOT NULL,
    time_type         text        NOT NULL,
    location          text        NOT NULL,
    requested_time    timestamptz NOT NULL,
    sent_at           timestamptz NOT NULL,
    message_status    text        NOT NULL,
    sender            text        NOT NULL,
    real_or_synthetic text        NOT NULL,
    source            text        NOT NULL,
    CONSTRAINT port_call_messages_pkey PRIMARY KEY (message_id),
    CONSTRAINT port_call_messages_vessel_fk FOREIGN KEY (vessel_id) REFERENCES public.vessels (vessel_id),
    CONSTRAINT port_call_messages_port_fk FOREIGN KEY (port_locode) REFERENCES public.ports (locode),
    CONSTRAINT port_call_messages_time_type_chk CHECK (time_type = 'RTA'),
    CONSTRAINT port_call_messages_location_chk CHECK (location IN ('berth', 'pilot_boarding_place')),
    CONSTRAINT port_call_messages_status_chk CHECK (message_status IN ('requested', 'cancelled')),
    CONSTRAINT port_call_messages_sender_chk CHECK (sender IN ('port', 'agent', 'terminal')),
    CONSTRAINT port_call_messages_origin_chk CHECK (real_or_synthetic IN ('real', 'synthetic')),
    CONSTRAINT port_call_messages_order_chk CHECK (sent_at < requested_time)
);
CREATE INDEX port_call_messages_call_idx ON public.port_call_messages (vessel_id, port_locode, voyage_no, sent_at DESC);

COMMENT ON TABLE public.port_call_messages IS 'Port-call messages: the Requested Time of Arrival (RTA) a port or agent sends a vessel; the RTA known at a clock = the latest message with sent_at <= the clock for the port call (JIT arrival plan D-J1); level 1 / Operations (migration 030)';
COMMENT ON COLUMN public.port_call_messages.message_id IS 'the message identifier (synthetic: PCM-<vessel>-<voyage>-<n>)';
COMMENT ON COLUMN public.port_call_messages.vessel_id IS 'the vessel the message is for (FK vessels)';
COMMENT ON COLUMN public.port_call_messages.voyage_no IS 'the voyage number of the port call (the voyage file''s voyage_no)';
COMMENT ON COLUMN public.port_call_messages.port_locode IS 'the port of the call, UN/LOCODE (FK ports)';
COMMENT ON COLUMN public.port_call_messages.time_type IS 'RTA = Requested Time of Arrival (IMO JIT Arrival Guide)';
COMMENT ON COLUMN public.port_call_messages.location IS 'where the requested time applies: berth (all fast) or pilot_boarding_place';
COMMENT ON COLUMN public.port_call_messages.requested_time IS 'the requested time of arrival at the location, UTC';
COMMENT ON COLUMN public.port_call_messages.sent_at IS 'when the message was sent, UTC: a tool at clock t reads only messages with sent_at <= t';
COMMENT ON COLUMN public.port_call_messages.message_status IS 'requested, or cancelled (the call has no RTA from then on)';
COMMENT ON COLUMN public.port_call_messages.sender IS 'port, agent or terminal';
COMMENT ON COLUMN public.port_call_messages.real_or_synthetic IS 'real (a received message) or synthetic (the generator)';
COMMENT ON COLUMN public.port_call_messages.source IS 'where the row comes from (feed, file or generator)';

INSERT INTO public.port_call_messages (message_id, vessel_id, voyage_no, port_locode, time_type, location,
    requested_time, sent_at, message_status, sender, real_or_synthetic, source) VALUES
{",\n".join(lit(r) for r in out.itertuples(index=False))};

COMMIT;
"""
mig_sha = write_or_verify(MIGRATION, sql)
manifest = {"generator": "pipelines/scripts/synthetic/Port_call_generator.py", "plan": "JIT_arrival_plan.md D-J1",
            "seed": "numpy default_rng([42, 30])", "scenarios": {k: {"p": p, "offset_h": list(r)}
                                                                for k, (p, r) in SCENARIOS.items()},
            "rows": len(out), "calls": len(truth), "calls_by_scenario": counts,
            "files": {"port_call_messages.csv": csv_sha, "030_port_call_messages.sql": mig_sha},
            # ground truth for checks only — never a database column
            "scenario_by_vessel": {str(k): v for k, v in sorted(truth.items())}}
write_or_verify(OUT / "manifest.json", json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
back = pd.read_csv(OUT / "port_call_messages.csv")
assert len(back) == len(out) and list(back.columns) == list(out.columns) and back.message_id.is_unique
print(f"csv sha256 {csv_sha[:12]}…, migration sha256 {mig_sha[:12]}…")
print(f"✅ Final Checkpoint: {len(out)} RTA messages for {len(truth)} port calls; CSV + manifest + migration 030 "
      "written or identical; reload equal")
