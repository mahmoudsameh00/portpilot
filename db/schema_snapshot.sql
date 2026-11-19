--
-- PostgreSQL database dump
--

-- Dumped from database version 16.9 (Debian 16.9-1.pgdg110+1)
-- Dumped by pg_dump version 16.9 (Debian 16.9-1.pgdg110+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: agent_state; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA agent_state;


--
-- Name: SCHEMA agent_state; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA agent_state IS 'LangGraph checkpoints of the agents platform (PostgresSaver; Agents plan Phase 5, D3). Tables created by PostgresSaver.setup() as the owner (deployment step); written only through the role agent_writer. Holds level-2 Finance numbers (tool results of a run).';


--
-- Name: api; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA api;


--
-- Name: SCHEMA api; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA api IS 'The NileGate API (FastAPI plan, ADR-064): logins, bearer tokens, conversations with their memory, and the audit log. Written only through the role api_writer; logins are created by the owner (Api_admin.py). Conversation turns hold masked answers (no numbers) and entity frames: level 2 / Finance at rest at most.';


--
-- Name: external; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA external;


--
-- Name: SCHEMA external; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA external IS 'Public external data loaded into the database (level 1), read by the finance views that relate NileGate to the outside world (traffic-billing link plan)';


--
-- Name: finance; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA finance;


--
-- Name: SCHEMA finance; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA finance IS 'Star views and weekly KPI views of the Weekly Finance Pack over the public tables (Agents plan Phase 2, D4); plain views, no stored data. Level 2, Finance.';


--
-- Name: finance_scenario; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA finance_scenario;


--
-- Name: SCHEMA finance_scenario; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA finance_scenario IS 'Scenario (planted: α = 1.6 × the real 2025 Suez traffic swing) — not NileGate''s billing. Re-dated copies of invoices / payments and twins of the finance KPI views; for the link measure and its check only';


--
-- Name: finance_test; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA finance_test;


--
-- Name: SCHEMA finance_test; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA finance_test IS 'Evaluation copy only (Agents plan §4a R7): 4 golden weeks with planted invoice errors and a budget miss; never joined with the real tables; the answer key is outside the database.';


--
-- Name: fuzzystrmatch; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS fuzzystrmatch WITH SCHEMA public;


--
-- Name: EXTENSION fuzzystrmatch; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION fuzzystrmatch IS 'determine similarities and distance between strings';


--
-- Name: postgis; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis WITH SCHEMA public;


--
-- Name: EXTENSION postgis; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis IS 'PostGIS geometry and geography spatial types and functions';


--
-- Name: postgis_tiger_geocoder; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder WITH SCHEMA tiger;


--
-- Name: EXTENSION postgis_tiger_geocoder; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis_tiger_geocoder IS 'PostGIS tiger geocoder and reverse geocoder';


--
-- Name: postgis_topology; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS postgis_topology WITH SCHEMA topology;


--
-- Name: EXTENSION postgis_topology; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION postgis_topology IS 'PostGIS topology spatial types and functions';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: checkpoint_blobs; Type: TABLE; Schema: agent_state; Owner: -
--

CREATE TABLE agent_state.checkpoint_blobs (
    thread_id text NOT NULL,
    checkpoint_ns text DEFAULT ''::text NOT NULL,
    channel text NOT NULL,
    version text NOT NULL,
    type text NOT NULL,
    blob bytea
);


--
-- Name: checkpoint_migrations; Type: TABLE; Schema: agent_state; Owner: -
--

CREATE TABLE agent_state.checkpoint_migrations (
    v integer NOT NULL
);


--
-- Name: checkpoint_writes; Type: TABLE; Schema: agent_state; Owner: -
--

CREATE TABLE agent_state.checkpoint_writes (
    thread_id text NOT NULL,
    checkpoint_ns text DEFAULT ''::text NOT NULL,
    checkpoint_id text NOT NULL,
    task_id text NOT NULL,
    idx integer NOT NULL,
    channel text NOT NULL,
    type text,
    blob bytea NOT NULL,
    task_path text DEFAULT ''::text NOT NULL
);


--
-- Name: checkpoints; Type: TABLE; Schema: agent_state; Owner: -
--

CREATE TABLE agent_state.checkpoints (
    thread_id text NOT NULL,
    checkpoint_ns text DEFAULT ''::text NOT NULL,
    checkpoint_id text NOT NULL,
    parent_checkpoint_id text,
    type text,
    checkpoint jsonb NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL
);


--
-- Name: llm_daily_usage; Type: TABLE; Schema: agent_state; Owner: -
--

CREATE TABLE agent_state.llm_daily_usage (
    scope text NOT NULL,
    provider_day date NOT NULL,
    requests integer DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_daily_usage_requests_check CHECK ((requests >= 0))
);


--
-- Name: TABLE llm_daily_usage; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON TABLE agent_state.llm_daily_usage IS 'The daily LLM request count shared by every process (FastAPI plan C1, ADR-045): a call is reserved by one atomic INSERT … ON CONFLICT DO UPDATE … WHERE requests < limit RETURNING before it is sent; no row back = the daily quota is spent. Written by pipelines/agents/llm.py as ports_agent.';


--
-- Name: COLUMN llm_daily_usage.scope; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON COLUMN agent_state.llm_daily_usage.scope IS 'What the provider counts per day: a model (Gemini, Groq: provider/model) or a whole provider (OpenRouter), as llm.py''s scope()';


--
-- Name: COLUMN llm_daily_usage.provider_day; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON COLUMN agent_state.llm_daily_usage.provider_day IS 'The provider''s day (its own time zone, llm.PROVIDERS day_tz)';


--
-- Name: COLUMN llm_daily_usage.requests; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON COLUMN agent_state.llm_daily_usage.requests IS 'Requests reserved that day (sent or being sent)';


--
-- Name: COLUMN llm_daily_usage.updated_at; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON COLUMN agent_state.llm_daily_usage.updated_at IS 'Last reservation';


--
-- Name: llm_minute_usage; Type: TABLE; Schema: agent_state; Owner: -
--

CREATE TABLE agent_state.llm_minute_usage (
    scope text NOT NULL,
    minute timestamp with time zone NOT NULL,
    requests integer DEFAULT 0 NOT NULL,
    tokens integer DEFAULT 0 NOT NULL,
    CONSTRAINT llm_minute_usage_minute_check CHECK ((minute = date_trunc('minute'::text, minute))),
    CONSTRAINT llm_minute_usage_requests_check CHECK ((requests >= 0)),
    CONSTRAINT llm_minute_usage_tokens_check CHECK ((tokens >= 0))
);


--
-- Name: TABLE llm_minute_usage; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON TABLE agent_state.llm_minute_usage IS 'The per-minute LLM budget shared by every process (FastAPI plan C2, ADR-045): requests and estimated tokens reserved in the current minute, atomically; over the limit → the caller waits for the next minute. Rows older than a day are deleted by llm.py.';


--
-- Name: COLUMN llm_minute_usage.scope; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON COLUMN agent_state.llm_minute_usage.scope IS 'The rate scope (llm.py: a provider or provider/model)';


--
-- Name: COLUMN llm_minute_usage.minute; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON COLUMN agent_state.llm_minute_usage.minute IS 'The UTC minute (truncated)';


--
-- Name: COLUMN llm_minute_usage.requests; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON COLUMN agent_state.llm_minute_usage.requests IS 'Requests reserved in that minute';


--
-- Name: COLUMN llm_minute_usage.tokens; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON COLUMN agent_state.llm_minute_usage.tokens IS 'Estimated tokens reserved in that minute';


--
-- Name: pack_approved; Type: TABLE; Schema: agent_state; Owner: -
--

CREATE TABLE agent_state.pack_approved (
    report_week integer NOT NULL,
    thread_id text NOT NULL,
    approved_at timestamp with time zone NOT NULL,
    approver_employee_id integer NOT NULL,
    trend_series text[] NOT NULL,
    trend_weeks integer NOT NULL,
    variance_measure text NOT NULL,
    variance_rows text NOT NULL,
    degraded boolean NOT NULL,
    published_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT pack_approved_report_week_check CHECK (((report_week >= 1) AND (report_week <= 52))),
    CONSTRAINT pack_approved_thread_id_check CHECK ((thread_id ~~ 'weekly_pack:live:2025-W%'::text)),
    CONSTRAINT pack_approved_trend_series_check CHECK ((((cardinality(trend_series) >= 1) AND (cardinality(trend_series) <= 3)) AND (trend_series <@ ARRAY['billed_sdr'::text, 'budget_sdr'::text, 'collected_sdr'::text, 'ar_sdr'::text, 'overdue_sdr'::text, 'dso_days'::text]))),
    CONSTRAINT pack_approved_trend_weeks_check CHECK ((trend_weeks = ANY (ARRAY[4, 8, 13, 26]))),
    CONSTRAINT pack_approved_variance_measure_check CHECK ((variance_measure = ANY (ARRAY['budget_variance_sdr'::text, 'budget_variance_pct'::text, 'billed_wow_change_sdr'::text]))),
    CONSTRAINT pack_approved_variance_rows_check CHECK ((variance_rows = ANY (ARRAY['all'::text, 'top5'::text, 'bottom5'::text])))
);


--
-- Name: TABLE pack_approved; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON TABLE agent_state.pack_approved IS 'One row per report week with a published weekly pack (approver-request plan §2c): the chart choices as approved (defaults filled in) and who approved. Written only by the pack publisher on approve (a re-published week replaces its row); read by the finance.pack_* views.';


--
-- Name: COLUMN pack_approved.trend_series; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON COLUMN agent_state.pack_approved.trend_series IS 'The trend chart''s series (deck/charts.py TREND_SERIES keys), in drawing order';


--
-- Name: COLUMN pack_approved.trend_weeks; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON COLUMN agent_state.pack_approved.trend_weeks IS 'The trend chart''s window in weeks (4 / 8 / 13 / 26)';


--
-- Name: COLUMN pack_approved.variance_measure; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON COLUMN agent_state.pack_approved.variance_measure IS 'The variance chart''s measure (a finance.kpi_weekly_category column)';


--
-- Name: COLUMN pack_approved.variance_rows; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON COLUMN agent_state.pack_approved.variance_rows IS 'all / top5 / bottom5 categories by the measure';


--
-- Name: COLUMN pack_approved.degraded; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON COLUMN agent_state.pack_approved.degraded IS 'true = code replaced or dropped some of the Writer''s texts (c4 fallback); read the deck before quoting it';


--
-- Name: pack_approved_summary; Type: TABLE; Schema: agent_state; Owner: -
--

CREATE TABLE agent_state.pack_approved_summary (
    report_week integer NOT NULL,
    idx integer NOT NULL,
    text text NOT NULL,
    CONSTRAINT pack_approved_summary_idx_check CHECK (((idx >= 0) AND (idx <= 9))),
    CONSTRAINT pack_approved_summary_text_check CHECK (((length(text) >= 1) AND (length(text) <= 600)))
);


--
-- Name: TABLE pack_approved_summary; Type: COMMENT; Schema: agent_state; Owner: -
--

COMMENT ON TABLE agent_state.pack_approved_summary IS 'The approved executive summary of a report week (the deck''s slide 2, numbers filled in as the Validator passed them), one row per line.';


--
-- Name: audit_log; Type: TABLE; Schema: api; Owner: -
--

CREATE TABLE api.audit_log (
    id bigint NOT NULL,
    at timestamp with time zone DEFAULT now() NOT NULL,
    employee_id integer,
    request_id uuid,
    trace_id text,
    resource_type text NOT NULL,
    resource_id text,
    action text NOT NULL,
    decision text NOT NULL,
    detail jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT audit_log_decision_check CHECK ((decision = ANY (ARRAY['allowed'::text, 'denied'::text]))),
    CONSTRAINT audit_log_detail_check CHECK ((jsonb_typeof(detail) = 'object'::text))
);


--
-- Name: TABLE audit_log; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON TABLE api.audit_log IS 'Who did or was refused what through the API (ADR-014 redesign; THREAT_MODEL LLM02 / T8). Append-only for the runtime (INSERT, SELECT). Never a password, a token, a question''s text or an answer.';


--
-- Name: COLUMN audit_log.id; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.audit_log.id IS 'Surrogate key, in insertion order';


--
-- Name: COLUMN audit_log.at; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.audit_log.at IS 'When';


--
-- Name: COLUMN audit_log.employee_id; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.audit_log.employee_id IS 'The signed-in employee; NULL for a failed sign-in with an unknown email (no FK: rows outlive a login)';


--
-- Name: COLUMN audit_log.request_id; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.audit_log.request_id IS 'The X-Request-ID of the HTTP request (also in the access log, Sentry and LangSmith)';


--
-- Name: COLUMN audit_log.trace_id; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.audit_log.trace_id IS 'The agent_state thread id of a run (= the LangSmith trace''s thread_id metadata), when there is one';


--
-- Name: COLUMN audit_log.resource_type; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.audit_log.resource_type IS 'login, token, conversation, question, upload, pack, route_advice, voyage_watch, tool';


--
-- Name: COLUMN audit_log.resource_id; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.audit_log.resource_id IS 'Its id (a thread id, a document id, a tool name …); NULL when none';


--
-- Name: COLUMN audit_log.action; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.audit_log.action IS 'sign_in, sign_out, read, ask, refused_part, upload, decide, promote, …';


--
-- Name: COLUMN audit_log.decision; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.audit_log.decision IS 'allowed or denied';


--
-- Name: COLUMN audit_log.detail; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.audit_log.detail IS 'Small structured facts (status, counts, reasons); redacted, no free text from a model or a user';


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: api; Owner: -
--

ALTER TABLE api.audit_log ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME api.audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: conversation_turns; Type: TABLE; Schema: api; Owner: -
--

CREATE TABLE api.conversation_turns (
    conversation_id uuid NOT NULL,
    turn_no integer NOT NULL,
    question text NOT NULL,
    standalone_question text,
    resolved_by text NOT NULL,
    lang text NOT NULL,
    as_of timestamp with time zone NOT NULL,
    status text,
    thread_id text,
    answer_masked text,
    frame jsonb DEFAULT '{}'::jsonb NOT NULL,
    refused text[] DEFAULT '{}'::text[] NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT conversation_turns_frame_check CHECK ((jsonb_typeof(frame) = 'object'::text)),
    CONSTRAINT conversation_turns_lang_check CHECK ((lang = ANY (ARRAY['en'::text, 'ar'::text]))),
    CONSTRAINT conversation_turns_question_check CHECK (((char_length(question) >= 1) AND (char_length(question) <= 2000))),
    CONSTRAINT conversation_turns_resolved_by_check CHECK ((resolved_by = ANY (ARRAY['none'::text, 'code'::text, 'model'::text, 'clarify'::text]))),
    CONSTRAINT conversation_turns_turn_no_check CHECK ((turn_no >= 1))
);


--
-- Name: TABLE conversation_turns; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON TABLE api.conversation_turns IS 'The memory of a conversation (FastAPI plan §6a, ADR-065): one row per question. Never a number of an earlier answer (answer_masked), never upload / document / web text, never an entity of a refused part.';


--
-- Name: COLUMN conversation_turns.conversation_id; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversation_turns.conversation_id IS 'The conversation (api.conversations)';


--
-- Name: COLUMN conversation_turns.turn_no; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversation_turns.turn_no IS '1, 2, … in the order asked';


--
-- Name: COLUMN conversation_turns.question; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversation_turns.question IS 'The employee''s words as asked (≤ 2,000 characters)';


--
-- Name: COLUMN conversation_turns.standalone_question; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversation_turns.standalone_question IS 'The follow-up rewritten as a full question by the memory step (what was routed and answered); NULL when the question was routed as asked';


--
-- Name: COLUMN conversation_turns.resolved_by; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversation_turns.resolved_by IS 'none = not a follow-up; code = resolved by the rules; model = one guarded rewrite call; clarify = the API asked the employee back (no tool ran)';


--
-- Name: COLUMN conversation_turns.lang; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversation_turns.lang IS 'en or ar (Egyptian Arabic), detected or asked';


--
-- Name: COLUMN conversation_turns.as_of; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversation_turns.as_of IS 'The clock the turn ran at (RunContext.as_of)';


--
-- Name: COLUMN conversation_turns.status; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversation_turns.status IS 'The supervisor''s status (answered, partial, not_permitted, not_in_data, validation_failed, output_invalid) or clarify; NULL while running';


--
-- Name: COLUMN conversation_turns.thread_id; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversation_turns.thread_id IS 'The agent_state thread of the answer (ask:<employee>:<as_of>:<n>); NULL for clarify';


--
-- Name: COLUMN conversation_turns.answer_masked; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversation_turns.answer_masked IS 'The rendered answer with every slot replaced by ⟨n⟩: context for a later rewrite, never a source of a figure';


--
-- Name: COLUMN conversation_turns.frame; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversation_turns.frame IS 'The entity frame built by code from this turn''s cited evidence rows (vessel ids, report weeks, customer ids, LOCODEs, routes, invoice numbers, document ids, alert ids, topic)';


--
-- Name: COLUMN conversation_turns.refused; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversation_turns.refused IS 'Tools the router dropped for this asker on this turn (their entities never enter the frame)';


--
-- Name: COLUMN conversation_turns.created_at; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversation_turns.created_at IS 'Asked at';


--
-- Name: conversations; Type: TABLE; Schema: api; Owner: -
--

CREATE TABLE api.conversations (
    conversation_id uuid DEFAULT gen_random_uuid() NOT NULL,
    employee_id integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    last_turn_at timestamp with time zone,
    closed_at timestamp with time zone
);


--
-- Name: TABLE conversations; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON TABLE api.conversations IS 'A conversation of one employee (FastAPI plan §3.2 / §6a): its question turns and their memory; the uploads of the conversation live only in the API process memory (ADR-043). Only its owner continues it; the CEO may read it.';


--
-- Name: COLUMN conversations.conversation_id; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversations.conversation_id IS 'Random id (also the upload session id)';


--
-- Name: COLUMN conversations.employee_id; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversations.employee_id IS 'The owner (api.logins)';


--
-- Name: COLUMN conversations.created_at; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversations.created_at IS 'Opened at';


--
-- Name: COLUMN conversations.last_turn_at; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversations.last_turn_at IS 'The last question''s instant; NULL before the first question';


--
-- Name: COLUMN conversations.closed_at; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.conversations.closed_at IS 'Closed by its owner or after 8 h idle; NULL = open. Closing deletes its turns (the memory)';


--
-- Name: logins; Type: TABLE; Schema: api; Owner: -
--

CREATE TABLE api.logins (
    employee_id integer NOT NULL,
    password_hash text NOT NULL,
    disabled boolean DEFAULT false NOT NULL,
    failed_attempts integer DEFAULT 0 NOT NULL,
    locked_until timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    password_set_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT logins_failed_attempts_check CHECK ((failed_attempts >= 0)),
    CONSTRAINT logins_password_hash_check CHECK ((password_hash ~~ 'scrypt$%'::text))
);


--
-- Name: TABLE logins; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON TABLE api.logins IS 'One API login per employee (FastAPI plan §6, owner A1): the employee signs in with the employees.email of this id and a password. Created / reset / disabled by the owner with Api_admin.py; the API only reads the hash and counts failures.';


--
-- Name: COLUMN logins.employee_id; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.logins.employee_id IS 'The employee this login signs in as (employees.employee_id); role, ceiling and department are read from employees at every request, never stored here';


--
-- Name: COLUMN logins.password_hash; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.logins.password_hash IS 'scrypt$<n>$<r>$<p>$<salt base64>$<hash base64> (hashlib.scrypt, a random 16-byte salt per login); the password itself is never stored or logged';


--
-- Name: COLUMN logins.disabled; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.logins.disabled IS 'true = this login cannot sign in (set by the owner); its tokens are refused too';


--
-- Name: COLUMN logins.failed_attempts; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.logins.failed_attempts IS 'Wrong passwords since the last successful sign-in; at 5 the login is locked for 15 minutes';


--
-- Name: COLUMN logins.locked_until; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.logins.locked_until IS 'Sign-in refused until this instant (after 5 failures); NULL = not locked';


--
-- Name: COLUMN logins.created_at; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.logins.created_at IS 'When the owner created the login';


--
-- Name: COLUMN logins.password_set_at; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.logins.password_set_at IS 'When the password was last set by the owner';


--
-- Name: tokens; Type: TABLE; Schema: api; Owner: -
--

CREATE TABLE api.tokens (
    token_sha256 bytea NOT NULL,
    employee_id integer NOT NULL,
    issued_at timestamp with time zone DEFAULT now() NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    CONSTRAINT tokens_check CHECK ((expires_at > issued_at)),
    CONSTRAINT tokens_token_sha256_check CHECK ((octet_length(token_sha256) = 32))
);


--
-- Name: TABLE tokens; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON TABLE api.tokens IS 'Bearer tokens issued at sign-in (FastAPI plan §6): only the SHA-256 of the 32 random bytes is stored, so a copy of this table signs nobody in. Valid while not revoked and before expires_at (8 h).';


--
-- Name: COLUMN tokens.token_sha256; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.tokens.token_sha256 IS 'SHA-256 of the token the client holds (32 bytes)';


--
-- Name: COLUMN tokens.employee_id; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.tokens.employee_id IS 'The login the token belongs to (api.logins)';


--
-- Name: COLUMN tokens.issued_at; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.tokens.issued_at IS 'Sign-in instant';


--
-- Name: COLUMN tokens.expires_at; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.tokens.expires_at IS 'The token is refused from this instant (issued_at + 8 h)';


--
-- Name: COLUMN tokens.revoked_at; Type: COMMENT; Schema: api; Owner: -
--

COMMENT ON COLUMN api.tokens.revoked_at IS 'Set at logout (or by the owner); NULL = not revoked';


--
-- Name: suez_transits_daily; Type: TABLE; Schema: external; Owner: -
--

CREATE TABLE external.suez_transits_daily (
    date date NOT NULL,
    n_total integer NOT NULL,
    n_container integer NOT NULL,
    n_tanker integer NOT NULL,
    n_dry_bulk integer NOT NULL,
    n_general_cargo integer NOT NULL,
    n_roro integer NOT NULL,
    capacity bigint NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    CONSTRAINT suez_transits_daily_capacity_check CHECK ((capacity >= 0)),
    CONSTRAINT suez_transits_daily_check CHECK ((n_total >= ((((n_container + n_tanker) + n_dry_bulk) + n_general_cargo) + n_roro))),
    CONSTRAINT suez_transits_daily_n_container_check CHECK ((n_container >= 0)),
    CONSTRAINT suez_transits_daily_n_dry_bulk_check CHECK ((n_dry_bulk >= 0)),
    CONSTRAINT suez_transits_daily_n_general_cargo_check CHECK ((n_general_cargo >= 0)),
    CONSTRAINT suez_transits_daily_n_roro_check CHECK ((n_roro >= 0)),
    CONSTRAINT suez_transits_daily_n_tanker_check CHECK ((n_tanker >= 0)),
    CONSTRAINT suez_transits_daily_n_total_check CHECK ((n_total >= 0))
);


--
-- Name: TABLE suez_transits_daily; Type: COMMENT; Schema: external; Owner: -
--

COMMENT ON TABLE external.suez_transits_daily IS 'IMF PortWatch daily Suez Canal transits (AIS-based estimates, public, level 1), 2024-12-23 … 2025-12-28; loaded by Suez_transits_loader.py; read by finance.kpi_traffic_link (migration 026+)';


--
-- Name: COLUMN suez_transits_daily.date; Type: COMMENT; Schema: external; Owner: -
--

COMMENT ON COLUMN external.suez_transits_daily.date IS 'Day (UTC) of the PortWatch estimate';


--
-- Name: COLUMN suez_transits_daily.n_total; Type: COMMENT; Schema: external; Owner: -
--

COMMENT ON COLUMN external.suez_transits_daily.n_total IS 'Transit calls through the Suez Canal that day, all vessel types (PortWatch n_total)';


--
-- Name: COLUMN suez_transits_daily.n_container; Type: COMMENT; Schema: external; Owner: -
--

COMMENT ON COLUMN external.suez_transits_daily.n_container IS 'Container ship transits that day';


--
-- Name: COLUMN suez_transits_daily.n_tanker; Type: COMMENT; Schema: external; Owner: -
--

COMMENT ON COLUMN external.suez_transits_daily.n_tanker IS 'Tanker transits that day';


--
-- Name: COLUMN suez_transits_daily.n_dry_bulk; Type: COMMENT; Schema: external; Owner: -
--

COMMENT ON COLUMN external.suez_transits_daily.n_dry_bulk IS 'Dry bulk carrier transits that day';


--
-- Name: COLUMN suez_transits_daily.n_general_cargo; Type: COMMENT; Schema: external; Owner: -
--

COMMENT ON COLUMN external.suez_transits_daily.n_general_cargo IS 'General cargo ship transits that day';


--
-- Name: COLUMN suez_transits_daily.n_roro; Type: COMMENT; Schema: external; Owner: -
--

COMMENT ON COLUMN external.suez_transits_daily.n_roro IS 'Ro-ro ship transits that day';


--
-- Name: COLUMN suez_transits_daily.capacity; Type: COMMENT; Schema: external; Owner: -
--

COMMENT ON COLUMN external.suez_transits_daily.capacity IS 'Summed capacity of the transits that day, as PortWatch reports it (its own unit)';


--
-- Name: COLUMN suez_transits_daily.retrieved_at; Type: COMMENT; Schema: external; Owner: -
--

COMMENT ON COLUMN external.suez_transits_daily.retrieved_at IS 'When the loader fetched this row from PortWatch (UTC); PortWatch revises past days';


--
-- Name: customers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.customers (
    customer_id integer NOT NULL,
    customer_name text NOT NULL,
    country text NOT NULL,
    segment text NOT NULL,
    payment_terms_days integer NOT NULL,
    credit_rating text NOT NULL,
    CONSTRAINT customers_rating_chk CHECK ((credit_rating = ANY (ARRAY['A'::text, 'B'::text, 'C'::text]))),
    CONSTRAINT customers_segment_chk CHECK ((segment = ANY (ARRAY['container'::text, 'tanker'::text, 'bulk'::text, 'roro'::text, 'cruise'::text, 'agent'::text]))),
    CONSTRAINT customers_terms_chk CHECK ((payment_terms_days = ANY (ARRAY[30, 45, 60])))
);


--
-- Name: TABLE customers; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.customers IS 'Synthetic customers (shipping lines / agents) billed for Suez transit dues; 40 invented companies (Agents plan §4a R1). Level 2, Finance.';


--
-- Name: COLUMN customers.customer_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.customers.customer_id IS 'Surrogate key';


--
-- Name: COLUMN customers.customer_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.customers.customer_name IS 'Invented company name (not a real company)';


--
-- Name: COLUMN customers.country; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.customers.country IS 'Headquarters country (not the flag of its vessels)';


--
-- Name: COLUMN customers.segment; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.customers.segment IS 'Customer segment by the vessel types it operates';


--
-- Name: COLUMN customers.payment_terms_days; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.customers.payment_terms_days IS 'Payment terms: due date = invoice date + these days';


--
-- Name: COLUMN customers.credit_rating; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.customers.credit_rating IS 'Credit rating A / B / C (correlates with payment behaviour, does not reveal it)';


--
-- Name: dim_customer; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.dim_customer AS
 SELECT customer_id,
    customer_name,
    country,
    segment,
    payment_terms_days,
    credit_rating
   FROM public.customers;


--
-- Name: VIEW dim_customer; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.dim_customer IS 'Billed customers (shipping lines and agents, synthetic). Level 2, Finance.';


--
-- Name: COLUMN dim_customer.customer_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_customer.customer_id IS 'Customer id';


--
-- Name: COLUMN dim_customer.customer_name; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_customer.customer_name IS 'Invented company name (no real company)';


--
-- Name: COLUMN dim_customer.country; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_customer.country IS 'Head-office country';


--
-- Name: COLUMN dim_customer.segment; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_customer.segment IS 'container, tanker, bulk, roro, cruise or agent';


--
-- Name: COLUMN dim_customer.payment_terms_days; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_customer.payment_terms_days IS 'Payment terms in days (30, 45 or 60): due date = invoice date + terms';


--
-- Name: COLUMN dim_customer.credit_rating; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_customer.credit_rating IS 'Credit rating A, B or C';


--
-- Name: dim_date; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.dim_date AS
 SELECT (d)::date AS date_day,
    (EXTRACT(isoyear FROM d))::integer AS iso_year,
    (EXTRACT(week FROM d))::integer AS iso_week,
    to_char(d, 'IYYY"-W"IW'::text) AS iso_week_label,
    (date_trunc('week'::text, d))::date AS week_start,
    ((date_trunc('week'::text, d))::date + 6) AS week_end,
        CASE
            WHEN (EXTRACT(isoyear FROM d) = (2025)::numeric) THEN (EXTRACT(week FROM d))::integer
            ELSE NULL::integer
        END AS report_week,
    (EXTRACT(isodow FROM d))::integer AS iso_dow,
    (EXTRACT(year FROM d))::integer AS calendar_year,
    (EXTRACT(quarter FROM d))::integer AS calendar_quarter,
    (EXTRACT(month FROM d))::integer AS calendar_month
   FROM generate_series(('2025-01-01'::date)::timestamp with time zone, ('2026-03-31'::date)::timestamp with time zone, '1 day'::interval) d(d);


--
-- Name: VIEW dim_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.dim_date IS 'Calendar 2025-01-01 → 2026-03-31 (the payments horizon), one row per day, with its ISO week. Level 2, Finance (schema level).';


--
-- Name: COLUMN dim_date.date_day; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_date.date_day IS 'The day';


--
-- Name: COLUMN dim_date.iso_year; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_date.iso_year IS 'ISO-8601 week-numbering year (2025-12-29..31 belong to 2026)';


--
-- Name: COLUMN dim_date.iso_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_date.iso_week IS 'ISO-8601 week number 1–53 (Monday to Sunday)';


--
-- Name: COLUMN dim_date.iso_week_label; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_date.iso_week_label IS 'ISO week as text, e.g. 2025-W05';


--
-- Name: COLUMN dim_date.week_start; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_date.week_start IS 'Monday of the ISO week';


--
-- Name: COLUMN dim_date.week_end; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_date.week_end IS 'Sunday of the ISO week (the "as of" day of a report)';


--
-- Name: COLUMN dim_date.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_date.report_week IS 'Report week 1–52 (ISO weeks of 2025, D12); NULL for days of ISO 2026';


--
-- Name: COLUMN dim_date.iso_dow; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_date.iso_dow IS 'ISO day of week, 1 = Monday … 7 = Sunday';


--
-- Name: COLUMN dim_date.calendar_year; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_date.calendar_year IS 'Calendar year';


--
-- Name: COLUMN dim_date.calendar_quarter; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_date.calendar_quarter IS 'Calendar quarter 1–4';


--
-- Name: COLUMN dim_date.calendar_month; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_date.calendar_month IS 'Calendar month 1–12';


--
-- Name: toll_rate_bands; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.toll_rate_bands (
    id integer NOT NULL,
    vessel_category text NOT NULL,
    laden_ballast text NOT NULL,
    band_order integer NOT NULL,
    band_label text NOT NULL,
    band_min_tons numeric NOT NULL,
    band_max_tons numeric,
    rate_sdr_per_ton numeric NOT NULL,
    CONSTRAINT toll_rate_bands_band_order_chk CHECK ((band_order >= 1)),
    CONSTRAINT toll_rate_bands_band_range_chk CHECK (((band_min_tons >= (0)::numeric) AND ((band_max_tons IS NULL) OR (band_max_tons > band_min_tons)))),
    CONSTRAINT toll_rate_bands_laden_ballast_chk CHECK ((laden_ballast = ANY (ARRAY['Laden'::text, 'Ballast'::text]))),
    CONSTRAINT toll_rate_bands_rate_chk CHECK ((rate_sdr_per_ton > (0)::numeric)),
    CONSTRAINT toll_rate_bands_vessel_category_chk CHECK ((vessel_category = ANY (ARRAY['Chemical Tankers & Other Liquid Bulk Tankers'::text, 'Containerships'::text, 'Crude Oil Tankers'::text, 'Cruise Ships'::text, 'Dry Bulk Vessels'::text, 'General Cargo / Multi-Purpose / Heavy Lift Vessels'::text, 'Liquefied Natural Gas (LNG) Carriers'::text, 'Liquefied Petroleum Gas (LPG) Carriers'::text, 'Other Vessels'::text, 'Petroleum Product Tankers'::text, 'Roll-On/Roll-Off (Ro/Ro) Vessels'::text, 'Special Floating Units'::text, 'Vehicles Carriers'::text])))
);


--
-- Name: TABLE toll_rate_bands; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.toll_rate_bands IS 'Suez Canal transit dues from 2023-01-01, progressive bands per vessel category and condition (ADR-004, ADR-005). Level 1, Finance.';


--
-- Name: COLUMN toll_rate_bands.id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.toll_rate_bands.id IS 'Surrogate key';


--
-- Name: COLUMN toll_rate_bands.vessel_category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.toll_rate_bands.vessel_category IS 'Suez vessel category (same 13 values as vessels.vessel_type)';


--
-- Name: COLUMN toll_rate_bands.laden_ballast; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.toll_rate_bands.laden_ballast IS 'Laden or Ballast';


--
-- Name: COLUMN toll_rate_bands.band_order; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.toll_rate_bands.band_order IS 'Position of the band within (category, condition), from 1';


--
-- Name: COLUMN toll_rate_bands.band_label; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.toll_rate_bands.band_label IS 'Band label as printed in the tariff';


--
-- Name: COLUMN toll_rate_bands.band_min_tons; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.toll_rate_bands.band_min_tons IS 'Lower bound of the band, SCNT';


--
-- Name: COLUMN toll_rate_bands.band_max_tons; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.toll_rate_bands.band_max_tons IS 'Upper bound of the band, SCNT; NULL = open last band';


--
-- Name: COLUMN toll_rate_bands.rate_sdr_per_ton; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.toll_rate_bands.rate_sdr_per_ton IS 'Rate in SDR per SCNT ton within the band (money is stored in SDR only, ADR-003)';


--
-- Name: dim_toll_band; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.dim_toll_band AS
 SELECT id AS toll_rate_band_id,
    vessel_category,
    laden_ballast,
    band_order,
    band_label,
    band_min_tons,
    band_max_tons,
    rate_sdr_per_ton
   FROM public.toll_rate_bands;


--
-- Name: VIEW dim_toll_band; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.dim_toll_band IS 'Suez transit dues bands (progressive, SDR per SCNT; ADR-004). Level 2, Finance (schema level; the tariff table is level 1).';


--
-- Name: COLUMN dim_toll_band.toll_rate_band_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_toll_band.toll_rate_band_id IS 'Band id (toll_rate_bands.id)';


--
-- Name: COLUMN dim_toll_band.vessel_category; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_toll_band.vessel_category IS 'Tariff vessel category';


--
-- Name: COLUMN dim_toll_band.laden_ballast; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_toll_band.laden_ballast IS 'Laden or Ballast';


--
-- Name: COLUMN dim_toll_band.band_order; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_toll_band.band_order IS 'Band position 1–8 within the category and condition';


--
-- Name: COLUMN dim_toll_band.band_label; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_toll_band.band_label IS 'Band label as printed in the tariff';


--
-- Name: COLUMN dim_toll_band.band_min_tons; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_toll_band.band_min_tons IS 'Lower bound of the band (SCNT)';


--
-- Name: COLUMN dim_toll_band.band_max_tons; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_toll_band.band_max_tons IS 'Upper bound of the band (SCNT); NULL = open-ended';


--
-- Name: COLUMN dim_toll_band.rate_sdr_per_ton; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_toll_band.rate_sdr_per_ton IS 'Rate in SDR per SCNT inside the band';


--
-- Name: ports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ports (
    locode character varying(5) NOT NULL,
    name text NOT NULL,
    country text NOT NULL,
    function character(8) NOT NULL,
    status character(2) NOT NULL,
    outflows double precision NOT NULL,
    lon double precision NOT NULL,
    lat double precision NOT NULL,
    geom public.geometry(Point,4326) NOT NULL,
    CONSTRAINT ports_function_format_chk CHECK ((function ~ '^[0-9-]{7}[0-9B-]$'::text)),
    CONSTRAINT ports_geom_matches_lon_lat_chk CHECK (((abs((public.st_x(geom) - lon)) < (0.000000001)::double precision) AND (abs((public.st_y(geom) - lat)) < (0.000000001)::double precision))),
    CONSTRAINT ports_lat_lon_chk CHECK ((((lat >= ('-90'::integer)::double precision) AND (lat <= (90)::double precision)) AND ((lon >= ('-180'::integer)::double precision) AND (lon <= (180)::double precision)))),
    CONSTRAINT ports_locode_format_chk CHECK (((locode)::text ~ '^[A-Z]{2}[A-Z2-9]{3}$'::text)),
    CONSTRAINT ports_outflows_chk CHECK ((outflows >= (0)::double precision)),
    CONSTRAINT ports_status_format_chk CHECK ((status ~ '^[A-Z]{2}$'::text))
);


--
-- Name: TABLE ports; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.ports IS 'Real port reference (UN/LOCODE, from attributed_ports.geojson; ADR-002). Level 1, Operations.';


--
-- Name: COLUMN ports.locode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ports.locode IS '5-character UN/LOCODE, the cross-entity key for ports (ADR-002)';


--
-- Name: COLUMN ports.name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ports.name IS 'Port name';


--
-- Name: COLUMN ports.country; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ports.country IS 'Country name (port_connections uses ISO alpha-2 codes instead)';


--
-- Name: COLUMN ports.function; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ports.function IS 'UN/LOCODE function classifier, 8 positions (1 = port, 2 = rail, 3 = road, 4 = airport, 5 = postal, 6 = multimodal, 7 = fixed transport, B = border crossing; - = no)';


--
-- Name: COLUMN ports.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ports.status IS 'UN/LOCODE status code (e.g. AI = approved by national agency, RL = recognised location)';


--
-- Name: COLUMN ports.outflows; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ports.outflows IS 'Aggregated outgoing flow of the port in the port-flows network';


--
-- Name: COLUMN ports.lon; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ports.lon IS 'Longitude, WGS 84 (= ST_X(geom))';


--
-- Name: COLUMN ports.lat; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ports.lat IS 'Latitude, WGS 84 (= ST_Y(geom))';


--
-- Name: COLUMN ports.geom; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.ports.geom IS 'Point, SRID 4326';


--
-- Name: vessels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vessels (
    vessel_id integer NOT NULL,
    imo_number character varying(7) NOT NULL,
    vessel_name text NOT NULL,
    vessel_type text NOT NULL,
    flag_country text NOT NULL,
    scnt_tons numeric NOT NULL,
    origin_locode character varying(5) NOT NULL,
    destination_locode character varying(5) NOT NULL,
    condition text NOT NULL,
    status text NOT NULL,
    mmsi character varying(9) NOT NULL,
    customer_id integer NOT NULL,
    CONSTRAINT vessels_condition_chk CHECK ((condition = ANY (ARRAY['Laden'::text, 'Ballast'::text]))),
    CONSTRAINT vessels_imo_number_format_chk CHECK (((imo_number)::text ~ '^[0-9]{7}$'::text)),
    CONSTRAINT vessels_mmsi_format_chk CHECK (((mmsi)::text ~ '^[2-7][0-9]{8}$'::text)),
    CONSTRAINT vessels_route_chk CHECK (((origin_locode)::text <> (destination_locode)::text)),
    CONSTRAINT vessels_scnt_tons_chk CHECK ((scnt_tons > (0)::numeric)),
    CONSTRAINT vessels_status_chk CHECK ((status = ANY (ARRAY['In Transit'::text, 'At Port'::text, 'Anchored'::text, 'Completed'::text]))),
    CONSTRAINT vessels_vessel_type_chk CHECK ((vessel_type = ANY (ARRAY['Chemical Tankers & Other Liquid Bulk Tankers'::text, 'Containerships'::text, 'Crude Oil Tankers'::text, 'Cruise Ships'::text, 'Dry Bulk Vessels'::text, 'General Cargo / Multi-Purpose / Heavy Lift Vessels'::text, 'Liquefied Natural Gas (LNG) Carriers'::text, 'Liquefied Petroleum Gas (LPG) Carriers'::text, 'Other Vessels'::text, 'Petroleum Product Tankers'::text, 'Roll-On/Roll-Off (Ro/Ro) Vessels'::text, 'Special Floating Units'::text, 'Vehicles Carriers'::text])))
);


--
-- Name: TABLE vessels; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.vessels IS 'Synthetic NileGate fleet (500 vessels, seed 42): system of record for vessel identity (ADR-028). Level 1, Operations.';


--
-- Name: COLUMN vessels.vessel_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessels.vessel_id IS 'Surrogate key (= imo_number - 9000000)';


--
-- Name: COLUMN vessels.imo_number; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessels.imo_number IS '7-digit IMO number (synthetic, sequential; the IMO check digit is not enforced)';


--
-- Name: COLUMN vessels.vessel_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessels.vessel_name IS 'Vessel name (synthetic)';


--
-- Name: COLUMN vessels.vessel_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessels.vessel_type IS 'Suez vessel category (same values as toll_rate_bands.vessel_category)';


--
-- Name: COLUMN vessels.flag_country; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessels.flag_country IS 'Flag state name; its ITU MID is the first 3 digits of mmsi';


--
-- Name: COLUMN vessels.scnt_tons; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessels.scnt_tons IS 'Suez Canal Net Tonnage (SCNT), basis of the transit dues';


--
-- Name: COLUMN vessels.origin_locode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessels.origin_locode IS 'Origin port of the current voyage (UN/LOCODE)';


--
-- Name: COLUMN vessels.destination_locode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessels.destination_locode IS 'Destination port of the current voyage (UN/LOCODE)';


--
-- Name: COLUMN vessels.condition; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessels.condition IS 'Laden or Ballast (selects the toll band set)';


--
-- Name: COLUMN vessels.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessels.status IS 'In Transit, At Port, Anchored or Completed; the synthetic AIS tracks follow it (ADR-032)';


--
-- Name: COLUMN vessels.mmsi; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessels.mmsi IS 'Ship station MMSI: MID of flag_country (db/reference/flag_country_mid.csv) + 6 digits. Synthetic (migration 005).';


--
-- Name: COLUMN vessels.customer_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessels.customer_id IS 'The customer billed for this vessel (FK customers; migration 012)';


--
-- Name: dim_vessel; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.dim_vessel AS
 SELECT v.vessel_id,
    v.imo_number,
    v.vessel_name,
    v.vessel_type AS vessel_category,
    v.flag_country,
    v.scnt_tons,
    v.condition,
    v.origin_locode,
    po.name AS origin_port,
    v.destination_locode,
    pd.name AS destination_port,
    (((v.origin_locode)::text || '-'::text) || (v.destination_locode)::text) AS route,
    v.customer_id
   FROM ((public.vessels v
     LEFT JOIN public.ports po ON (((po.locode)::text = (v.origin_locode)::text)))
     LEFT JOIN public.ports pd ON (((pd.locode)::text = (v.destination_locode)::text)));


--
-- Name: VIEW dim_vessel; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.dim_vessel IS 'Vessels with their category, route (port names) and billed customer. Level 2, Finance (schema level; the vessels table is level 1).';


--
-- Name: COLUMN dim_vessel.vessel_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_vessel.vessel_id IS 'Vessel id';


--
-- Name: COLUMN dim_vessel.imo_number; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_vessel.imo_number IS 'IMO number (7 digits, synthetic)';


--
-- Name: COLUMN dim_vessel.vessel_name; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_vessel.vessel_name IS 'Vessel name';


--
-- Name: COLUMN dim_vessel.vessel_category; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_vessel.vessel_category IS 'Suez tariff vessel category (13 values) = vessels.vessel_type; the budget is set per category';


--
-- Name: COLUMN dim_vessel.flag_country; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_vessel.flag_country IS 'Flag state';


--
-- Name: COLUMN dim_vessel.scnt_tons; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_vessel.scnt_tons IS 'Suez Canal Net Tonnage';


--
-- Name: COLUMN dim_vessel.condition; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_vessel.condition IS 'Laden or Ballast (vessel record)';


--
-- Name: COLUMN dim_vessel.origin_locode; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_vessel.origin_locode IS 'Origin port UN/LOCODE';


--
-- Name: COLUMN dim_vessel.origin_port; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_vessel.origin_port IS 'Origin port name';


--
-- Name: COLUMN dim_vessel.destination_locode; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_vessel.destination_locode IS 'Destination port UN/LOCODE';


--
-- Name: COLUMN dim_vessel.destination_port; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_vessel.destination_port IS 'Destination port name';


--
-- Name: COLUMN dim_vessel.route; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_vessel.route IS 'origin-destination LOCODE pair';


--
-- Name: COLUMN dim_vessel.customer_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_vessel.customer_id IS 'The customer billed for this vessel';


--
-- Name: dim_week; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.dim_week AS
 SELECT w AS report_week,
    format('2025-W%s'::text, lpad((w)::text, 2, '0'::text)) AS iso_week_label,
    ('2024-12-30'::date + (7 * (w - 1))) AS week_start,
    (('2024-12-30'::date + (7 * (w - 1))) + 6) AS week_end,
    GREATEST(((('2024-12-30'::date + (7 * (w - 1))) + 6) - 90), '2025-01-01'::date) AS dso_window_start,
    (((('2024-12-30'::date + (7 * (w - 1))) + 6) - GREATEST(((('2024-12-30'::date + (7 * (w - 1))) + 6) - 90), '2025-01-01'::date)) + 1) AS dso_window_days,
    ((((('2024-12-30'::date + (7 * (w - 1))) + 6) - '2025-01-01'::date) + 1) < 91) AS is_warmup
   FROM generate_series(1, 52) w(w);


--
-- Name: VIEW dim_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.dim_week IS 'The 52 report weeks (ISO weeks of 2025, D12) with the DSO window. Level 2, Finance (schema level).';


--
-- Name: COLUMN dim_week.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_week.report_week IS 'Report week 1–52 = ISO week of 2025';


--
-- Name: COLUMN dim_week.iso_week_label; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_week.iso_week_label IS 'ISO week as text, e.g. 2025-W05';


--
-- Name: COLUMN dim_week.week_start; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_week.week_start IS 'Monday of the week';


--
-- Name: COLUMN dim_week.week_end; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_week.week_end IS 'Sunday of the week: every "as of" metric is measured at its end (23:59)';


--
-- Name: COLUMN dim_week.dso_window_start; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_week.dso_window_start IS 'First day of the DSO window: week_end − 90 days, not before 2025-01-01 (start of the billing history)';


--
-- Name: COLUMN dim_week.dso_window_days; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_week.dso_window_days IS 'Length of the DSO window in days: 91, or fewer in the warm-up weeks';


--
-- Name: COLUMN dim_week.is_warmup; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.dim_week.is_warmup IS 'True for weeks 1–13: less than 91 days of billing history, receivables still building up from zero (no 2024 invoices); DSO uses the shorter window (owner decision P2-2)';


--
-- Name: invoices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invoices (
    invoice_id integer NOT NULL,
    invoice_number text NOT NULL,
    vessel_id integer NOT NULL,
    toll_rate_band_id integer,
    invoice_date date NOT NULL,
    scnt_tons numeric NOT NULL,
    rate_sdr_per_ton numeric,
    amount numeric NOT NULL,
    description text,
    status text NOT NULL,
    CONSTRAINT invoices_amount_chk CHECK ((amount > (0)::numeric)),
    CONSTRAINT invoices_number_format_chk CHECK ((invoice_number ~ '^INV-[0-9]{7}$'::text)),
    CONSTRAINT invoices_rate_chk CHECK (((rate_sdr_per_ton IS NULL) OR (rate_sdr_per_ton > (0)::numeric))),
    CONSTRAINT invoices_scnt_tons_chk CHECK ((scnt_tons > (0)::numeric)),
    CONSTRAINT invoices_status_chk CHECK ((status = ANY (ARRAY['Issued'::text, 'Paid'::text, 'Pending'::text])))
);


--
-- Name: TABLE invoices; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.invoices IS 'Suez transit dues invoices (1,000, dated 2025), built in PostgreSQL (ADR-013). Level 2, Finance.';


--
-- Name: COLUMN invoices.invoice_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invoices.invoice_id IS 'Surrogate key';


--
-- Name: COLUMN invoices.invoice_number; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invoices.invoice_number IS 'Unique number INV-nnnnnnn';


--
-- Name: COLUMN invoices.vessel_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invoices.vessel_id IS 'Invoiced vessel';


--
-- Name: COLUMN invoices.toll_rate_band_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invoices.toll_rate_band_id IS 'Terminal toll band reached by the vessel SCNT (ADR-004)';


--
-- Name: COLUMN invoices.invoice_date; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invoices.invoice_date IS 'Invoice date (2025)';


--
-- Name: COLUMN invoices.scnt_tons; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invoices.scnt_tons IS 'SCNT of the vessel at invoicing';


--
-- Name: COLUMN invoices.rate_sdr_per_ton; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invoices.rate_sdr_per_ton IS 'Rate of the terminal band, SDR per ton';


--
-- Name: COLUMN invoices.amount; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invoices.amount IS 'Progressive sum over the bands, in SDR (ADR-003, ADR-004)';


--
-- Name: COLUMN invoices.description; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invoices.description IS 'Free text, e.g. Suez Canal transit dues - <category>';


--
-- Name: COLUMN invoices.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.invoices.status IS 'Original generator label (Issued / Pending / Paid), drawn at random over 2025 (ADR-013); NOT the payment state — the payment state is derived from payments by the finance views (Agents plan §4a, D6 amended 2026-10-13).';


--
-- Name: payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payments (
    invoice_number text NOT NULL,
    paid_date date NOT NULL,
    amount_sdr numeric NOT NULL,
    CONSTRAINT payments_amount_chk CHECK ((amount_sdr > (0)::numeric))
);


--
-- Name: TABLE payments; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.payments IS 'One full payment per paid invoice (no partial payments), up to 2026-03-31; an invoice without a row is unpaid. Level 2, Finance.';


--
-- Name: COLUMN payments.invoice_number; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.payments.invoice_number IS 'The paid invoice (FK invoices)';


--
-- Name: COLUMN payments.paid_date; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.payments.paid_date IS 'Date the payment was received';


--
-- Name: COLUMN payments.amount_sdr; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.payments.amount_sdr IS 'Amount paid in SDR (= the invoice amount)';


--
-- Name: fact_invoice; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.fact_invoice AS
 SELECT i.invoice_id,
    i.invoice_number,
    i.invoice_date,
        CASE
            WHEN (EXTRACT(isoyear FROM i.invoice_date) = (2025)::numeric) THEN (EXTRACT(week FROM i.invoice_date))::integer
            ELSE NULL::integer
        END AS invoice_report_week,
    v.customer_id,
    i.vessel_id,
    v.vessel_type AS vessel_category,
    b.laden_ballast AS priced_condition,
    i.toll_rate_band_id,
    i.scnt_tons,
    i.rate_sdr_per_ton,
    i.amount AS amount_sdr,
    c.payment_terms_days,
    (i.invoice_date + c.payment_terms_days) AS due_date,
    p.paid_date,
    (p.paid_date - i.invoice_date) AS days_to_pay,
    (p.paid_date - (i.invoice_date + c.payment_terms_days)) AS days_paid_after_due
   FROM ((((public.invoices i
     JOIN public.vessels v ON ((v.vessel_id = i.vessel_id)))
     JOIN public.customers c ON ((c.customer_id = v.customer_id)))
     LEFT JOIN public.toll_rate_bands b ON ((b.id = i.toll_rate_band_id)))
     LEFT JOIN public.payments p ON ((p.invoice_number = i.invoice_number)));


--
-- Name: VIEW fact_invoice; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.fact_invoice IS 'One row per invoice with the derived due date and its payment (ADR-046: invoices.status is a label and is not used). Level 2, Finance.';


--
-- Name: COLUMN fact_invoice.invoice_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.invoice_id IS 'Invoice id';


--
-- Name: COLUMN fact_invoice.invoice_number; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.invoice_number IS 'Invoice number INV-nnnnnnn';


--
-- Name: COLUMN fact_invoice.invoice_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.invoice_date IS 'Invoice (billing) date: revenue is counted in its week';


--
-- Name: COLUMN fact_invoice.invoice_report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.invoice_report_week IS 'Report week of the invoice date; NULL for 2025-12-29..31 (ISO 2026-W01)';


--
-- Name: COLUMN fact_invoice.customer_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.customer_id IS 'Billed customer (through the vessel)';


--
-- Name: COLUMN fact_invoice.vessel_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.vessel_id IS 'Vessel id';


--
-- Name: COLUMN fact_invoice.vessel_category; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.vessel_category IS 'Vessel category (13 tariff categories)';


--
-- Name: COLUMN fact_invoice.priced_condition; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.priced_condition IS 'Laden or Ballast as priced (from the terminal band; Special Floating Units always Laden)';


--
-- Name: COLUMN fact_invoice.toll_rate_band_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.toll_rate_band_id IS 'Terminal band containing the vessel SCNT';


--
-- Name: COLUMN fact_invoice.scnt_tons; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.scnt_tons IS 'Billed Suez Canal Net Tonnage';


--
-- Name: COLUMN fact_invoice.rate_sdr_per_ton; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.rate_sdr_per_ton IS 'Rate of the terminal band (SDR per SCNT)';


--
-- Name: COLUMN fact_invoice.amount_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.amount_sdr IS 'Invoice amount in SDR (progressive toll, ADR-003 / ADR-004)';


--
-- Name: COLUMN fact_invoice.payment_terms_days; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.payment_terms_days IS 'Customer payment terms in days';


--
-- Name: COLUMN fact_invoice.due_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.due_date IS 'Derived due date = invoice_date + payment_terms_days (not stored, ADR-046)';


--
-- Name: COLUMN fact_invoice.paid_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.paid_date IS 'Date of the single full payment; NULL = unpaid at the 2026-03-31 horizon';


--
-- Name: COLUMN fact_invoice.days_to_pay; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.days_to_pay IS 'paid_date − invoice_date in days; NULL if unpaid';


--
-- Name: COLUMN fact_invoice.days_paid_after_due; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_invoice.days_paid_after_due IS 'paid_date − due_date in days (negative = paid early); NULL if unpaid';


--
-- Name: fact_ar_snapshot; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.fact_ar_snapshot AS
 SELECT w.report_week,
    w.week_end AS as_of_date,
    f.invoice_number,
    f.invoice_date,
    f.due_date,
    f.customer_id,
    f.vessel_id,
    f.vessel_category,
    f.amount_sdr,
    (w.week_end - f.due_date) AS days_past_due,
    ((w.week_end - f.due_date) > 0) AS is_overdue,
        CASE
            WHEN ((w.week_end - f.due_date) <= 0) THEN 'current'::text
            WHEN ((w.week_end - f.due_date) <= 30) THEN '1-30'::text
            WHEN ((w.week_end - f.due_date) <= 60) THEN '31-60'::text
            WHEN ((w.week_end - f.due_date) <= 90) THEN '61-90'::text
            ELSE '90+'::text
        END AS aging_bucket,
        CASE
            WHEN ((w.week_end - f.due_date) <= 0) THEN 1
            WHEN ((w.week_end - f.due_date) <= 30) THEN 2
            WHEN ((w.week_end - f.due_date) <= 60) THEN 3
            WHEN ((w.week_end - f.due_date) <= 90) THEN 4
            ELSE 5
        END AS aging_bucket_order
   FROM (finance.dim_week w
     JOIN finance.fact_invoice f ON (((f.invoice_date <= w.week_end) AND ((f.paid_date IS NULL) OR (f.paid_date > w.week_end)))));


--
-- Name: VIEW fact_ar_snapshot; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.fact_ar_snapshot IS 'Receivables as of each report week: one row per invoice issued on or before the week''s Sunday and not paid by then, with its age past due. Level 2, Finance.';


--
-- Name: COLUMN fact_ar_snapshot.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_ar_snapshot.report_week IS 'Report week';


--
-- Name: COLUMN fact_ar_snapshot.as_of_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_ar_snapshot.as_of_date IS 'Sunday of the report week (as of 23:59)';


--
-- Name: COLUMN fact_ar_snapshot.invoice_number; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_ar_snapshot.invoice_number IS 'Open invoice';


--
-- Name: COLUMN fact_ar_snapshot.invoice_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_ar_snapshot.invoice_date IS 'Invoice date';


--
-- Name: COLUMN fact_ar_snapshot.due_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_ar_snapshot.due_date IS 'Derived due date';


--
-- Name: COLUMN fact_ar_snapshot.customer_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_ar_snapshot.customer_id IS 'Billed customer';


--
-- Name: COLUMN fact_ar_snapshot.vessel_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_ar_snapshot.vessel_id IS 'Vessel id';


--
-- Name: COLUMN fact_ar_snapshot.vessel_category; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_ar_snapshot.vessel_category IS 'Vessel category';


--
-- Name: COLUMN fact_ar_snapshot.amount_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_ar_snapshot.amount_sdr IS 'Open amount in SDR (no partial payments: the full invoice amount)';


--
-- Name: COLUMN fact_ar_snapshot.days_past_due; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_ar_snapshot.days_past_due IS 'as_of_date − due_date in days (≤ 0 = not yet due)';


--
-- Name: COLUMN fact_ar_snapshot.is_overdue; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_ar_snapshot.is_overdue IS 'True when days_past_due ≥ 1';


--
-- Name: COLUMN fact_ar_snapshot.aging_bucket; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_ar_snapshot.aging_bucket IS 'current (≤ 0), 1-30, 31-60, 61-90 or 90+ days past due';


--
-- Name: COLUMN fact_ar_snapshot.aging_bucket_order; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_ar_snapshot.aging_bucket_order IS 'Sort order of aging_bucket, 1 = current … 5 = 90+';


--
-- Name: fact_payment; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.fact_payment AS
 SELECT p.invoice_number,
    p.paid_date,
        CASE
            WHEN (EXTRACT(isoyear FROM p.paid_date) = (2025)::numeric) THEN (EXTRACT(week FROM p.paid_date))::integer
            ELSE NULL::integer
        END AS paid_report_week,
    p.amount_sdr,
    f.invoice_date,
    f.due_date,
    f.customer_id,
    f.vessel_id,
    f.vessel_category,
    f.days_to_pay,
    f.days_paid_after_due
   FROM (public.payments p
     JOIN finance.fact_invoice f ON ((f.invoice_number = p.invoice_number)));


--
-- Name: VIEW fact_payment; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.fact_payment IS 'One row per payment (one full payment per paid invoice): collections are counted in the week of paid_date. Level 2, Finance.';


--
-- Name: COLUMN fact_payment.invoice_number; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_payment.invoice_number IS 'Paid invoice';


--
-- Name: COLUMN fact_payment.paid_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_payment.paid_date IS 'Payment date';


--
-- Name: COLUMN fact_payment.paid_report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_payment.paid_report_week IS 'Report week of the payment; NULL for payments in ISO 2026';


--
-- Name: COLUMN fact_payment.amount_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_payment.amount_sdr IS 'Amount received in SDR (= the invoice amount)';


--
-- Name: COLUMN fact_payment.invoice_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_payment.invoice_date IS 'Invoice date of the paid invoice';


--
-- Name: COLUMN fact_payment.due_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_payment.due_date IS 'Derived due date of the paid invoice';


--
-- Name: COLUMN fact_payment.customer_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_payment.customer_id IS 'Paying customer';


--
-- Name: COLUMN fact_payment.vessel_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_payment.vessel_id IS 'Vessel of the paid invoice';


--
-- Name: COLUMN fact_payment.vessel_category; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_payment.vessel_category IS 'Vessel category of the paid invoice';


--
-- Name: COLUMN fact_payment.days_to_pay; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_payment.days_to_pay IS 'paid_date − invoice_date in days';


--
-- Name: COLUMN fact_payment.days_paid_after_due; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.fact_payment.days_paid_after_due IS 'paid_date − due_date in days (negative = paid early)';


--
-- Name: invoice_audit; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.invoice_audit AS
 WITH billed AS (
         SELECT i.invoice_number,
            i.vessel_id,
            i.invoice_date,
            i.scnt_tons,
            i.amount AS billed_sdr,
            i.rate_sdr_per_ton AS billed_rate
           FROM public.invoices i
        ), inv AS (
         SELECT b.invoice_number,
            b.vessel_id,
            b.invoice_date,
            b.scnt_tons,
            b.billed_sdr,
            b.billed_rate,
            v.vessel_name,
            v.vessel_type AS vessel_category,
            v.condition,
            v.scnt_tons AS vessel_scnt,
                CASE
                    WHEN (v.vessel_type = 'Special Floating Units'::text) THEN 'Laden'::text
                    ELSE v.condition
                END AS priced_condition,
            d.report_week
           FROM ((billed b
             JOIN public.vessels v ON ((v.vessel_id = b.vessel_id)))
             JOIN finance.dim_date d ON ((d.date_day = b.invoice_date)))
        ), scenario AS (
         SELECT inv.invoice_number,
            'expected'::text AS scenario,
            inv.vessel_category AS category,
            inv.priced_condition AS cond,
            inv.vessel_scnt AS tons
           FROM inv
        UNION ALL
         SELECT inv.invoice_number,
            'invoice_tonnage'::text,
            inv.vessel_category,
            inv.priced_condition,
            inv.scnt_tons
           FROM inv
          WHERE (inv.scnt_tons <> inv.vessel_scnt)
        UNION ALL
         SELECT inv.invoice_number,
            'condition_swapped'::text,
            inv.vessel_category,
                CASE inv.condition
                    WHEN 'Laden'::text THEN 'Ballast'::text
                    ELSE 'Laden'::text
                END AS "case",
            inv.vessel_scnt
           FROM inv
          WHERE (inv.vessel_category <> 'Special Floating Units'::text)
        UNION ALL
         SELECT inv.invoice_number,
            'sfu_priced_ballast'::text,
            'Other Vessels'::text,
            'Ballast'::text,
            inv.vessel_scnt
           FROM inv
          WHERE (inv.vessel_category = 'Special Floating Units'::text)
        UNION ALL
         SELECT inv.invoice_number,
            'notes_crude_ballast'::text,
            'Crude Oil Tankers'::text,
            'Ballast'::text,
            inv.vessel_scnt
           FROM inv
          WHERE ((inv.priced_condition = 'Ballast'::text) AND (inv.vessel_category = 'Chemical Tankers & Other Liquid Bulk Tankers'::text))
        ), priced AS (
         SELECT s.invoice_number,
            s.scenario,
            sum((t.rate_sdr_per_ton * (LEAST(s.tons, COALESCE(t.band_max_tons, s.tons)) - t.band_min_tons))) AS toll_exact,
            (array_agg(t.rate_sdr_per_ton ORDER BY t.band_order DESC))[1] AS terminal_rate,
            (array_agg(t.band_label ORDER BY t.band_order DESC))[1] AS terminal_band
           FROM (scenario s
             JOIN public.toll_rate_bands t ON (((t.vessel_category = s.category) AND (t.laden_ballast = s.cond) AND (s.tons > t.band_min_tons))))
          GROUP BY s.invoice_number, s.scenario
        ), hyp AS (
         SELECT i.invoice_number,
            i.vessel_id,
            i.invoice_date,
            i.scnt_tons,
            i.billed_sdr,
            i.billed_rate,
            i.vessel_name,
            i.vessel_category,
            i.condition,
            i.vessel_scnt,
            i.priced_condition,
            i.report_week,
            e.toll_exact AS expected_exact,
            round(e.toll_exact, 2) AS expected_sdr,
            e.terminal_rate,
            e.terminal_band,
            round(it.toll_exact, 2) AS invoice_tonnage_sdr,
            round((e.terminal_rate * i.vessel_scnt), 2) AS flat_terminal_sdr,
            round(cs.toll_exact, 2) AS condition_swapped_sdr,
            round(sb.toll_exact, 2) AS sfu_ballast_sdr,
            round(nc.toll_exact, 2) AS notes_crude_sdr,
            row_number() OVER w AS dup_rank,
            first_value(i.invoice_number) OVER w AS dup_first
           FROM (((((inv i
             JOIN priced e ON (((e.invoice_number = i.invoice_number) AND (e.scenario = 'expected'::text))))
             LEFT JOIN priced it ON (((it.invoice_number = i.invoice_number) AND (it.scenario = 'invoice_tonnage'::text))))
             LEFT JOIN priced cs ON (((cs.invoice_number = i.invoice_number) AND (cs.scenario = 'condition_swapped'::text))))
             LEFT JOIN priced sb ON (((sb.invoice_number = i.invoice_number) AND (sb.scenario = 'sfu_priced_ballast'::text))))
             LEFT JOIN priced nc ON (((nc.invoice_number = i.invoice_number) AND (nc.scenario = 'notes_crude_ballast'::text))))
          WINDOW w AS (PARTITION BY i.vessel_id, i.invoice_date, i.billed_sdr ORDER BY i.invoice_number)
        ), findings AS (
         SELECT h.invoice_number,
            h.vessel_id,
            h.invoice_date,
            h.scnt_tons,
            h.billed_sdr,
            h.billed_rate,
            h.vessel_name,
            h.vessel_category,
            h.condition,
            h.vessel_scnt,
            h.priced_condition,
            h.report_week,
            h.expected_exact,
            h.expected_sdr,
            h.terminal_rate,
            h.terminal_band,
            h.invoice_tonnage_sdr,
            h.flat_terminal_sdr,
            h.condition_swapped_sdr,
            h.sfu_ballast_sdr,
            h.notes_crude_sdr,
            h.dup_rank,
            h.dup_first,
            'duplicate_charge'::text AS check_code,
            NULL::text AS probable_cause,
            (0)::numeric AS expected_charge,
            h.dup_first AS duplicate_of,
            format('same vessel, date and amount as %s: the whole charge is billed twice'::text, h.dup_first) AS evidence
           FROM hyp h
          WHERE (h.dup_rank > 1)
        UNION ALL
         SELECT h.invoice_number,
            h.vessel_id,
            h.invoice_date,
            h.scnt_tons,
            h.billed_sdr,
            h.billed_rate,
            h.vessel_name,
            h.vessel_category,
            h.condition,
            h.vessel_scnt,
            h.priced_condition,
            h.report_week,
            h.expected_exact,
            h.expected_sdr,
            h.terminal_rate,
            h.terminal_band,
            h.invoice_tonnage_sdr,
            h.flat_terminal_sdr,
            h.condition_swapped_sdr,
            h.sfu_ballast_sdr,
            h.notes_crude_sdr,
            h.dup_rank,
            h.dup_first,
            'tonnage_mismatch'::text,
            NULL::text,
            h.expected_sdr,
            NULL::text,
            format('invoice SCNT %s <> vessel SCNT %s'::text, h.scnt_tons, h.vessel_scnt) AS format
           FROM hyp h
          WHERE ((h.dup_rank = 1) AND (h.scnt_tons <> h.vessel_scnt))
        UNION ALL
         SELECT h.invoice_number,
            h.vessel_id,
            h.invoice_date,
            h.scnt_tons,
            h.billed_sdr,
            h.billed_rate,
            h.vessel_name,
            h.vessel_category,
            h.condition,
            h.vessel_scnt,
            h.priced_condition,
            h.report_week,
            h.expected_exact,
            h.expected_sdr,
            h.terminal_rate,
            h.terminal_band,
            h.invoice_tonnage_sdr,
            h.flat_terminal_sdr,
            h.condition_swapped_sdr,
            h.sfu_ballast_sdr,
            h.notes_crude_sdr,
            h.dup_rank,
            h.dup_first,
            'amount_mismatch'::text,
                CASE
                    WHEN (abs((h.billed_sdr - h.invoice_tonnage_sdr)) <= 0.01) THEN 'billed_on_invoice_tonnage'::text
                    WHEN (abs((h.billed_sdr - h.flat_terminal_sdr)) <= 0.01) THEN 'flat_terminal_rate'::text
                    WHEN (abs((h.billed_sdr - h.condition_swapped_sdr)) <= 0.01) THEN 'condition_swapped'::text
                    WHEN (abs((h.billed_sdr - h.sfu_ballast_sdr)) <= 0.01) THEN 'sfu_priced_ballast'::text
                    WHEN (abs((h.billed_sdr - h.notes_crude_sdr)) <= 0.01) THEN 'notes_crude_ballast_rate'::text
                    ELSE 'unexplained'::text
                END AS "case",
            h.expected_sdr,
            NULL::text,
            format('billed %s SDR; tariff %s / %s at %s SCNT = %s SDR (progressive, terminal band %s at %s SDR/t)'::text, h.billed_sdr, h.vessel_category, h.priced_condition, h.vessel_scnt, h.expected_sdr, h.terminal_band, h.terminal_rate) AS format
           FROM hyp h
          WHERE ((h.dup_rank = 1) AND (abs((h.billed_sdr - h.expected_exact)) > 0.01))
        UNION ALL
         SELECT h.invoice_number,
            h.vessel_id,
            h.invoice_date,
            h.scnt_tons,
            h.billed_sdr,
            h.billed_rate,
            h.vessel_name,
            h.vessel_category,
            h.condition,
            h.vessel_scnt,
            h.priced_condition,
            h.report_week,
            h.expected_exact,
            h.expected_sdr,
            h.terminal_rate,
            h.terminal_band,
            h.invoice_tonnage_sdr,
            h.flat_terminal_sdr,
            h.condition_swapped_sdr,
            h.sfu_ballast_sdr,
            h.notes_crude_sdr,
            h.dup_rank,
            h.dup_first,
            'rate_mismatch'::text,
            NULL::text,
            h.expected_sdr,
            NULL::text,
            format('stored rate %s SDR/t <> terminal band %s rate %s SDR/t'::text, h.billed_rate, h.terminal_band, h.terminal_rate) AS format
           FROM hyp h
          WHERE ((h.dup_rank = 1) AND (h.billed_rate IS NOT NULL) AND (h.billed_rate <> h.terminal_rate))
        )
 SELECT report_week,
    invoice_number,
    invoice_date,
    vessel_id,
    vessel_name,
    vessel_category,
    condition AS vessel_condition,
    check_code,
    probable_cause,
    billed_sdr,
    expected_charge AS expected_sdr,
    round((billed_sdr - expected_charge), 2) AS difference_sdr,
    duplicate_of,
    evidence,
        CASE
            WHEN (probable_cause = 'notes_crude_ballast_rate'::text) THEN 'manual_review'::text
            ELSE 'error'::text
        END AS review
   FROM findings;


--
-- Name: VIEW invoice_audit; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.invoice_audit IS 'Invoice audit findings (Agents plan §5a, migration 015): every invoice recomputed from the progressive toll bands (ADR-004); one row per finding (duplicate_charge, tonnage_mismatch, amount_mismatch with a probable cause, rate_mismatch). No row = the invoice passed. Read by the invoice_audit tool and the Exceptions page. Level 2, Finance.';


--
-- Name: COLUMN invoice_audit.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.report_week IS 'Report week of the invoice date (ISO 2025 week; NULL for 2026-W01)';


--
-- Name: COLUMN invoice_audit.invoice_number; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.invoice_number IS 'The invoice with the finding';


--
-- Name: COLUMN invoice_audit.invoice_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.invoice_date IS 'Invoice date';


--
-- Name: COLUMN invoice_audit.vessel_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.vessel_id IS 'The billed vessel';


--
-- Name: COLUMN invoice_audit.vessel_name; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.vessel_name IS 'Vessel name';


--
-- Name: COLUMN invoice_audit.vessel_category; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.vessel_category IS 'Tariff category of the vessel (vessels.vessel_type)';


--
-- Name: COLUMN invoice_audit.vessel_condition; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.vessel_condition IS 'Condition of the vessel (vessels.condition); Special Floating Units are priced Laden';


--
-- Name: COLUMN invoice_audit.check_code; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.check_code IS 'duplicate_charge | tonnage_mismatch | amount_mismatch | rate_mismatch';


--
-- Name: COLUMN invoice_audit.probable_cause; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.probable_cause IS 'amount_mismatch only: billed_on_invoice_tonnage | flat_terminal_rate | condition_swapped | sfu_priced_ballast | notes_crude_ballast_rate | unexplained (the first hypothesis that reproduces the billed amount within 0.01 SDR)';


--
-- Name: COLUMN invoice_audit.billed_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.billed_sdr IS 'Amount billed (SDR)';


--
-- Name: COLUMN invoice_audit.expected_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.expected_sdr IS 'Correct charge (SDR): the progressive toll of the vessel; 0 for a duplicate';


--
-- Name: COLUMN invoice_audit.difference_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.difference_sdr IS 'billed - expected (SDR): positive = overbilled, negative = underbilled';


--
-- Name: COLUMN invoice_audit.duplicate_of; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.duplicate_of IS 'duplicate_charge only: the original invoice number';


--
-- Name: COLUMN invoice_audit.evidence; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.evidence IS 'The numbers behind the finding (tons, category, condition, band, rate)';


--
-- Name: COLUMN invoice_audit.review; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.invoice_audit.review IS 'error | manual_review: manual_review = priced by a tariff Notes rule (a ballast chemical tanker at the Crude Oil Tankers ballast rates — right if it is an oil/chemical tanker, migration 019) — confirm the rule, it may be correct; not counted as money at stake';


--
-- Name: kpi_customer_13w; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.kpi_customer_13w AS
 WITH grid AS (
         SELECT w.report_week,
            w.week_start,
            w.week_end,
            c.customer_id
           FROM (finance.dim_week w
             CROSS JOIN public.customers c)
        ), billing AS (
         SELECT g.report_week,
            g.customer_id,
            COALESCE(sum(f.amount_sdr) FILTER (WHERE (f.invoice_date >= g.week_start)), (0)::numeric) AS billed_week_sdr,
            COALESCE(sum(f.amount_sdr), (0)::numeric) AS billed_13w_sdr
           FROM (grid g
             LEFT JOIN finance.fact_invoice f ON (((f.customer_id = g.customer_id) AND ((f.invoice_date >= (g.week_end - 90)) AND (f.invoice_date <= g.week_end)))))
          GROUP BY g.report_week, g.customer_id
        ), open_ar AS (
         SELECT fact_ar_snapshot.report_week,
            fact_ar_snapshot.customer_id,
            sum(fact_ar_snapshot.amount_sdr) AS ar_sdr,
            sum(fact_ar_snapshot.amount_sdr) FILTER (WHERE fact_ar_snapshot.is_overdue) AS overdue_sdr
           FROM finance.fact_ar_snapshot
          GROUP BY fact_ar_snapshot.report_week, fact_ar_snapshot.customer_id
        ), ranked AS (
         SELECT b.report_week,
            b.customer_id,
            b.billed_week_sdr,
            b.billed_13w_sdr,
            sum(b.billed_13w_sdr) OVER (PARTITION BY b.report_week) AS total_13w_sdr,
            row_number() OVER (PARTITION BY b.report_week ORDER BY b.billed_13w_sdr DESC, b.customer_id) AS rank_13w
           FROM billing b
        ), prev AS (
         SELECT r.report_week,
            r.customer_id,
            c.customer_name,
            c.segment,
            c.country,
            c.credit_rating,
            c.payment_terms_days,
            round(r.billed_week_sdr, 2) AS billed_week_sdr,
            round(r.billed_13w_sdr, 2) AS billed_13w_sdr,
            round((((100)::numeric * r.billed_13w_sdr) / NULLIF(r.total_13w_sdr, (0)::numeric)), 2) AS share_13w_pct,
            r.rank_13w,
            lag(r.rank_13w) OVER (PARTITION BY r.customer_id ORDER BY r.report_week) AS rank_13w_prev,
            ((r.rank_13w <= 10) AND (r.billed_13w_sdr > (0)::numeric)) AS is_top10,
            round(COALESCE(o.ar_sdr, (0)::numeric), 2) AS ar_sdr,
            round(COALESCE(o.overdue_sdr, (0)::numeric), 2) AS overdue_sdr
           FROM ((ranked r
             JOIN public.customers c ON ((c.customer_id = r.customer_id)))
             LEFT JOIN open_ar o ON (((o.report_week = r.report_week) AND (o.customer_id = r.customer_id))))
        ), punctuality AS (
         SELECT g.report_week,
            g.customer_id,
            ((100.0 * (count(p_1.invoice_number) FILTER (WHERE (p_1.days_paid_after_due <= 0)))::numeric) / (NULLIF(count(p_1.invoice_number), 0))::numeric) AS ontime_13w
           FROM (grid g
             LEFT JOIN finance.fact_payment p_1 ON (((p_1.customer_id = g.customer_id) AND ((p_1.paid_date >= (g.week_end - 90)) AND (p_1.paid_date <= g.week_end)))))
          GROUP BY g.report_week, g.customer_id
        )
 SELECT p.report_week,
    p.customer_id,
    p.customer_name,
    p.segment,
    p.country,
    p.credit_rating,
    p.payment_terms_days,
    p.billed_week_sdr,
    p.billed_13w_sdr,
    p.share_13w_pct,
    p.rank_13w,
    p.rank_13w_prev,
    p.is_top10,
    p.ar_sdr,
    p.overdue_sdr,
    round((((100)::numeric * p.ar_sdr) / NULLIF(p.billed_13w_sdr, (0)::numeric)), 2) AS ar_to_billed_13w_pct,
        CASE
            WHEN (p.report_week <= 13) THEN NULL::boolean
            ELSE ((p.ar_sdr >= (1000000)::numeric) AND ((p.billed_13w_sdr = (0)::numeric) OR (p.ar_sdr >= (0.8 * p.billed_13w_sdr))))
        END AS is_watchlist,
    round(pu.ontime_13w, 2) AS ontime_13w_pct
   FROM (prev p
     JOIN punctuality pu ON (((pu.report_week = p.report_week) AND (pu.customer_id = p.customer_id))));


--
-- Name: VIEW kpi_customer_13w; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.kpi_customer_13w IS 'Every customer in every report week: billing of the week and of the trailing 13 weeks (91 days ending Sunday), share, rank, receivables. Level 2, Finance.';


--
-- Name: COLUMN kpi_customer_13w.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.report_week IS 'Report week';


--
-- Name: COLUMN kpi_customer_13w.customer_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.customer_id IS 'Customer id';


--
-- Name: COLUMN kpi_customer_13w.customer_name; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.customer_name IS 'Customer name';


--
-- Name: COLUMN kpi_customer_13w.segment; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.segment IS 'Customer segment';


--
-- Name: COLUMN kpi_customer_13w.country; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.country IS 'Head-office country';


--
-- Name: COLUMN kpi_customer_13w.credit_rating; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.credit_rating IS 'Credit rating A, B or C';


--
-- Name: COLUMN kpi_customer_13w.payment_terms_days; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.payment_terms_days IS 'Payment terms in days';


--
-- Name: COLUMN kpi_customer_13w.billed_week_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.billed_week_sdr IS 'Billed in the report week (SDR, 2 decimals)';


--
-- Name: COLUMN kpi_customer_13w.billed_13w_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.billed_13w_sdr IS 'Billed in the trailing 13 weeks = 91 days ending the week''s Sunday (SDR, 2 decimals)';


--
-- Name: COLUMN kpi_customer_13w.share_13w_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.share_13w_pct IS 'Share of all billing in the trailing 13 weeks, percent (2 decimals)';


--
-- Name: COLUMN kpi_customer_13w.rank_13w; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.rank_13w IS 'Rank by billed_13w_sdr (1 = largest; ties by customer_id)';


--
-- Name: COLUMN kpi_customer_13w.rank_13w_prev; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.rank_13w_prev IS 'rank_13w in the previous report week; NULL in week 1';


--
-- Name: COLUMN kpi_customer_13w.is_top10; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.is_top10 IS 'True for ranks 1–10 with billing > 0 in the trailing 13 weeks';


--
-- Name: COLUMN kpi_customer_13w.ar_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.ar_sdr IS 'Open receivables of the customer as of the week''s Sunday (SDR)';


--
-- Name: COLUMN kpi_customer_13w.overdue_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.overdue_sdr IS 'Overdue part of ar_sdr (SDR)';


--
-- Name: COLUMN kpi_customer_13w.ar_to_billed_13w_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.ar_to_billed_13w_pct IS 'Customer AR ÷ its own 13-week billing × 100; NULL when it billed nothing in 13 weeks (M15).';


--
-- Name: COLUMN kpi_customer_13w.is_watchlist; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.is_watchlist IS 'AR ≥ 1,000,000 SDR and (no 13-week billing or AR ≥ 80 % of it); NULL in warm-up weeks 1–13 (M15, W-R1 / W-R7).';


--
-- Name: COLUMN kpi_customer_13w.ontime_13w_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_customer_13w.ontime_13w_pct IS 'Share of the customer''s payments in the 91 days ending Sunday paid on or before due, percent; NULL without payments (M16).';


--
-- Name: kpi_overdue_list; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.kpi_overdue_list AS
 SELECT a.report_week,
    a.as_of_date,
    a.invoice_number,
    a.customer_id,
    c.customer_name,
    a.vessel_id,
    v.vessel_name,
    a.vessel_category,
    a.invoice_date,
    a.due_date,
    a.amount_sdr,
    a.days_past_due,
    a.aging_bucket,
    row_number() OVER (PARTITION BY a.report_week ORDER BY a.amount_sdr DESC, a.invoice_number) AS rank_by_amount
   FROM ((finance.fact_ar_snapshot a
     JOIN public.customers c ON ((c.customer_id = a.customer_id)))
     JOIN public.vessels v ON ((v.vessel_id = a.vessel_id)))
  WHERE a.is_overdue;


--
-- Name: VIEW kpi_overdue_list; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.kpi_overdue_list IS 'Overdue invoices (≥ 1 day past due) as of each report week, ranked by amount. Level 2, Finance.';


--
-- Name: COLUMN kpi_overdue_list.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.report_week IS 'Report week';


--
-- Name: COLUMN kpi_overdue_list.as_of_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.as_of_date IS 'Sunday of the report week';


--
-- Name: COLUMN kpi_overdue_list.invoice_number; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.invoice_number IS 'Overdue invoice';


--
-- Name: COLUMN kpi_overdue_list.customer_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.customer_id IS 'Customer id';


--
-- Name: COLUMN kpi_overdue_list.customer_name; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.customer_name IS 'Customer name';


--
-- Name: COLUMN kpi_overdue_list.vessel_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.vessel_id IS 'Vessel id';


--
-- Name: COLUMN kpi_overdue_list.vessel_name; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.vessel_name IS 'Vessel name';


--
-- Name: COLUMN kpi_overdue_list.vessel_category; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.vessel_category IS 'Vessel category';


--
-- Name: COLUMN kpi_overdue_list.invoice_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.invoice_date IS 'Invoice date';


--
-- Name: COLUMN kpi_overdue_list.due_date; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.due_date IS 'Derived due date';


--
-- Name: COLUMN kpi_overdue_list.amount_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.amount_sdr IS 'Open amount (SDR)';


--
-- Name: COLUMN kpi_overdue_list.days_past_due; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.days_past_due IS 'Days past due as of the Sunday';


--
-- Name: COLUMN kpi_overdue_list.aging_bucket; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.aging_bucket IS '1-30, 31-60, 61-90 or 90+';


--
-- Name: COLUMN kpi_overdue_list.rank_by_amount; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_overdue_list.rank_by_amount IS 'Rank within the week by amount (1 = largest)';


--
-- Name: budget_weekly; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.budget_weekly (
    budget_year integer NOT NULL,
    iso_week integer NOT NULL,
    vessel_category text NOT NULL,
    budget_sdr numeric NOT NULL,
    CONSTRAINT budget_weekly_amount_chk CHECK ((budget_sdr >= (0)::numeric)),
    CONSTRAINT budget_weekly_category_chk CHECK ((vessel_category = ANY (ARRAY['Chemical Tankers & Other Liquid Bulk Tankers'::text, 'Containerships'::text, 'Crude Oil Tankers'::text, 'Cruise Ships'::text, 'Dry Bulk Vessels'::text, 'General Cargo / Multi-Purpose / Heavy Lift Vessels'::text, 'Liquefied Natural Gas (LNG) Carriers'::text, 'Liquefied Petroleum Gas (LPG) Carriers'::text, 'Other Vessels'::text, 'Petroleum Product Tankers'::text, 'Roll-On/Roll-Off (Ro/Ro) Vessels'::text, 'Special Floating Units'::text, 'Vehicles Carriers'::text]))),
    CONSTRAINT budget_weekly_week_chk CHECK (((iso_week >= 1) AND (iso_week <= 52))),
    CONSTRAINT budget_weekly_year_chk CHECK ((budget_year = 2025))
);


--
-- Name: TABLE budget_weekly; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.budget_weekly IS 'Weekly budget 2025 per vessel category: a planning model (fleet x 2.0 transits x median-tonnage laden toll, seasonal +/-6 %), not fitted to the invoices (Agents plan §4a R6). Level 2, Finance.';


--
-- Name: COLUMN budget_weekly.budget_year; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.budget_weekly.budget_year IS 'Budget year (2025 only)';


--
-- Name: COLUMN budget_weekly.iso_week; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.budget_weekly.iso_week IS 'ISO week of the budget year';


--
-- Name: COLUMN budget_weekly.vessel_category; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.budget_weekly.vessel_category IS 'Suez tariff vessel category (same 13 values as vessels.vessel_type)';


--
-- Name: COLUMN budget_weekly.budget_sdr; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.budget_weekly.budget_sdr IS 'Budgeted transit dues in SDR';


--
-- Name: kpi_weekly; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.kpi_weekly AS
 WITH billed AS (
         SELECT w.report_week,
            count(f.invoice_id) AS invoices_billed,
            COALESCE(sum(f.amount_sdr), (0)::numeric) AS billed_sdr
           FROM (finance.dim_week w
             LEFT JOIN finance.fact_invoice f ON (((f.invoice_date >= w.week_start) AND (f.invoice_date <= w.week_end))))
          GROUP BY w.report_week
        ), collected AS (
         SELECT w.report_week,
            count(p_1.invoice_number) AS payments_received,
            COALESCE(sum(p_1.amount_sdr), (0)::numeric) AS collected_sdr
           FROM (finance.dim_week w
             LEFT JOIN finance.fact_payment p_1 ON (((p_1.paid_date >= w.week_start) AND (p_1.paid_date <= w.week_end))))
          GROUP BY w.report_week
        ), ar AS (
         SELECT w.report_week,
            count(a.invoice_number) AS ar_invoices,
            COALESCE(sum(a.amount_sdr), (0)::numeric) AS ar_sdr,
            count(a.invoice_number) FILTER (WHERE a.is_overdue) AS overdue_invoices,
            COALESCE(sum(a.amount_sdr) FILTER (WHERE a.is_overdue), (0)::numeric) AS overdue_sdr,
            COALESCE(sum(a.amount_sdr) FILTER (WHERE (a.aging_bucket = 'current'::text)), (0)::numeric) AS aging_current_sdr,
            COALESCE(sum(a.amount_sdr) FILTER (WHERE (a.aging_bucket = '1-30'::text)), (0)::numeric) AS aging_1_30_sdr,
            COALESCE(sum(a.amount_sdr) FILTER (WHERE (a.aging_bucket = '31-60'::text)), (0)::numeric) AS aging_31_60_sdr,
            COALESCE(sum(a.amount_sdr) FILTER (WHERE (a.aging_bucket = '61-90'::text)), (0)::numeric) AS aging_61_90_sdr,
            COALESCE(sum(a.amount_sdr) FILTER (WHERE (a.aging_bucket = '90+'::text)), (0)::numeric) AS aging_90_plus_sdr
           FROM (finance.dim_week w
             LEFT JOIN finance.fact_ar_snapshot a ON ((a.report_week = w.report_week)))
          GROUP BY w.report_week
        ), dso_base AS (
         SELECT w.report_week,
            COALESCE(sum(f.amount_sdr), (0)::numeric) AS dso_window_billed_sdr
           FROM (finance.dim_week w
             LEFT JOIN finance.fact_invoice f ON (((f.invoice_date >= w.dso_window_start) AND (f.invoice_date <= w.week_end))))
          GROUP BY w.report_week
        ), budget AS (
         SELECT budget_weekly.iso_week AS report_week,
            sum(budget_weekly.budget_sdr) AS budget_sdr
           FROM public.budget_weekly
          WHERE (budget_weekly.budget_year = 2025)
          GROUP BY budget_weekly.iso_week
        ), concentration AS (
         SELECT kpi_customer_13w.report_week,
            (sum(kpi_customer_13w.billed_13w_sdr) FILTER (WHERE kpi_customer_13w.is_top10) / NULLIF(sum(kpi_customer_13w.billed_13w_sdr), (0)::numeric)) AS top10_share
           FROM finance.kpi_customer_13w
          GROUP BY kpi_customer_13w.report_week
        ), base AS (
         SELECT w.report_week,
            w.iso_week_label,
            w.week_start,
            w.week_end,
            w.is_warmup,
            w.dso_window_days,
            b.invoices_billed,
            b.billed_sdr,
            c.payments_received,
            c.collected_sdr,
            a.ar_invoices,
            a.ar_sdr,
            a.overdue_invoices,
            a.overdue_sdr,
            a.aging_current_sdr,
            a.aging_1_30_sdr,
            a.aging_31_60_sdr,
            a.aging_61_90_sdr,
            a.aging_90_plus_sdr,
            d.dso_window_billed_sdr,
            ((a.ar_sdr / NULLIF(d.dso_window_billed_sdr, (0)::numeric)) * (w.dso_window_days)::numeric) AS dso_days,
            bu.budget_sdr,
            k.top10_share
           FROM ((((((finance.dim_week w
             JOIN billed b ON ((b.report_week = w.report_week)))
             JOIN collected c ON ((c.report_week = w.report_week)))
             JOIN ar a ON ((a.report_week = w.report_week)))
             JOIN dso_base d ON ((d.report_week = w.report_week)))
             LEFT JOIN budget bu ON ((bu.report_week = w.report_week)))
             LEFT JOIN concentration k ON ((k.report_week = w.report_week)))
        ), prev AS (
         SELECT base.report_week,
            base.iso_week_label,
            base.week_start,
            base.week_end,
            base.is_warmup,
            base.invoices_billed,
            round(base.billed_sdr, 2) AS billed_sdr,
            base.payments_received,
            round(base.collected_sdr, 2) AS collected_sdr,
            base.ar_invoices,
            round(base.ar_sdr, 2) AS ar_sdr,
            base.overdue_invoices,
            round(base.overdue_sdr, 2) AS overdue_sdr,
            round(base.aging_current_sdr, 2) AS aging_current_sdr,
            round(base.aging_1_30_sdr, 2) AS aging_1_30_sdr,
            round(base.aging_31_60_sdr, 2) AS aging_31_60_sdr,
            round(base.aging_61_90_sdr, 2) AS aging_61_90_sdr,
            round(base.aging_90_plus_sdr, 2) AS aging_90_plus_sdr,
            base.dso_window_days,
            round(base.dso_window_billed_sdr, 2) AS dso_window_billed_sdr,
            round(base.dso_days, 1) AS dso_days,
            round(base.budget_sdr, 2) AS budget_sdr,
            round((base.billed_sdr - base.budget_sdr), 2) AS budget_variance_sdr,
            round((((100)::numeric * (base.billed_sdr - base.budget_sdr)) / NULLIF(base.budget_sdr, (0)::numeric)), 2) AS budget_variance_pct,
            round(((100)::numeric * base.top10_share), 2) AS top10_share_13w_pct,
            round((((100)::numeric * (base.billed_sdr - lag(base.billed_sdr) OVER wk)) / NULLIF(lag(base.billed_sdr) OVER wk, (0)::numeric)), 2) AS billed_wow_pct,
            round((((100)::numeric * (base.collected_sdr - lag(base.collected_sdr) OVER wk)) / NULLIF(lag(base.collected_sdr) OVER wk, (0)::numeric)), 2) AS collected_wow_pct,
            round((((100)::numeric * (base.ar_sdr - lag(base.ar_sdr) OVER wk)) / NULLIF(lag(base.ar_sdr) OVER wk, (0)::numeric)), 2) AS ar_wow_pct,
            round((((100)::numeric * (base.overdue_sdr - lag(base.overdue_sdr) OVER wk)) / NULLIF(lag(base.overdue_sdr) OVER wk, (0)::numeric)), 2) AS overdue_wow_pct,
            round((base.dso_days - lag(base.dso_days) OVER wk), 1) AS dso_wow_days
           FROM base
          WINDOW wk AS (ORDER BY base.report_week)
        ), rolling AS (
         SELECT base.report_week,
            count(*) OVER r13 AS roll_window_weeks,
            sum(base.billed_sdr) OVER r13 AS billed_13w_sdr,
            sum(base.budget_sdr) OVER r13 AS budget_13w_sdr,
            round(((base.aging_current_sdr / NULLIF(base.dso_window_billed_sdr, (0)::numeric)) * (base.dso_window_days)::numeric), 1) AS dso_best_days
           FROM base
          WINDOW r13 AS (ORDER BY base.report_week ROWS BETWEEN 12 PRECEDING AND CURRENT ROW)
        ), swing AS (
         SELECT p_1.report_week,
            ( SELECT
                        CASE
                            WHEN (count(*) >= 8) THEN percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((abs(x.billed_wow_pct))::double precision))
                            ELSE NULL::double precision
                        END AS "case"
                   FROM prev x
                  WHERE (((x.report_week >= (p_1.report_week - 12)) AND (x.report_week <= p_1.report_week)) AND (x.billed_wow_pct IS NOT NULL))) AS billed_typ,
            ( SELECT
                        CASE
                            WHEN (count(*) >= 8) THEN percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((abs(x.collected_wow_pct))::double precision))
                            ELSE NULL::double precision
                        END AS "case"
                   FROM prev x
                  WHERE (((x.report_week >= (p_1.report_week - 12)) AND (x.report_week <= p_1.report_week)) AND (x.collected_wow_pct IS NOT NULL))) AS collected_typ,
            ( SELECT
                        CASE
                            WHEN (count(*) >= 8) THEN percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((abs(x.ar_wow_pct))::double precision))
                            ELSE NULL::double precision
                        END AS "case"
                   FROM prev x
                  WHERE (((x.report_week >= (p_1.report_week - 12)) AND (x.report_week <= p_1.report_week)) AND (x.ar_wow_pct IS NOT NULL))) AS ar_typ,
            ( SELECT
                        CASE
                            WHEN (count(*) >= 8) THEN percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((abs(x.overdue_wow_pct))::double precision))
                            ELSE NULL::double precision
                        END AS "case"
                   FROM prev x
                  WHERE (((x.report_week >= (p_1.report_week - 12)) AND (x.report_week <= p_1.report_week)) AND (x.overdue_wow_pct IS NOT NULL))) AS overdue_typ
           FROM prev p_1
        ), flows AS (
         SELECT w.report_week,
            COALESCE(sum(f.amount_sdr) FILTER (WHERE (((f.due_date >= (w.week_end - 7)) AND (f.due_date <= (w.week_end - 1))) AND ((f.paid_date IS NULL) OR (f.paid_date > w.week_end)))), (0)::numeric) AS overdue_new_sdr,
            COALESCE(sum(f.amount_sdr) FILTER (WHERE ((f.due_date <= (w.week_end - 8)) AND ((f.paid_date >= w.week_start) AND (f.paid_date <= w.week_end)))), (0)::numeric) AS overdue_paid_sdr,
            COALESCE(sum(f.amount_sdr) FILTER (WHERE ((f.due_date >= w.week_start) AND (f.due_date <= w.week_end))), (0)::numeric) AS due_week_sdr,
            COALESCE(sum(f.amount_sdr) FILTER (WHERE (((f.due_date >= w.week_start) AND (f.due_date <= w.week_end)) AND (f.paid_date <= w.week_end))), (0)::numeric) AS due_week_collected_sdr
           FROM (finance.dim_week w
             CROSS JOIN finance.fact_invoice f)
          GROUP BY w.report_week
        ), punctuality AS (
         SELECT w.report_week,
            ((100.0 * (count(p_1.invoice_number) FILTER (WHERE (p_1.days_paid_after_due <= 0)))::numeric) / (NULLIF(count(p_1.invoice_number), 0))::numeric) AS ontime_13w
           FROM (finance.dim_week w
             LEFT JOIN finance.fact_payment p_1 ON (((p_1.paid_date >= (w.week_end - 90)) AND (p_1.paid_date <= w.week_end))))
          GROUP BY w.report_week
        )
 SELECT p.report_week,
    p.iso_week_label,
    p.week_start,
    p.week_end,
    p.is_warmup,
    p.invoices_billed,
    p.billed_sdr,
    p.payments_received,
    p.collected_sdr,
    p.ar_invoices,
    p.ar_sdr,
    p.overdue_invoices,
    p.overdue_sdr,
    p.aging_current_sdr,
    p.aging_1_30_sdr,
    p.aging_31_60_sdr,
    p.aging_61_90_sdr,
    p.aging_90_plus_sdr,
    p.dso_window_days,
    p.dso_window_billed_sdr,
    p.dso_days,
    p.budget_sdr,
    p.budget_variance_sdr,
    p.budget_variance_pct,
    p.top10_share_13w_pct,
    p.billed_wow_pct,
    p.collected_wow_pct,
    p.ar_wow_pct,
    p.overdue_wow_pct,
    p.dso_wow_days,
    r.roll_window_weeks,
    round(r.billed_13w_sdr, 2) AS billed_13w_sdr,
    round(r.budget_13w_sdr, 2) AS budget_13w_sdr,
    round((((100)::numeric * (r.billed_13w_sdr - r.budget_13w_sdr)) / NULLIF(r.budget_13w_sdr, (0)::numeric)), 2) AS budget_variance_13w_pct,
    r.dso_best_days,
    (p.dso_days - r.dso_best_days) AS dso_delinquency_days,
    round((s.billed_typ)::numeric, 2) AS billed_wow_typical_pct,
    round((s.collected_typ)::numeric, 2) AS collected_wow_typical_pct,
    round((s.ar_typ)::numeric, 2) AS ar_wow_typical_pct,
    round((s.overdue_typ)::numeric, 2) AS overdue_wow_typical_pct,
    round(fl.overdue_new_sdr, 2) AS overdue_new_sdr,
    round(fl.overdue_paid_sdr, 2) AS overdue_paid_sdr,
    round(fl.due_week_sdr, 2) AS due_week_sdr,
    round(fl.due_week_collected_sdr, 2) AS due_week_collected_sdr,
    round((((100)::numeric * fl.due_week_collected_sdr) / NULLIF(fl.due_week_sdr, (0)::numeric)), 2) AS due_week_collected_pct,
    round(pu.ontime_13w, 2) AS ontime_13w_pct
   FROM ((((prev p
     JOIN rolling r ON ((r.report_week = p.report_week)))
     JOIN swing s ON ((s.report_week = p.report_week)))
     JOIN flows fl ON ((fl.report_week = p.report_week)))
     JOIN punctuality pu ON ((pu.report_week = p.report_week)));


--
-- Name: VIEW kpi_weekly; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.kpi_weekly IS 'Company KPIs, one row per report week (definitions: docs/finance_metrics.md). Money SDR 2 decimals, *_pct percent 2 decimals, days 1 decimal; WoW NULL in week 1. Level 2, Finance.';


--
-- Name: COLUMN kpi_weekly.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.report_week IS 'Report week 1–52';


--
-- Name: COLUMN kpi_weekly.iso_week_label; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.iso_week_label IS 'ISO week as text';


--
-- Name: COLUMN kpi_weekly.week_start; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.week_start IS 'Monday of the week';


--
-- Name: COLUMN kpi_weekly.week_end; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.week_end IS 'Sunday of the week (as of 23:59)';


--
-- Name: COLUMN kpi_weekly.is_warmup; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.is_warmup IS 'Weeks 1–13: under 91 days of history, receivables still building up; DSO on a shorter window';


--
-- Name: COLUMN kpi_weekly.invoices_billed; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.invoices_billed IS 'Number of invoices dated in the week';


--
-- Name: COLUMN kpi_weekly.billed_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.billed_sdr IS 'Billed revenue: sum of invoice amounts dated in the week (SDR)';


--
-- Name: COLUMN kpi_weekly.payments_received; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.payments_received IS 'Number of payments dated in the week';


--
-- Name: COLUMN kpi_weekly.collected_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.collected_sdr IS 'Collections: sum of payments dated in the week (SDR)';


--
-- Name: COLUMN kpi_weekly.ar_invoices; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.ar_invoices IS 'Number of open invoices at the week end';


--
-- Name: COLUMN kpi_weekly.ar_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.ar_sdr IS 'Accounts receivable at the week end: invoices issued by Sunday and unpaid by Sunday (SDR)';


--
-- Name: COLUMN kpi_weekly.overdue_invoices; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.overdue_invoices IS 'Number of open invoices at least 1 day past due';


--
-- Name: COLUMN kpi_weekly.overdue_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.overdue_sdr IS 'Overdue receivables (≥ 1 day past due) at the week end (SDR)';


--
-- Name: COLUMN kpi_weekly.aging_current_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.aging_current_sdr IS 'Receivables not yet due (SDR)';


--
-- Name: COLUMN kpi_weekly.aging_1_30_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.aging_1_30_sdr IS 'Receivables 1–30 days past due (SDR)';


--
-- Name: COLUMN kpi_weekly.aging_31_60_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.aging_31_60_sdr IS 'Receivables 31–60 days past due (SDR)';


--
-- Name: COLUMN kpi_weekly.aging_61_90_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.aging_61_90_sdr IS 'Receivables 61–90 days past due (SDR)';


--
-- Name: COLUMN kpi_weekly.aging_90_plus_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.aging_90_plus_sdr IS 'Receivables more than 90 days past due (SDR)';


--
-- Name: COLUMN kpi_weekly.dso_window_days; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.dso_window_days IS 'Days in the DSO window (91, fewer in warm-up weeks)';


--
-- Name: COLUMN kpi_weekly.dso_window_billed_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.dso_window_billed_sdr IS 'Billed revenue inside the DSO window (SDR)';


--
-- Name: COLUMN kpi_weekly.dso_days; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.dso_days IS 'DSO = ar_sdr ÷ dso_window_billed_sdr × dso_window_days (owner decision P2-1), 1 decimal';


--
-- Name: COLUMN kpi_weekly.budget_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.budget_sdr IS 'Weekly budget, all categories (SDR)';


--
-- Name: COLUMN kpi_weekly.budget_variance_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.budget_variance_sdr IS 'billed_sdr − budget_sdr (SDR)';


--
-- Name: COLUMN kpi_weekly.budget_variance_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.budget_variance_pct IS '(billed − budget) ÷ budget, percent';


--
-- Name: COLUMN kpi_weekly.top10_share_13w_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.top10_share_13w_pct IS 'Share of the 10 largest customers in the trailing 13 weeks'' billing, percent';


--
-- Name: COLUMN kpi_weekly.billed_wow_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.billed_wow_pct IS 'Billed revenue change vs the previous week, percent';


--
-- Name: COLUMN kpi_weekly.collected_wow_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.collected_wow_pct IS 'Collections change vs the previous week, percent';


--
-- Name: COLUMN kpi_weekly.ar_wow_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.ar_wow_pct IS 'Receivables change vs the previous week, percent';


--
-- Name: COLUMN kpi_weekly.overdue_wow_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.overdue_wow_pct IS 'Overdue receivables change vs the previous week, percent';


--
-- Name: COLUMN kpi_weekly.dso_wow_days; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.dso_wow_days IS 'DSO change vs the previous week, in days';


--
-- Name: COLUMN kpi_weekly.roll_window_weeks; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.roll_window_weeks IS 'Weeks in the rolling window of the *_13w columns: 13, or the report week number before week 13 (M9b).';


--
-- Name: COLUMN kpi_weekly.billed_13w_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.billed_13w_sdr IS 'Billed revenue of the rolling window (weeks w-12 … w, from week 1 before week 13), SDR (M9b).';


--
-- Name: COLUMN kpi_weekly.budget_13w_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.budget_13w_sdr IS 'Budget of the same rolling window, SDR (M9b).';


--
-- Name: COLUMN kpi_weekly.budget_variance_13w_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.budget_variance_13w_pct IS '(billed_13w − budget_13w) ÷ budget_13w × 100: the period''s position against plan (M9b).';


--
-- Name: COLUMN kpi_weekly.dso_best_days; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.dso_best_days IS 'Best-possible DSO: current (not overdue) AR ÷ DSO-window billing × window days, 1 decimal (M12).';


--
-- Name: COLUMN kpi_weekly.dso_delinquency_days; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.dso_delinquency_days IS 'dso_days − dso_best_days: the days of billing outstanding because customers pay late (M12).';


--
-- Name: COLUMN kpi_weekly.billed_wow_typical_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.billed_wow_typical_pct IS 'Typical weekly swing of billed: median |billed_wow_pct| over the rolling window, at least 8 values, else NULL (M13).';


--
-- Name: COLUMN kpi_weekly.collected_wow_typical_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.collected_wow_typical_pct IS 'Typical weekly swing of collected: median |collected_wow_pct| over the rolling window, at least 8 values (M13).';


--
-- Name: COLUMN kpi_weekly.ar_wow_typical_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.ar_wow_typical_pct IS 'Typical weekly swing of AR: median |ar_wow_pct| over the rolling window, at least 8 values (M13).';


--
-- Name: COLUMN kpi_weekly.overdue_wow_typical_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.overdue_wow_typical_pct IS 'Typical weekly swing of overdue: median |overdue_wow_pct| over the rolling window, at least 8 values (M13).';


--
-- Name: COLUMN kpi_weekly.overdue_new_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.overdue_new_sdr IS 'Invoices that became overdue in the week (due from the previous Sunday to this Saturday) and are unpaid at Sunday, SDR (M14).';


--
-- Name: COLUMN kpi_weekly.overdue_paid_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.overdue_paid_sdr IS 'Payments in the week on invoices already overdue at the previous Sunday, SDR; overdue change = new − paid (M14).';


--
-- Name: COLUMN kpi_weekly.due_week_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.due_week_sdr IS 'Invoices falling due in the week (Monday–Sunday), SDR (M14).';


--
-- Name: COLUMN kpi_weekly.due_week_collected_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.due_week_collected_sdr IS 'Part of due_week_sdr paid by the week''s Sunday, SDR (M14).';


--
-- Name: COLUMN kpi_weekly.due_week_collected_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.due_week_collected_pct IS 'due_week_collected_sdr ÷ due_week_sdr × 100 (M14).';


--
-- Name: COLUMN kpi_weekly.ontime_13w_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly.ontime_13w_pct IS 'Share of the payments made in the 91 days ending Sunday that were paid on or before due, percent (M16).';


--
-- Name: kpi_traffic_link; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.kpi_traffic_link AS
 WITH t AS (
         SELECT ((floor((((suez_transits_daily.date - '2024-12-30'::date))::numeric / 7.0)))::integer + 1) AS week,
            sum(suez_transits_daily.n_total) AS transits
           FROM external.suez_transits_daily
          GROUP BY ((floor((((suez_transits_daily.date - '2024-12-30'::date))::numeric / 7.0)))::integer + 1)
        ), k AS (
         SELECT kw.report_week,
            kw.invoices_billed,
            t0.transits AS transits_week,
            t1.transits AS transits_prev_week
           FROM ((finance.kpi_weekly kw
             JOIN t t0 ON ((t0.week = kw.report_week)))
             JOIN t t1 ON ((t1.week = (kw.report_week - 1))))
        ), r AS (
         SELECT k.report_week,
            k.invoices_billed,
            k.transits_week,
            k.transits_prev_week,
            count(*) OVER w AS n_weeks,
            corr((k.invoices_billed)::double precision, (k.transits_week)::double precision) OVER w AS r0,
            corr((k.invoices_billed)::double precision, (k.transits_prev_week)::double precision) OVER w AS r1
           FROM k
          WINDOW w AS (ORDER BY k.report_week ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        )
 SELECT report_week,
    invoices_billed,
    (transits_week)::integer AS suez_transits_week,
    (transits_prev_week)::integer AS suez_transits_prev_week,
    (n_weeks)::integer AS n_weeks,
        CASE
            WHEN (n_weeks >= 13) THEN round((r0)::numeric, 3)
            ELSE NULL::numeric
        END AS r_lag0,
        CASE
            WHEN (n_weeks >= 13) THEN round((r1)::numeric, 3)
            ELSE NULL::numeric
        END AS r_lag1,
        CASE
            WHEN (n_weeks >= 13) THEN round((((2)::double precision / sqrt((n_weeks)::double precision)))::numeric, 3)
            ELSE NULL::numeric
        END AS r_threshold,
        CASE
            WHEN (n_weeks < 13) THEN NULL::text
            WHEN ((abs(r0) >= ((2)::double precision / sqrt((n_weeks)::double precision))) OR (abs(r1) >= ((2)::double precision / sqrt((n_weeks)::double precision)))) THEN 'link'::text
            ELSE 'no_link'::text
        END AS link,
        CASE
            WHEN (n_weeks < 13) THEN NULL::integer
            WHEN ((abs(r0) >= ((2)::double precision / sqrt((n_weeks)::double precision))) AND (abs(r0) >= COALESCE(abs(r1), (0)::double precision))) THEN 0
            WHEN (abs(r1) >= ((2)::double precision / sqrt((n_weeks)::double precision))) THEN 1
            WHEN (abs(r0) >= ((2)::double precision / sqrt((n_weeks)::double precision))) THEN 0
            ELSE NULL::integer
        END AS link_lag
   FROM r;


--
-- Name: VIEW kpi_traffic_link; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.kpi_traffic_link IS 'M17 (docs/finance_metrics.md): year-to-date Pearson r of the weekly invoice count against weekly Suez transits (IMF PortWatch), lag 0 and 1; "link" = moves with, never a cause. Live data (migration 027)';


--
-- Name: COLUMN kpi_traffic_link.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_traffic_link.report_week IS 'Report week 1-52 (ISO 2025)';


--
-- Name: COLUMN kpi_traffic_link.invoices_billed; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_traffic_link.invoices_billed IS 'Invoices issued in the week (kpi_weekly.invoices_billed of this schema)';


--
-- Name: COLUMN kpi_traffic_link.suez_transits_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_traffic_link.suez_transits_week IS 'Suez Canal transits Monday-Sunday of the week (external.suez_transits_daily, n_total)';


--
-- Name: COLUMN kpi_traffic_link.suez_transits_prev_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_traffic_link.suez_transits_prev_week IS 'Suez Canal transits of the week before (lag 1; week 0 = 2024-12-23 ... 29)';


--
-- Name: COLUMN kpi_traffic_link.n_weeks; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_traffic_link.n_weeks IS 'Weeks in the year-to-date window (= report_week)';


--
-- Name: COLUMN kpi_traffic_link.r_lag0; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_traffic_link.r_lag0 IS 'Pearson r, weeks 1..w: invoice count vs the same week''s transits (3 decimals; NULL before week 13)';


--
-- Name: COLUMN kpi_traffic_link.r_lag1; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_traffic_link.r_lag1 IS 'Pearson r, weeks 1..w: invoice count vs the previous week''s transits (3 decimals; NULL before week 13)';


--
-- Name: COLUMN kpi_traffic_link.r_threshold; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_traffic_link.r_threshold IS '2 / sqrt(n_weeks): about the 5 % two-sided level for one test; two lags double the false rate (3 decimals)';


--
-- Name: COLUMN kpi_traffic_link.link; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_traffic_link.link IS 'link when |r_lag0| or |r_lag1| >= r_threshold (unrounded), else no_link; NULL before week 13. Moves with, never caused by';


--
-- Name: COLUMN kpi_traffic_link.link_lag; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_traffic_link.link_lag IS 'The lag that passes (0 or 1; the larger |r| when both do); NULL when no_link or before week 13';


--
-- Name: kpi_weekly_breakdown; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.kpi_weekly_breakdown AS
 WITH inv AS (
         SELECT w.report_week,
            f.invoice_id,
            f.amount_sdr,
            f.scnt_tons,
            f.vessel_category,
            f.priced_condition,
            tb.band_label AS toll_band,
            v.route,
            c.segment AS customer_segment,
            c.country AS customer_country,
            c.credit_rating
           FROM ((((finance.dim_week w
             JOIN finance.fact_invoice f ON (((f.invoice_date >= w.week_start) AND (f.invoice_date <= w.week_end))))
             LEFT JOIN finance.dim_toll_band tb ON ((tb.toll_rate_band_id = f.toll_rate_band_id)))
             LEFT JOIN finance.dim_vessel v ON ((v.vessel_id = f.vessel_id)))
             LEFT JOIN finance.dim_customer c ON ((c.customer_id = f.customer_id)))
        ), long AS (
         SELECT inv.report_week,
            inv.invoice_id,
            inv.amount_sdr,
            inv.scnt_tons,
            d.dimension,
            COALESCE(d.member, '(none)'::text) AS member
           FROM (inv
             CROSS JOIN LATERAL ( VALUES ('vessel_category'::text,inv.vessel_category), ('toll_band'::text,inv.toll_band), ('route'::text,inv.route), ('priced_condition'::text,inv.priced_condition), ('customer_segment'::text,inv.customer_segment), ('customer_country'::text,inv.customer_country), ('credit_rating'::text,inv.credit_rating)) d(dimension, member))
        ), agg AS (
         SELECT long.report_week,
            long.dimension,
            long.member,
            count(long.invoice_id) AS invoices_billed,
            sum(long.amount_sdr) AS billed_sdr,
            sum(long.scnt_tons) AS scnt_tons
           FROM long
          GROUP BY long.report_week, long.dimension, long.member
        )
 SELECT report_week,
    dimension,
    member,
    invoices_billed,
    round(billed_sdr, 2) AS billed_sdr,
    scnt_tons,
    round((((100)::numeric * billed_sdr) / NULLIF(sum(billed_sdr) OVER (PARTITION BY report_week, dimension), (0)::numeric)), 2) AS share_pct,
    rank() OVER (PARTITION BY report_week, dimension ORDER BY agg.billed_sdr DESC, member) AS rank_in_week
   FROM agg;


--
-- Name: VIEW kpi_weekly_breakdown; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.kpi_weekly_breakdown IS 'M18: the week''s billing by one dimension at a time (long format); members sum to kpi_weekly per week and dimension';


--
-- Name: COLUMN kpi_weekly_breakdown.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_breakdown.report_week IS 'Report week 1-52 (ISO 2025)';


--
-- Name: COLUMN kpi_weekly_breakdown.dimension; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_breakdown.dimension IS 'vessel_category | toll_band | route | priced_condition | customer_segment | customer_country | credit_rating';


--
-- Name: COLUMN kpi_weekly_breakdown.member; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_breakdown.member IS 'The dimension''s value (toll band = the top band reached, band_label; route = origin-destination UN/LOCODE; (none) when the invoice has no value)';


--
-- Name: COLUMN kpi_weekly_breakdown.invoices_billed; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_breakdown.invoices_billed IS 'Invoices dated in the week with this member';


--
-- Name: COLUMN kpi_weekly_breakdown.billed_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_breakdown.billed_sdr IS 'Sum of their amount_sdr (2 decimals)';


--
-- Name: COLUMN kpi_weekly_breakdown.scnt_tons; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_breakdown.scnt_tons IS 'Sum of their Suez Canal net tons';


--
-- Name: COLUMN kpi_weekly_breakdown.share_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_breakdown.share_pct IS 'billed_sdr / the week''s billed_sdr over all members of this dimension, percent (2 decimals)';


--
-- Name: COLUMN kpi_weekly_breakdown.rank_in_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_breakdown.rank_in_week IS '1 = the largest billed_sdr of the week for this dimension (ties by member name)';


--
-- Name: kpi_weekly_category; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.kpi_weekly_category AS
 WITH grid AS (
         SELECT w.report_week,
            w.week_start,
            w.week_end,
            b.vessel_category,
            b.budget_sdr
           FROM (finance.dim_week w
             JOIN public.budget_weekly b ON (((b.budget_year = 2025) AND (b.iso_week = w.report_week))))
        ), base AS (
         SELECT g.report_week,
            g.vessel_category,
            g.budget_sdr,
            count(f.invoice_id) AS invoices_billed,
            COALESCE(sum(f.amount_sdr), (0)::numeric) AS billed_sdr
           FROM (grid g
             LEFT JOIN finance.fact_invoice f ON (((f.vessel_category = g.vessel_category) AND ((f.invoice_date >= g.week_start) AND (f.invoice_date <= g.week_end)))))
          GROUP BY g.report_week, g.vessel_category, g.budget_sdr
        )
 SELECT report_week,
    vessel_category,
    invoices_billed,
    round(billed_sdr, 2) AS billed_sdr,
    round(budget_sdr, 2) AS budget_sdr,
    round((billed_sdr - budget_sdr), 2) AS budget_variance_sdr,
    round((((100)::numeric * (billed_sdr - budget_sdr)) / NULLIF(budget_sdr, (0)::numeric)), 2) AS budget_variance_pct,
    round(lag(billed_sdr) OVER cw, 2) AS billed_prev_sdr,
    round((billed_sdr - lag(billed_sdr) OVER cw), 2) AS billed_wow_change_sdr,
    round((((100)::numeric * (billed_sdr - lag(billed_sdr) OVER cw)) / NULLIF(lag(billed_sdr) OVER cw, (0)::numeric)), 2) AS billed_wow_pct,
    lag(invoices_billed) OVER cw AS invoices_prev
   FROM base
  WINDOW cw AS (PARTITION BY vessel_category ORDER BY report_week);


--
-- Name: VIEW kpi_weekly_category; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.kpi_weekly_category IS 'Billing vs budget per report week and vessel category (52 × 13 rows); the week''s drivers = largest |billed_wow_change_sdr|. Level 2, Finance.';


--
-- Name: COLUMN kpi_weekly_category.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_category.report_week IS 'Report week';


--
-- Name: COLUMN kpi_weekly_category.vessel_category; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_category.vessel_category IS 'Vessel category (13 tariff categories)';


--
-- Name: COLUMN kpi_weekly_category.invoices_billed; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_category.invoices_billed IS 'Invoices of the category dated in the week';


--
-- Name: COLUMN kpi_weekly_category.billed_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_category.billed_sdr IS 'Billed revenue of the category in the week (SDR)';


--
-- Name: COLUMN kpi_weekly_category.budget_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_category.budget_sdr IS 'Budget of the category for the week (SDR)';


--
-- Name: COLUMN kpi_weekly_category.budget_variance_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_category.budget_variance_sdr IS 'billed_sdr − budget_sdr (SDR)';


--
-- Name: COLUMN kpi_weekly_category.budget_variance_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_category.budget_variance_pct IS '(billed − budget) ÷ budget, percent';


--
-- Name: COLUMN kpi_weekly_category.billed_prev_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_category.billed_prev_sdr IS 'Billed revenue of the category in the previous week (SDR); NULL in week 1';


--
-- Name: COLUMN kpi_weekly_category.billed_wow_change_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_category.billed_wow_change_sdr IS 'billed_sdr − billed_prev_sdr (SDR)';


--
-- Name: COLUMN kpi_weekly_category.billed_wow_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_category.billed_wow_pct IS 'Change vs the previous week, percent; NULL when the previous week was 0';


--
-- Name: COLUMN kpi_weekly_category.invoices_prev; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_category.invoices_prev IS 'Invoices billed in the category in the previous report week; NULL in week 1 (shows how many invoices sit behind a WoW driver).';


--
-- Name: kpi_weekly_trend; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.kpi_weekly_trend AS
 SELECT s.report_week,
    t.report_week AS trend_week,
    (t.report_week - s.report_week) AS week_offset,
    (t.report_week = s.report_week) AS is_report_week,
    t.iso_week_label AS trend_week_label,
    t.week_end AS trend_week_end,
    t.is_warmup,
    t.invoices_billed,
    t.billed_sdr,
    t.collected_sdr,
    t.ar_sdr,
    t.overdue_sdr,
    t.dso_days,
    t.budget_sdr,
    t.budget_variance_sdr,
    t.budget_variance_pct,
    t.top10_share_13w_pct
   FROM (finance.dim_week s
     JOIN finance.kpi_weekly t ON (((t.report_week >= (s.report_week - 12)) AND (t.report_week <= s.report_week))));


--
-- Name: VIEW kpi_weekly_trend; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.kpi_weekly_trend IS 'The 13-week trend of each report week (M11): one row per (report_week, trend_week) for the weeks w−12 … w (fewer in weeks 1–12), values from kpi_weekly. Filter report_week, chart over trend_week. Level 2, Finance.';


--
-- Name: COLUMN kpi_weekly_trend.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.report_week IS 'The report week the trend belongs to (filter on this)';


--
-- Name: COLUMN kpi_weekly_trend.trend_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.trend_week IS 'A week inside the trend window (chart axis)';


--
-- Name: COLUMN kpi_weekly_trend.week_offset; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.week_offset IS 'trend_week − report_week: −12 … 0';


--
-- Name: COLUMN kpi_weekly_trend.is_report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.is_report_week IS 'True on the report week itself (offset 0)';


--
-- Name: COLUMN kpi_weekly_trend.trend_week_label; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.trend_week_label IS 'ISO label of the trend week, e.g. 2025-W23';


--
-- Name: COLUMN kpi_weekly_trend.trend_week_end; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.trend_week_end IS 'Sunday of the trend week';


--
-- Name: COLUMN kpi_weekly_trend.is_warmup; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.is_warmup IS 'The trend week is a warm-up week (1–13)';


--
-- Name: COLUMN kpi_weekly_trend.invoices_billed; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.invoices_billed IS 'kpi_weekly.invoices_billed of the trend week';


--
-- Name: COLUMN kpi_weekly_trend.billed_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.billed_sdr IS 'kpi_weekly.billed_sdr of the trend week (SDR)';


--
-- Name: COLUMN kpi_weekly_trend.collected_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.collected_sdr IS 'kpi_weekly.collected_sdr of the trend week (SDR)';


--
-- Name: COLUMN kpi_weekly_trend.ar_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.ar_sdr IS 'kpi_weekly.ar_sdr of the trend week (SDR)';


--
-- Name: COLUMN kpi_weekly_trend.overdue_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.overdue_sdr IS 'kpi_weekly.overdue_sdr of the trend week (SDR)';


--
-- Name: COLUMN kpi_weekly_trend.dso_days; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.dso_days IS 'kpi_weekly.dso_days of the trend week';


--
-- Name: COLUMN kpi_weekly_trend.budget_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.budget_sdr IS 'kpi_weekly.budget_sdr of the trend week (SDR)';


--
-- Name: COLUMN kpi_weekly_trend.budget_variance_sdr; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.budget_variance_sdr IS 'kpi_weekly.budget_variance_sdr of the trend week (SDR)';


--
-- Name: COLUMN kpi_weekly_trend.budget_variance_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.budget_variance_pct IS 'kpi_weekly.budget_variance_pct of the trend week (percent)';


--
-- Name: COLUMN kpi_weekly_trend.top10_share_13w_pct; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.kpi_weekly_trend.top10_share_13w_pct IS 'kpi_weekly.top10_share_13w_pct of the trend week (percent)';


--
-- Name: pack_approved_summary; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.pack_approved_summary AS
 SELECT s.report_week,
    w.iso_week_label,
    (s.idx + 1) AS line_no,
    s.text,
    p.approved_at,
    p.approver_employee_id,
    p.degraded
   FROM ((agent_state.pack_approved_summary s
     JOIN agent_state.pack_approved p USING (report_week))
     JOIN finance.dim_week w USING (report_week));


--
-- Name: VIEW pack_approved_summary; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.pack_approved_summary IS 'The approved weekly pack''s executive summary (slide 2), one row per line, for the Power BI "Approved pack" page (migration 024).';


--
-- Name: COLUMN pack_approved_summary.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_approved_summary.report_week IS 'Report week 1-52 (ISO 2025) of the approved pack';


--
-- Name: COLUMN pack_approved_summary.iso_week_label; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_approved_summary.iso_week_label IS 'The report week as an ISO label (finance.dim_week), e.g. 2025-W14';


--
-- Name: COLUMN pack_approved_summary.line_no; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_approved_summary.line_no IS 'Position of the summary line on slide 2 (1 = first)';


--
-- Name: COLUMN pack_approved_summary.text; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_approved_summary.text IS 'The approved summary line, numbers already rendered from their slots';


--
-- Name: COLUMN pack_approved_summary.approved_at; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_approved_summary.approved_at IS 'When the finance manager approved the pack (agent_state.pack_approved)';


--
-- Name: COLUMN pack_approved_summary.approver_employee_id; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_approved_summary.approver_employee_id IS 'employees.employee_id of the approver';


--
-- Name: COLUMN pack_approved_summary.degraded; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_approved_summary.degraded IS 'true = code replaced or dropped some of the Writer''s texts (c4 fallback); read the deck before quoting it';


--
-- Name: pack_trend_long; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.pack_trend_long AS
 SELECT p.report_week,
    t.report_week AS trend_week,
    t.iso_week_label AS trend_week_label,
    (t.report_week = p.report_week) AS is_report_week,
    s.ord AS series_order,
    s.series,
        CASE s.series
            WHEN 'billed_sdr'::text THEN 'Billed'::text
            WHEN 'budget_sdr'::text THEN 'Budget'::text
            WHEN 'collected_sdr'::text THEN 'Collected'::text
            WHEN 'ar_sdr'::text THEN 'Receivables'::text
            WHEN 'overdue_sdr'::text THEN 'Overdue'::text
            WHEN 'dso_days'::text THEN 'DSO'::text
            ELSE NULL::text
        END AS series_name,
        CASE
            WHEN (s.series = 'dso_days'::text) THEN 'days'::text
            ELSE 'SDR'::text
        END AS unit,
        CASE s.series
            WHEN 'billed_sdr'::text THEN t.billed_sdr
            WHEN 'budget_sdr'::text THEN t.budget_sdr
            WHEN 'collected_sdr'::text THEN t.collected_sdr
            WHEN 'ar_sdr'::text THEN t.ar_sdr
            WHEN 'overdue_sdr'::text THEN t.overdue_sdr
            WHEN 'dso_days'::text THEN t.dso_days
            ELSE NULL::numeric
        END AS value
   FROM ((agent_state.pack_approved p
     CROSS JOIN LATERAL unnest(p.trend_series) WITH ORDINALITY s(series, ord))
     JOIN finance.kpi_weekly t ON (((t.report_week >= GREATEST(1, ((p.report_week - p.trend_weeks) + 1))) AND (t.report_week <= p.report_week))));


--
-- Name: VIEW pack_trend_long; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.pack_trend_long IS 'The approved pack''s trend chart (slide 4) as long rows: the weeks of the approved window × the approved series, each value a finance.kpi_weekly column (migration 024; the deck''s render.trend_window).';


--
-- Name: COLUMN pack_trend_long.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_trend_long.report_week IS 'Report week 1-52 (ISO 2025) of the approved pack';


--
-- Name: COLUMN pack_trend_long.trend_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_trend_long.trend_week IS 'A week of the approved trend window (finance.kpi_weekly.report_week)';


--
-- Name: COLUMN pack_trend_long.trend_week_label; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_trend_long.trend_week_label IS 'The trend week as an ISO label (finance.dim_week)';


--
-- Name: COLUMN pack_trend_long.is_report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_trend_long.is_report_week IS 'true for the pack''s own report week (highlighted on the chart)';


--
-- Name: COLUMN pack_trend_long.series_order; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_trend_long.series_order IS 'Order of the series as approved (1 = first in the legend)';


--
-- Name: COLUMN pack_trend_long.series; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_trend_long.series IS 'The finance.kpi_weekly column the series shows (e.g. billed_sdr)';


--
-- Name: COLUMN pack_trend_long.series_name; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_trend_long.series_name IS 'Display name of the series';


--
-- Name: COLUMN pack_trend_long.unit; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_trend_long.unit IS 'Unit of value: SDR, or days for dso_days';


--
-- Name: COLUMN pack_trend_long.value; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_trend_long.value IS 'The series value in trend_week, read from finance.kpi_weekly';


--
-- Name: pack_variance_long; Type: VIEW; Schema: finance; Owner: -
--

CREATE VIEW finance.pack_variance_long AS
 WITH v AS (
         SELECT p.report_week,
            p.variance_measure AS measure,
            p.variance_rows,
            c.vessel_category,
                CASE p.variance_measure
                    WHEN 'budget_variance_sdr'::text THEN c.budget_variance_sdr
                    WHEN 'budget_variance_pct'::text THEN c.budget_variance_pct
                    WHEN 'billed_wow_change_sdr'::text THEN c.billed_wow_change_sdr
                    ELSE NULL::numeric
                END AS value
           FROM (agent_state.pack_approved p
             JOIN finance.kpi_weekly_category c USING (report_week))
        ), r AS (
         SELECT v.report_week,
            v.measure,
            v.variance_rows,
            v.vessel_category,
            v.value,
            row_number() OVER (PARTITION BY v.report_week ORDER BY COALESCE(v.value, (0)::numeric), v.vessel_category) AS sort_order,
            count(*) OVER (PARTITION BY v.report_week) AS n
           FROM v
        )
 SELECT report_week,
    measure,
        CASE measure
            WHEN 'budget_variance_sdr'::text THEN 'Billed − budget'::text
            WHEN 'budget_variance_pct'::text THEN 'Billed vs budget %'::text
            WHEN 'billed_wow_change_sdr'::text THEN 'Change on last week'::text
            ELSE NULL::text
        END AS measure_name,
        CASE
            WHEN (measure = 'budget_variance_pct'::text) THEN '%'::text
            ELSE 'SDR'::text
        END AS unit,
    vessel_category,
    value,
    sort_order
   FROM r
  WHERE ((variance_rows = 'all'::text) OR ((variance_rows = 'top5'::text) AND (sort_order > (n - 5))) OR ((variance_rows = 'bottom5'::text) AND (sort_order <= 5)));


--
-- Name: VIEW pack_variance_long; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON VIEW finance.pack_variance_long IS 'The approved pack''s variance chart (slide 5) as rows: the categories of the report week by the approved measure, ascending (sort_order), all / top 5 / bottom 5 as approved; each value a finance.kpi_weekly_category column (migration 024; the deck''s render.variance_rows).';


--
-- Name: COLUMN pack_variance_long.report_week; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_variance_long.report_week IS 'Report week 1-52 (ISO 2025) of the approved pack';


--
-- Name: COLUMN pack_variance_long.measure; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_variance_long.measure IS 'The finance.kpi_weekly_category column the chart shows, as approved (e.g. budget_variance_pct)';


--
-- Name: COLUMN pack_variance_long.measure_name; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_variance_long.measure_name IS 'Display name of the measure';


--
-- Name: COLUMN pack_variance_long.unit; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_variance_long.unit IS 'Unit of value: % for budget_variance_pct, else SDR';


--
-- Name: COLUMN pack_variance_long.vessel_category; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_variance_long.vessel_category IS 'Vessel category (toll category) of the row';


--
-- Name: COLUMN pack_variance_long.value; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_variance_long.value IS 'The measure for this category in the report week, read from finance.kpi_weekly_category';


--
-- Name: COLUMN pack_variance_long.sort_order; Type: COMMENT; Schema: finance; Owner: -
--

COMMENT ON COLUMN finance.pack_variance_long.sort_order IS 'Ascending rank by value (then category) within the report week; the chart draws in this order';


--
-- Name: invoices; Type: TABLE; Schema: finance_scenario; Owner: -
--

CREATE TABLE finance_scenario.invoices (
    invoice_id integer NOT NULL,
    invoice_number text NOT NULL,
    vessel_id integer NOT NULL,
    toll_rate_band_id integer,
    invoice_date date NOT NULL,
    scnt_tons numeric,
    rate_sdr_per_ton numeric,
    amount numeric NOT NULL,
    description text,
    status text,
    original_invoice_date date NOT NULL
);


--
-- Name: TABLE invoices; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON TABLE finance_scenario.invoices IS 'Scenario (planted: α = 1.6 × the real 2025 Suez traffic swing) — not NileGate''s billing: public.invoices with invoice_date re-dated';


--
-- Name: COLUMN invoices.invoice_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.invoices.invoice_id IS 'As in public.invoices';


--
-- Name: COLUMN invoices.invoice_number; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.invoices.invoice_number IS 'As in public.invoices';


--
-- Name: COLUMN invoices.vessel_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.invoices.vessel_id IS 'As in public.invoices';


--
-- Name: COLUMN invoices.toll_rate_band_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.invoices.toll_rate_band_id IS 'As in public.invoices';


--
-- Name: COLUMN invoices.invoice_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.invoices.invoice_date IS 'Scenario date: the re-dated invoice day';


--
-- Name: COLUMN invoices.scnt_tons; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.invoices.scnt_tons IS 'As in public.invoices';


--
-- Name: COLUMN invoices.rate_sdr_per_ton; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.invoices.rate_sdr_per_ton IS 'As in public.invoices';


--
-- Name: COLUMN invoices.amount; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.invoices.amount IS 'As in public.invoices (SDR)';


--
-- Name: COLUMN invoices.description; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.invoices.description IS 'As in public.invoices';


--
-- Name: COLUMN invoices.status; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.invoices.status IS 'As in public.invoices (a random label, never used)';


--
-- Name: COLUMN invoices.original_invoice_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.invoices.original_invoice_date IS 'The live invoice_date in public.invoices';


--
-- Name: payments; Type: TABLE; Schema: finance_scenario; Owner: -
--

CREATE TABLE finance_scenario.payments (
    invoice_number text NOT NULL,
    paid_date date NOT NULL,
    amount_sdr numeric NOT NULL,
    original_paid_date date NOT NULL
);


--
-- Name: TABLE payments; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON TABLE finance_scenario.payments IS 'Scenario (planted: α = 1.6 × the real 2025 Suez traffic swing) — not NileGate''s billing: public.payments with paid_date moved by its invoice, the delay kept';


--
-- Name: COLUMN payments.invoice_number; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.payments.invoice_number IS 'As in public.payments';


--
-- Name: COLUMN payments.paid_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.payments.paid_date IS 'Scenario date: the new invoice date + the live delay';


--
-- Name: COLUMN payments.amount_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.payments.amount_sdr IS 'As in public.payments (SDR)';


--
-- Name: COLUMN payments.original_paid_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.payments.original_paid_date IS 'The live paid_date in public.payments';


--
-- Name: fact_invoice; Type: VIEW; Schema: finance_scenario; Owner: -
--

CREATE VIEW finance_scenario.fact_invoice AS
 SELECT i.invoice_id,
    i.invoice_number,
    i.invoice_date,
        CASE
            WHEN (EXTRACT(isoyear FROM i.invoice_date) = (2025)::numeric) THEN (EXTRACT(week FROM i.invoice_date))::integer
            ELSE NULL::integer
        END AS invoice_report_week,
    v.customer_id,
    i.vessel_id,
    v.vessel_type AS vessel_category,
    b.laden_ballast AS priced_condition,
    i.toll_rate_band_id,
    i.scnt_tons,
    i.rate_sdr_per_ton,
    i.amount AS amount_sdr,
    c.payment_terms_days,
    (i.invoice_date + c.payment_terms_days) AS due_date,
    p.paid_date,
    (p.paid_date - i.invoice_date) AS days_to_pay,
    (p.paid_date - (i.invoice_date + c.payment_terms_days)) AS days_paid_after_due
   FROM ((((finance_scenario.invoices i
     JOIN public.vessels v ON ((v.vessel_id = i.vessel_id)))
     JOIN public.customers c ON ((c.customer_id = v.customer_id)))
     LEFT JOIN public.toll_rate_bands b ON ((b.id = i.toll_rate_band_id)))
     LEFT JOIN finance_scenario.payments p ON ((p.invoice_number = i.invoice_number)));


--
-- Name: VIEW fact_invoice; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON VIEW finance_scenario.fact_invoice IS 'Scenario (planted: α = 1.6 × the real 2025 Suez traffic swing) — not NileGate''s billing. Twin of finance.fact_invoice: One row per invoice with the derived due date and its payment (ADR-046: invoices.status is a label and is not used). Level 2, Finance.';


--
-- Name: COLUMN fact_invoice.invoice_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.invoice_id IS 'Invoice id';


--
-- Name: COLUMN fact_invoice.invoice_number; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.invoice_number IS 'Invoice number INV-nnnnnnn';


--
-- Name: COLUMN fact_invoice.invoice_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.invoice_date IS 'Invoice (billing) date: revenue is counted in its week';


--
-- Name: COLUMN fact_invoice.invoice_report_week; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.invoice_report_week IS 'Report week of the invoice date; NULL for 2025-12-29..31 (ISO 2026-W01)';


--
-- Name: COLUMN fact_invoice.customer_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.customer_id IS 'Billed customer (through the vessel)';


--
-- Name: COLUMN fact_invoice.vessel_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.vessel_id IS 'Vessel id';


--
-- Name: COLUMN fact_invoice.vessel_category; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.vessel_category IS 'Vessel category (13 tariff categories)';


--
-- Name: COLUMN fact_invoice.priced_condition; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.priced_condition IS 'Laden or Ballast as priced (from the terminal band; Special Floating Units always Laden)';


--
-- Name: COLUMN fact_invoice.toll_rate_band_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.toll_rate_band_id IS 'Terminal band containing the vessel SCNT';


--
-- Name: COLUMN fact_invoice.scnt_tons; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.scnt_tons IS 'Billed Suez Canal Net Tonnage';


--
-- Name: COLUMN fact_invoice.rate_sdr_per_ton; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.rate_sdr_per_ton IS 'Rate of the terminal band (SDR per SCNT)';


--
-- Name: COLUMN fact_invoice.amount_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.amount_sdr IS 'Invoice amount in SDR (progressive toll, ADR-003 / ADR-004)';


--
-- Name: COLUMN fact_invoice.payment_terms_days; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.payment_terms_days IS 'Customer payment terms in days';


--
-- Name: COLUMN fact_invoice.due_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.due_date IS 'Derived due date = invoice_date + payment_terms_days (not stored, ADR-046)';


--
-- Name: COLUMN fact_invoice.paid_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.paid_date IS 'Date of the single full payment; NULL = unpaid at the 2026-03-31 horizon';


--
-- Name: COLUMN fact_invoice.days_to_pay; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.days_to_pay IS 'paid_date − invoice_date in days; NULL if unpaid';


--
-- Name: COLUMN fact_invoice.days_paid_after_due; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_invoice.days_paid_after_due IS 'paid_date − due_date in days (negative = paid early); NULL if unpaid';


--
-- Name: fact_ar_snapshot; Type: VIEW; Schema: finance_scenario; Owner: -
--

CREATE VIEW finance_scenario.fact_ar_snapshot AS
 SELECT w.report_week,
    w.week_end AS as_of_date,
    f.invoice_number,
    f.invoice_date,
    f.due_date,
    f.customer_id,
    f.vessel_id,
    f.vessel_category,
    f.amount_sdr,
    (w.week_end - f.due_date) AS days_past_due,
    ((w.week_end - f.due_date) > 0) AS is_overdue,
        CASE
            WHEN ((w.week_end - f.due_date) <= 0) THEN 'current'::text
            WHEN ((w.week_end - f.due_date) <= 30) THEN '1-30'::text
            WHEN ((w.week_end - f.due_date) <= 60) THEN '31-60'::text
            WHEN ((w.week_end - f.due_date) <= 90) THEN '61-90'::text
            ELSE '90+'::text
        END AS aging_bucket,
        CASE
            WHEN ((w.week_end - f.due_date) <= 0) THEN 1
            WHEN ((w.week_end - f.due_date) <= 30) THEN 2
            WHEN ((w.week_end - f.due_date) <= 60) THEN 3
            WHEN ((w.week_end - f.due_date) <= 90) THEN 4
            ELSE 5
        END AS aging_bucket_order
   FROM (finance.dim_week w
     JOIN finance_scenario.fact_invoice f ON (((f.invoice_date <= w.week_end) AND ((f.paid_date IS NULL) OR (f.paid_date > w.week_end)))));


--
-- Name: VIEW fact_ar_snapshot; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON VIEW finance_scenario.fact_ar_snapshot IS 'Scenario (planted: α = 1.6 × the real 2025 Suez traffic swing) — not NileGate''s billing. Twin of finance.fact_ar_snapshot: Receivables as of each report week: one row per invoice issued on or before the week''s Sunday and not paid by then, with its age past due. Level 2, Finance.';


--
-- Name: COLUMN fact_ar_snapshot.report_week; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_ar_snapshot.report_week IS 'Report week';


--
-- Name: COLUMN fact_ar_snapshot.as_of_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_ar_snapshot.as_of_date IS 'Sunday of the report week (as of 23:59)';


--
-- Name: COLUMN fact_ar_snapshot.invoice_number; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_ar_snapshot.invoice_number IS 'Open invoice';


--
-- Name: COLUMN fact_ar_snapshot.invoice_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_ar_snapshot.invoice_date IS 'Invoice date';


--
-- Name: COLUMN fact_ar_snapshot.due_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_ar_snapshot.due_date IS 'Derived due date';


--
-- Name: COLUMN fact_ar_snapshot.customer_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_ar_snapshot.customer_id IS 'Billed customer';


--
-- Name: COLUMN fact_ar_snapshot.vessel_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_ar_snapshot.vessel_id IS 'Vessel id';


--
-- Name: COLUMN fact_ar_snapshot.vessel_category; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_ar_snapshot.vessel_category IS 'Vessel category';


--
-- Name: COLUMN fact_ar_snapshot.amount_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_ar_snapshot.amount_sdr IS 'Open amount in SDR (no partial payments: the full invoice amount)';


--
-- Name: COLUMN fact_ar_snapshot.days_past_due; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_ar_snapshot.days_past_due IS 'as_of_date − due_date in days (≤ 0 = not yet due)';


--
-- Name: COLUMN fact_ar_snapshot.is_overdue; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_ar_snapshot.is_overdue IS 'True when days_past_due ≥ 1';


--
-- Name: COLUMN fact_ar_snapshot.aging_bucket; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_ar_snapshot.aging_bucket IS 'current (≤ 0), 1-30, 31-60, 61-90 or 90+ days past due';


--
-- Name: COLUMN fact_ar_snapshot.aging_bucket_order; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_ar_snapshot.aging_bucket_order IS 'Sort order of aging_bucket, 1 = current … 5 = 90+';


--
-- Name: fact_payment; Type: VIEW; Schema: finance_scenario; Owner: -
--

CREATE VIEW finance_scenario.fact_payment AS
 SELECT p.invoice_number,
    p.paid_date,
        CASE
            WHEN (EXTRACT(isoyear FROM p.paid_date) = (2025)::numeric) THEN (EXTRACT(week FROM p.paid_date))::integer
            ELSE NULL::integer
        END AS paid_report_week,
    p.amount_sdr,
    f.invoice_date,
    f.due_date,
    f.customer_id,
    f.vessel_id,
    f.vessel_category,
    f.days_to_pay,
    f.days_paid_after_due
   FROM (finance_scenario.payments p
     JOIN finance_scenario.fact_invoice f ON ((f.invoice_number = p.invoice_number)));


--
-- Name: VIEW fact_payment; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON VIEW finance_scenario.fact_payment IS 'Scenario (planted: α = 1.6 × the real 2025 Suez traffic swing) — not NileGate''s billing. Twin of finance.fact_payment: One row per payment (one full payment per paid invoice): collections are counted in the week of paid_date. Level 2, Finance.';


--
-- Name: COLUMN fact_payment.invoice_number; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_payment.invoice_number IS 'Paid invoice';


--
-- Name: COLUMN fact_payment.paid_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_payment.paid_date IS 'Payment date';


--
-- Name: COLUMN fact_payment.paid_report_week; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_payment.paid_report_week IS 'Report week of the payment; NULL for payments in ISO 2026';


--
-- Name: COLUMN fact_payment.amount_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_payment.amount_sdr IS 'Amount received in SDR (= the invoice amount)';


--
-- Name: COLUMN fact_payment.invoice_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_payment.invoice_date IS 'Invoice date of the paid invoice';


--
-- Name: COLUMN fact_payment.due_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_payment.due_date IS 'Derived due date of the paid invoice';


--
-- Name: COLUMN fact_payment.customer_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_payment.customer_id IS 'Paying customer';


--
-- Name: COLUMN fact_payment.vessel_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_payment.vessel_id IS 'Vessel of the paid invoice';


--
-- Name: COLUMN fact_payment.vessel_category; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_payment.vessel_category IS 'Vessel category of the paid invoice';


--
-- Name: COLUMN fact_payment.days_to_pay; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_payment.days_to_pay IS 'paid_date − invoice_date in days';


--
-- Name: COLUMN fact_payment.days_paid_after_due; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.fact_payment.days_paid_after_due IS 'paid_date − due_date in days (negative = paid early)';


--
-- Name: kpi_customer_13w; Type: VIEW; Schema: finance_scenario; Owner: -
--

CREATE VIEW finance_scenario.kpi_customer_13w AS
 WITH grid AS (
         SELECT w.report_week,
            w.week_start,
            w.week_end,
            c.customer_id
           FROM (finance.dim_week w
             CROSS JOIN public.customers c)
        ), billing AS (
         SELECT g.report_week,
            g.customer_id,
            COALESCE(sum(f.amount_sdr) FILTER (WHERE (f.invoice_date >= g.week_start)), (0)::numeric) AS billed_week_sdr,
            COALESCE(sum(f.amount_sdr), (0)::numeric) AS billed_13w_sdr
           FROM (grid g
             LEFT JOIN finance_scenario.fact_invoice f ON (((f.customer_id = g.customer_id) AND (f.invoice_date >= (g.week_end - 90)) AND (f.invoice_date <= g.week_end))))
          GROUP BY g.report_week, g.customer_id
        ), open_ar AS (
         SELECT fact_ar_snapshot.report_week,
            fact_ar_snapshot.customer_id,
            sum(fact_ar_snapshot.amount_sdr) AS ar_sdr,
            sum(fact_ar_snapshot.amount_sdr) FILTER (WHERE fact_ar_snapshot.is_overdue) AS overdue_sdr
           FROM finance_scenario.fact_ar_snapshot
          GROUP BY fact_ar_snapshot.report_week, fact_ar_snapshot.customer_id
        ), ranked AS (
         SELECT b.report_week,
            b.customer_id,
            b.billed_week_sdr,
            b.billed_13w_sdr,
            sum(b.billed_13w_sdr) OVER (PARTITION BY b.report_week) AS total_13w_sdr,
            row_number() OVER (PARTITION BY b.report_week ORDER BY b.billed_13w_sdr DESC, b.customer_id) AS rank_13w
           FROM billing b
        ), prev AS (
         SELECT r.report_week,
            r.customer_id,
            c.customer_name,
            c.segment,
            c.country,
            c.credit_rating,
            c.payment_terms_days,
            round(r.billed_week_sdr, 2) AS billed_week_sdr,
            round(r.billed_13w_sdr, 2) AS billed_13w_sdr,
            round((((100)::numeric * r.billed_13w_sdr) / NULLIF(r.total_13w_sdr, (0)::numeric)), 2) AS share_13w_pct,
            r.rank_13w,
            lag(r.rank_13w) OVER (PARTITION BY r.customer_id ORDER BY r.report_week) AS rank_13w_prev,
            ((r.rank_13w <= 10) AND (r.billed_13w_sdr > (0)::numeric)) AS is_top10,
            round(COALESCE(o.ar_sdr, (0)::numeric), 2) AS ar_sdr,
            round(COALESCE(o.overdue_sdr, (0)::numeric), 2) AS overdue_sdr
           FROM ((ranked r
             JOIN public.customers c ON ((c.customer_id = r.customer_id)))
             LEFT JOIN open_ar o ON (((o.report_week = r.report_week) AND (o.customer_id = r.customer_id))))
        ), punctuality AS (
         SELECT g.report_week,
            g.customer_id,
            ((100.0 * (count(p_1.invoice_number) FILTER (WHERE (p_1.days_paid_after_due <= 0)))::numeric) / (NULLIF(count(p_1.invoice_number), 0))::numeric) AS ontime_13w
           FROM (grid g
             LEFT JOIN finance_scenario.fact_payment p_1 ON (((p_1.customer_id = g.customer_id) AND (p_1.paid_date >= (g.week_end - 90)) AND (p_1.paid_date <= g.week_end))))
          GROUP BY g.report_week, g.customer_id
        )
 SELECT p.report_week,
    p.customer_id,
    p.customer_name,
    p.segment,
    p.country,
    p.credit_rating,
    p.payment_terms_days,
    p.billed_week_sdr,
    p.billed_13w_sdr,
    p.share_13w_pct,
    p.rank_13w,
    p.rank_13w_prev,
    p.is_top10,
    p.ar_sdr,
    p.overdue_sdr,
    round((((100)::numeric * p.ar_sdr) / NULLIF(p.billed_13w_sdr, (0)::numeric)), 2) AS ar_to_billed_13w_pct,
        CASE
            WHEN (p.report_week <= 13) THEN NULL::boolean
            ELSE ((p.ar_sdr >= (1000000)::numeric) AND ((p.billed_13w_sdr = (0)::numeric) OR (p.ar_sdr >= (0.8 * p.billed_13w_sdr))))
        END AS is_watchlist,
    round(pu.ontime_13w, 2) AS ontime_13w_pct
   FROM (prev p
     JOIN punctuality pu ON (((pu.report_week = p.report_week) AND (pu.customer_id = p.customer_id))));


--
-- Name: VIEW kpi_customer_13w; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON VIEW finance_scenario.kpi_customer_13w IS 'Scenario (planted: α = 1.6 × the real 2025 Suez traffic swing) — not NileGate''s billing. Twin of finance.kpi_customer_13w: Every customer in every report week: billing of the week and of the trailing 13 weeks (91 days ending Sunday), share, rank, receivables. Level 2, Finance.';


--
-- Name: COLUMN kpi_customer_13w.report_week; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.report_week IS 'Report week';


--
-- Name: COLUMN kpi_customer_13w.customer_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.customer_id IS 'Customer id';


--
-- Name: COLUMN kpi_customer_13w.customer_name; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.customer_name IS 'Customer name';


--
-- Name: COLUMN kpi_customer_13w.segment; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.segment IS 'Customer segment';


--
-- Name: COLUMN kpi_customer_13w.country; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.country IS 'Head-office country';


--
-- Name: COLUMN kpi_customer_13w.credit_rating; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.credit_rating IS 'Credit rating A, B or C';


--
-- Name: COLUMN kpi_customer_13w.payment_terms_days; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.payment_terms_days IS 'Payment terms in days';


--
-- Name: COLUMN kpi_customer_13w.billed_week_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.billed_week_sdr IS 'Billed in the report week (SDR, 2 decimals)';


--
-- Name: COLUMN kpi_customer_13w.billed_13w_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.billed_13w_sdr IS 'Billed in the trailing 13 weeks = 91 days ending the week''s Sunday (SDR, 2 decimals)';


--
-- Name: COLUMN kpi_customer_13w.share_13w_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.share_13w_pct IS 'Share of all billing in the trailing 13 weeks, percent (2 decimals)';


--
-- Name: COLUMN kpi_customer_13w.rank_13w; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.rank_13w IS 'Rank by billed_13w_sdr (1 = largest; ties by customer_id)';


--
-- Name: COLUMN kpi_customer_13w.rank_13w_prev; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.rank_13w_prev IS 'rank_13w in the previous report week; NULL in week 1';


--
-- Name: COLUMN kpi_customer_13w.is_top10; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.is_top10 IS 'True for ranks 1–10 with billing > 0 in the trailing 13 weeks';


--
-- Name: COLUMN kpi_customer_13w.ar_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.ar_sdr IS 'Open receivables of the customer as of the week''s Sunday (SDR)';


--
-- Name: COLUMN kpi_customer_13w.overdue_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.overdue_sdr IS 'Overdue part of ar_sdr (SDR)';


--
-- Name: COLUMN kpi_customer_13w.ar_to_billed_13w_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.ar_to_billed_13w_pct IS 'Customer AR ÷ its own 13-week billing × 100; NULL when it billed nothing in 13 weeks (M15).';


--
-- Name: COLUMN kpi_customer_13w.is_watchlist; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.is_watchlist IS 'AR ≥ 1,000,000 SDR and (no 13-week billing or AR ≥ 80 % of it); NULL in warm-up weeks 1–13 (M15, W-R1 / W-R7).';


--
-- Name: COLUMN kpi_customer_13w.ontime_13w_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_customer_13w.ontime_13w_pct IS 'Share of the customer''s payments in the 91 days ending Sunday paid on or before due, percent; NULL without payments (M16).';


--
-- Name: kpi_overdue_list; Type: VIEW; Schema: finance_scenario; Owner: -
--

CREATE VIEW finance_scenario.kpi_overdue_list AS
 SELECT a.report_week,
    a.as_of_date,
    a.invoice_number,
    a.customer_id,
    c.customer_name,
    a.vessel_id,
    v.vessel_name,
    a.vessel_category,
    a.invoice_date,
    a.due_date,
    a.amount_sdr,
    a.days_past_due,
    a.aging_bucket,
    row_number() OVER (PARTITION BY a.report_week ORDER BY a.amount_sdr DESC, a.invoice_number) AS rank_by_amount
   FROM ((finance_scenario.fact_ar_snapshot a
     JOIN public.customers c ON ((c.customer_id = a.customer_id)))
     JOIN public.vessels v ON ((v.vessel_id = a.vessel_id)))
  WHERE a.is_overdue;


--
-- Name: VIEW kpi_overdue_list; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON VIEW finance_scenario.kpi_overdue_list IS 'Scenario (planted: α = 1.6 × the real 2025 Suez traffic swing) — not NileGate''s billing. Twin of finance.kpi_overdue_list: Overdue invoices (≥ 1 day past due) as of each report week, ranked by amount. Level 2, Finance.';


--
-- Name: COLUMN kpi_overdue_list.report_week; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.report_week IS 'Report week';


--
-- Name: COLUMN kpi_overdue_list.as_of_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.as_of_date IS 'Sunday of the report week';


--
-- Name: COLUMN kpi_overdue_list.invoice_number; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.invoice_number IS 'Overdue invoice';


--
-- Name: COLUMN kpi_overdue_list.customer_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.customer_id IS 'Customer id';


--
-- Name: COLUMN kpi_overdue_list.customer_name; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.customer_name IS 'Customer name';


--
-- Name: COLUMN kpi_overdue_list.vessel_id; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.vessel_id IS 'Vessel id';


--
-- Name: COLUMN kpi_overdue_list.vessel_name; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.vessel_name IS 'Vessel name';


--
-- Name: COLUMN kpi_overdue_list.vessel_category; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.vessel_category IS 'Vessel category';


--
-- Name: COLUMN kpi_overdue_list.invoice_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.invoice_date IS 'Invoice date';


--
-- Name: COLUMN kpi_overdue_list.due_date; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.due_date IS 'Derived due date';


--
-- Name: COLUMN kpi_overdue_list.amount_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.amount_sdr IS 'Open amount (SDR)';


--
-- Name: COLUMN kpi_overdue_list.days_past_due; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.days_past_due IS 'Days past due as of the Sunday';


--
-- Name: COLUMN kpi_overdue_list.aging_bucket; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.aging_bucket IS '1-30, 31-60, 61-90 or 90+';


--
-- Name: COLUMN kpi_overdue_list.rank_by_amount; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_overdue_list.rank_by_amount IS 'Rank within the week by amount (1 = largest)';


--
-- Name: kpi_weekly; Type: VIEW; Schema: finance_scenario; Owner: -
--

CREATE VIEW finance_scenario.kpi_weekly AS
 WITH billed AS (
         SELECT w.report_week,
            count(f.invoice_id) AS invoices_billed,
            COALESCE(sum(f.amount_sdr), (0)::numeric) AS billed_sdr
           FROM (finance.dim_week w
             LEFT JOIN finance_scenario.fact_invoice f ON (((f.invoice_date >= w.week_start) AND (f.invoice_date <= w.week_end))))
          GROUP BY w.report_week
        ), collected AS (
         SELECT w.report_week,
            count(p_1.invoice_number) AS payments_received,
            COALESCE(sum(p_1.amount_sdr), (0)::numeric) AS collected_sdr
           FROM (finance.dim_week w
             LEFT JOIN finance_scenario.fact_payment p_1 ON (((p_1.paid_date >= w.week_start) AND (p_1.paid_date <= w.week_end))))
          GROUP BY w.report_week
        ), ar AS (
         SELECT w.report_week,
            count(a.invoice_number) AS ar_invoices,
            COALESCE(sum(a.amount_sdr), (0)::numeric) AS ar_sdr,
            count(a.invoice_number) FILTER (WHERE a.is_overdue) AS overdue_invoices,
            COALESCE(sum(a.amount_sdr) FILTER (WHERE a.is_overdue), (0)::numeric) AS overdue_sdr,
            COALESCE(sum(a.amount_sdr) FILTER (WHERE (a.aging_bucket = 'current'::text)), (0)::numeric) AS aging_current_sdr,
            COALESCE(sum(a.amount_sdr) FILTER (WHERE (a.aging_bucket = '1-30'::text)), (0)::numeric) AS aging_1_30_sdr,
            COALESCE(sum(a.amount_sdr) FILTER (WHERE (a.aging_bucket = '31-60'::text)), (0)::numeric) AS aging_31_60_sdr,
            COALESCE(sum(a.amount_sdr) FILTER (WHERE (a.aging_bucket = '61-90'::text)), (0)::numeric) AS aging_61_90_sdr,
            COALESCE(sum(a.amount_sdr) FILTER (WHERE (a.aging_bucket = '90+'::text)), (0)::numeric) AS aging_90_plus_sdr
           FROM (finance.dim_week w
             LEFT JOIN finance_scenario.fact_ar_snapshot a ON ((a.report_week = w.report_week)))
          GROUP BY w.report_week
        ), dso_base AS (
         SELECT w.report_week,
            COALESCE(sum(f.amount_sdr), (0)::numeric) AS dso_window_billed_sdr
           FROM (finance.dim_week w
             LEFT JOIN finance_scenario.fact_invoice f ON (((f.invoice_date >= w.dso_window_start) AND (f.invoice_date <= w.week_end))))
          GROUP BY w.report_week
        ), budget AS (
         SELECT budget_weekly.iso_week AS report_week,
            sum(budget_weekly.budget_sdr) AS budget_sdr
           FROM public.budget_weekly
          WHERE (budget_weekly.budget_year = 2025)
          GROUP BY budget_weekly.iso_week
        ), concentration AS (
         SELECT kpi_customer_13w.report_week,
            (sum(kpi_customer_13w.billed_13w_sdr) FILTER (WHERE kpi_customer_13w.is_top10) / NULLIF(sum(kpi_customer_13w.billed_13w_sdr), (0)::numeric)) AS top10_share
           FROM finance_scenario.kpi_customer_13w
          GROUP BY kpi_customer_13w.report_week
        ), base AS (
         SELECT w.report_week,
            w.iso_week_label,
            w.week_start,
            w.week_end,
            w.is_warmup,
            w.dso_window_days,
            b.invoices_billed,
            b.billed_sdr,
            c.payments_received,
            c.collected_sdr,
            a.ar_invoices,
            a.ar_sdr,
            a.overdue_invoices,
            a.overdue_sdr,
            a.aging_current_sdr,
            a.aging_1_30_sdr,
            a.aging_31_60_sdr,
            a.aging_61_90_sdr,
            a.aging_90_plus_sdr,
            d.dso_window_billed_sdr,
            ((a.ar_sdr / NULLIF(d.dso_window_billed_sdr, (0)::numeric)) * (w.dso_window_days)::numeric) AS dso_days,
            bu.budget_sdr,
            k.top10_share
           FROM ((((((finance.dim_week w
             JOIN billed b ON ((b.report_week = w.report_week)))
             JOIN collected c ON ((c.report_week = w.report_week)))
             JOIN ar a ON ((a.report_week = w.report_week)))
             JOIN dso_base d ON ((d.report_week = w.report_week)))
             LEFT JOIN budget bu ON ((bu.report_week = w.report_week)))
             LEFT JOIN concentration k ON ((k.report_week = w.report_week)))
        ), prev AS (
         SELECT base.report_week,
            base.iso_week_label,
            base.week_start,
            base.week_end,
            base.is_warmup,
            base.invoices_billed,
            round(base.billed_sdr, 2) AS billed_sdr,
            base.payments_received,
            round(base.collected_sdr, 2) AS collected_sdr,
            base.ar_invoices,
            round(base.ar_sdr, 2) AS ar_sdr,
            base.overdue_invoices,
            round(base.overdue_sdr, 2) AS overdue_sdr,
            round(base.aging_current_sdr, 2) AS aging_current_sdr,
            round(base.aging_1_30_sdr, 2) AS aging_1_30_sdr,
            round(base.aging_31_60_sdr, 2) AS aging_31_60_sdr,
            round(base.aging_61_90_sdr, 2) AS aging_61_90_sdr,
            round(base.aging_90_plus_sdr, 2) AS aging_90_plus_sdr,
            base.dso_window_days,
            round(base.dso_window_billed_sdr, 2) AS dso_window_billed_sdr,
            round(base.dso_days, 1) AS dso_days,
            round(base.budget_sdr, 2) AS budget_sdr,
            round((base.billed_sdr - base.budget_sdr), 2) AS budget_variance_sdr,
            round((((100)::numeric * (base.billed_sdr - base.budget_sdr)) / NULLIF(base.budget_sdr, (0)::numeric)), 2) AS budget_variance_pct,
            round(((100)::numeric * base.top10_share), 2) AS top10_share_13w_pct,
            round((((100)::numeric * (base.billed_sdr - lag(base.billed_sdr) OVER wk)) / NULLIF(lag(base.billed_sdr) OVER wk, (0)::numeric)), 2) AS billed_wow_pct,
            round((((100)::numeric * (base.collected_sdr - lag(base.collected_sdr) OVER wk)) / NULLIF(lag(base.collected_sdr) OVER wk, (0)::numeric)), 2) AS collected_wow_pct,
            round((((100)::numeric * (base.ar_sdr - lag(base.ar_sdr) OVER wk)) / NULLIF(lag(base.ar_sdr) OVER wk, (0)::numeric)), 2) AS ar_wow_pct,
            round((((100)::numeric * (base.overdue_sdr - lag(base.overdue_sdr) OVER wk)) / NULLIF(lag(base.overdue_sdr) OVER wk, (0)::numeric)), 2) AS overdue_wow_pct,
            round((base.dso_days - lag(base.dso_days) OVER wk), 1) AS dso_wow_days
           FROM base
          WINDOW wk AS (ORDER BY base.report_week)
        ), rolling AS (
         SELECT base.report_week,
            count(*) OVER r13 AS roll_window_weeks,
            sum(base.billed_sdr) OVER r13 AS billed_13w_sdr,
            sum(base.budget_sdr) OVER r13 AS budget_13w_sdr,
            round(((base.aging_current_sdr / NULLIF(base.dso_window_billed_sdr, (0)::numeric)) * (base.dso_window_days)::numeric), 1) AS dso_best_days
           FROM base
          WINDOW r13 AS (ORDER BY base.report_week ROWS BETWEEN 12 PRECEDING AND CURRENT ROW)
        ), swing AS (
         SELECT p_1.report_week,
            ( SELECT
                        CASE
                            WHEN (count(*) >= 8) THEN percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((abs(x.billed_wow_pct))::double precision))
                            ELSE NULL::double precision
                        END AS "case"
                   FROM prev x
                  WHERE ((x.report_week >= (p_1.report_week - 12)) AND (x.report_week <= p_1.report_week) AND (x.billed_wow_pct IS NOT NULL))) AS billed_typ,
            ( SELECT
                        CASE
                            WHEN (count(*) >= 8) THEN percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((abs(x.collected_wow_pct))::double precision))
                            ELSE NULL::double precision
                        END AS "case"
                   FROM prev x
                  WHERE ((x.report_week >= (p_1.report_week - 12)) AND (x.report_week <= p_1.report_week) AND (x.collected_wow_pct IS NOT NULL))) AS collected_typ,
            ( SELECT
                        CASE
                            WHEN (count(*) >= 8) THEN percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((abs(x.ar_wow_pct))::double precision))
                            ELSE NULL::double precision
                        END AS "case"
                   FROM prev x
                  WHERE ((x.report_week >= (p_1.report_week - 12)) AND (x.report_week <= p_1.report_week) AND (x.ar_wow_pct IS NOT NULL))) AS ar_typ,
            ( SELECT
                        CASE
                            WHEN (count(*) >= 8) THEN percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((abs(x.overdue_wow_pct))::double precision))
                            ELSE NULL::double precision
                        END AS "case"
                   FROM prev x
                  WHERE ((x.report_week >= (p_1.report_week - 12)) AND (x.report_week <= p_1.report_week) AND (x.overdue_wow_pct IS NOT NULL))) AS overdue_typ
           FROM prev p_1
        ), flows AS (
         SELECT w.report_week,
            COALESCE(sum(f.amount_sdr) FILTER (WHERE ((f.due_date >= (w.week_end - 7)) AND (f.due_date <= (w.week_end - 1)) AND ((f.paid_date IS NULL) OR (f.paid_date > w.week_end)))), (0)::numeric) AS overdue_new_sdr,
            COALESCE(sum(f.amount_sdr) FILTER (WHERE ((f.due_date <= (w.week_end - 8)) AND (f.paid_date >= w.week_start) AND (f.paid_date <= w.week_end))), (0)::numeric) AS overdue_paid_sdr,
            COALESCE(sum(f.amount_sdr) FILTER (WHERE ((f.due_date >= w.week_start) AND (f.due_date <= w.week_end))), (0)::numeric) AS due_week_sdr,
            COALESCE(sum(f.amount_sdr) FILTER (WHERE ((f.due_date >= w.week_start) AND (f.due_date <= w.week_end) AND (f.paid_date <= w.week_end))), (0)::numeric) AS due_week_collected_sdr
           FROM (finance.dim_week w
             CROSS JOIN finance_scenario.fact_invoice f)
          GROUP BY w.report_week
        ), punctuality AS (
         SELECT w.report_week,
            ((100.0 * (count(p_1.invoice_number) FILTER (WHERE (p_1.days_paid_after_due <= 0)))::numeric) / (NULLIF(count(p_1.invoice_number), 0))::numeric) AS ontime_13w
           FROM (finance.dim_week w
             LEFT JOIN finance_scenario.fact_payment p_1 ON (((p_1.paid_date >= (w.week_end - 90)) AND (p_1.paid_date <= w.week_end))))
          GROUP BY w.report_week
        )
 SELECT p.report_week,
    p.iso_week_label,
    p.week_start,
    p.week_end,
    p.is_warmup,
    p.invoices_billed,
    p.billed_sdr,
    p.payments_received,
    p.collected_sdr,
    p.ar_invoices,
    p.ar_sdr,
    p.overdue_invoices,
    p.overdue_sdr,
    p.aging_current_sdr,
    p.aging_1_30_sdr,
    p.aging_31_60_sdr,
    p.aging_61_90_sdr,
    p.aging_90_plus_sdr,
    p.dso_window_days,
    p.dso_window_billed_sdr,
    p.dso_days,
    p.budget_sdr,
    p.budget_variance_sdr,
    p.budget_variance_pct,
    p.top10_share_13w_pct,
    p.billed_wow_pct,
    p.collected_wow_pct,
    p.ar_wow_pct,
    p.overdue_wow_pct,
    p.dso_wow_days,
    r.roll_window_weeks,
    round(r.billed_13w_sdr, 2) AS billed_13w_sdr,
    round(r.budget_13w_sdr, 2) AS budget_13w_sdr,
    round((((100)::numeric * (r.billed_13w_sdr - r.budget_13w_sdr)) / NULLIF(r.budget_13w_sdr, (0)::numeric)), 2) AS budget_variance_13w_pct,
    r.dso_best_days,
    (p.dso_days - r.dso_best_days) AS dso_delinquency_days,
    round((s.billed_typ)::numeric, 2) AS billed_wow_typical_pct,
    round((s.collected_typ)::numeric, 2) AS collected_wow_typical_pct,
    round((s.ar_typ)::numeric, 2) AS ar_wow_typical_pct,
    round((s.overdue_typ)::numeric, 2) AS overdue_wow_typical_pct,
    round(fl.overdue_new_sdr, 2) AS overdue_new_sdr,
    round(fl.overdue_paid_sdr, 2) AS overdue_paid_sdr,
    round(fl.due_week_sdr, 2) AS due_week_sdr,
    round(fl.due_week_collected_sdr, 2) AS due_week_collected_sdr,
    round((((100)::numeric * fl.due_week_collected_sdr) / NULLIF(fl.due_week_sdr, (0)::numeric)), 2) AS due_week_collected_pct,
    round(pu.ontime_13w, 2) AS ontime_13w_pct
   FROM ((((prev p
     JOIN rolling r ON ((r.report_week = p.report_week)))
     JOIN swing s ON ((s.report_week = p.report_week)))
     JOIN flows fl ON ((fl.report_week = p.report_week)))
     JOIN punctuality pu ON ((pu.report_week = p.report_week)));


--
-- Name: VIEW kpi_weekly; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON VIEW finance_scenario.kpi_weekly IS 'Scenario (planted: α = 1.6 × the real 2025 Suez traffic swing) — not NileGate''s billing. Twin of finance.kpi_weekly: Company KPIs, one row per report week (definitions: docs/finance_metrics.md). Money SDR 2 decimals, *_pct percent 2 decimals, days 1 decimal; WoW NULL in week 1. Level 2, Finance.';


--
-- Name: COLUMN kpi_weekly.report_week; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.report_week IS 'Report week 1–52';


--
-- Name: COLUMN kpi_weekly.iso_week_label; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.iso_week_label IS 'ISO week as text';


--
-- Name: COLUMN kpi_weekly.week_start; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.week_start IS 'Monday of the week';


--
-- Name: COLUMN kpi_weekly.week_end; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.week_end IS 'Sunday of the week (as of 23:59)';


--
-- Name: COLUMN kpi_weekly.is_warmup; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.is_warmup IS 'Weeks 1–13: under 91 days of history, receivables still building up; DSO on a shorter window';


--
-- Name: COLUMN kpi_weekly.invoices_billed; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.invoices_billed IS 'Number of invoices dated in the week';


--
-- Name: COLUMN kpi_weekly.billed_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.billed_sdr IS 'Billed revenue: sum of invoice amounts dated in the week (SDR)';


--
-- Name: COLUMN kpi_weekly.payments_received; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.payments_received IS 'Number of payments dated in the week';


--
-- Name: COLUMN kpi_weekly.collected_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.collected_sdr IS 'Collections: sum of payments dated in the week (SDR)';


--
-- Name: COLUMN kpi_weekly.ar_invoices; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.ar_invoices IS 'Number of open invoices at the week end';


--
-- Name: COLUMN kpi_weekly.ar_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.ar_sdr IS 'Accounts receivable at the week end: invoices issued by Sunday and unpaid by Sunday (SDR)';


--
-- Name: COLUMN kpi_weekly.overdue_invoices; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.overdue_invoices IS 'Number of open invoices at least 1 day past due';


--
-- Name: COLUMN kpi_weekly.overdue_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.overdue_sdr IS 'Overdue receivables (≥ 1 day past due) at the week end (SDR)';


--
-- Name: COLUMN kpi_weekly.aging_current_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.aging_current_sdr IS 'Receivables not yet due (SDR)';


--
-- Name: COLUMN kpi_weekly.aging_1_30_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.aging_1_30_sdr IS 'Receivables 1–30 days past due (SDR)';


--
-- Name: COLUMN kpi_weekly.aging_31_60_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.aging_31_60_sdr IS 'Receivables 31–60 days past due (SDR)';


--
-- Name: COLUMN kpi_weekly.aging_61_90_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.aging_61_90_sdr IS 'Receivables 61–90 days past due (SDR)';


--
-- Name: COLUMN kpi_weekly.aging_90_plus_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.aging_90_plus_sdr IS 'Receivables more than 90 days past due (SDR)';


--
-- Name: COLUMN kpi_weekly.dso_window_days; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.dso_window_days IS 'Days in the DSO window (91, fewer in warm-up weeks)';


--
-- Name: COLUMN kpi_weekly.dso_window_billed_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.dso_window_billed_sdr IS 'Billed revenue inside the DSO window (SDR)';


--
-- Name: COLUMN kpi_weekly.dso_days; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.dso_days IS 'DSO = ar_sdr ÷ dso_window_billed_sdr × dso_window_days (owner decision P2-1), 1 decimal';


--
-- Name: COLUMN kpi_weekly.budget_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.budget_sdr IS 'Weekly budget, all categories (SDR)';


--
-- Name: COLUMN kpi_weekly.budget_variance_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.budget_variance_sdr IS 'billed_sdr − budget_sdr (SDR)';


--
-- Name: COLUMN kpi_weekly.budget_variance_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.budget_variance_pct IS '(billed − budget) ÷ budget, percent';


--
-- Name: COLUMN kpi_weekly.top10_share_13w_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.top10_share_13w_pct IS 'Share of the 10 largest customers in the trailing 13 weeks'' billing, percent';


--
-- Name: COLUMN kpi_weekly.billed_wow_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.billed_wow_pct IS 'Billed revenue change vs the previous week, percent';


--
-- Name: COLUMN kpi_weekly.collected_wow_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.collected_wow_pct IS 'Collections change vs the previous week, percent';


--
-- Name: COLUMN kpi_weekly.ar_wow_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.ar_wow_pct IS 'Receivables change vs the previous week, percent';


--
-- Name: COLUMN kpi_weekly.overdue_wow_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.overdue_wow_pct IS 'Overdue receivables change vs the previous week, percent';


--
-- Name: COLUMN kpi_weekly.dso_wow_days; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.dso_wow_days IS 'DSO change vs the previous week, in days';


--
-- Name: COLUMN kpi_weekly.roll_window_weeks; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.roll_window_weeks IS 'Weeks in the rolling window of the *_13w columns: 13, or the report week number before week 13 (M9b).';


--
-- Name: COLUMN kpi_weekly.billed_13w_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.billed_13w_sdr IS 'Billed revenue of the rolling window (weeks w-12 … w, from week 1 before week 13), SDR (M9b).';


--
-- Name: COLUMN kpi_weekly.budget_13w_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.budget_13w_sdr IS 'Budget of the same rolling window, SDR (M9b).';


--
-- Name: COLUMN kpi_weekly.budget_variance_13w_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.budget_variance_13w_pct IS '(billed_13w − budget_13w) ÷ budget_13w × 100: the period''s position against plan (M9b).';


--
-- Name: COLUMN kpi_weekly.dso_best_days; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.dso_best_days IS 'Best-possible DSO: current (not overdue) AR ÷ DSO-window billing × window days, 1 decimal (M12).';


--
-- Name: COLUMN kpi_weekly.dso_delinquency_days; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.dso_delinquency_days IS 'dso_days − dso_best_days: the days of billing outstanding because customers pay late (M12).';


--
-- Name: COLUMN kpi_weekly.billed_wow_typical_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.billed_wow_typical_pct IS 'Typical weekly swing of billed: median |billed_wow_pct| over the rolling window, at least 8 values, else NULL (M13).';


--
-- Name: COLUMN kpi_weekly.collected_wow_typical_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.collected_wow_typical_pct IS 'Typical weekly swing of collected: median |collected_wow_pct| over the rolling window, at least 8 values (M13).';


--
-- Name: COLUMN kpi_weekly.ar_wow_typical_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.ar_wow_typical_pct IS 'Typical weekly swing of AR: median |ar_wow_pct| over the rolling window, at least 8 values (M13).';


--
-- Name: COLUMN kpi_weekly.overdue_wow_typical_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.overdue_wow_typical_pct IS 'Typical weekly swing of overdue: median |overdue_wow_pct| over the rolling window, at least 8 values (M13).';


--
-- Name: COLUMN kpi_weekly.overdue_new_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.overdue_new_sdr IS 'Invoices that became overdue in the week (due from the previous Sunday to this Saturday) and are unpaid at Sunday, SDR (M14).';


--
-- Name: COLUMN kpi_weekly.overdue_paid_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.overdue_paid_sdr IS 'Payments in the week on invoices already overdue at the previous Sunday, SDR; overdue change = new − paid (M14).';


--
-- Name: COLUMN kpi_weekly.due_week_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.due_week_sdr IS 'Invoices falling due in the week (Monday–Sunday), SDR (M14).';


--
-- Name: COLUMN kpi_weekly.due_week_collected_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.due_week_collected_sdr IS 'Part of due_week_sdr paid by the week''s Sunday, SDR (M14).';


--
-- Name: COLUMN kpi_weekly.due_week_collected_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.due_week_collected_pct IS 'due_week_collected_sdr ÷ due_week_sdr × 100 (M14).';


--
-- Name: COLUMN kpi_weekly.ontime_13w_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly.ontime_13w_pct IS 'Share of the payments made in the 91 days ending Sunday that were paid on or before due, percent (M16).';


--
-- Name: kpi_traffic_link; Type: VIEW; Schema: finance_scenario; Owner: -
--

CREATE VIEW finance_scenario.kpi_traffic_link AS
 WITH t AS (
         SELECT ((floor((((suez_transits_daily.date - '2024-12-30'::date))::numeric / 7.0)))::integer + 1) AS week,
            sum(suez_transits_daily.n_total) AS transits
           FROM external.suez_transits_daily
          GROUP BY ((floor((((suez_transits_daily.date - '2024-12-30'::date))::numeric / 7.0)))::integer + 1)
        ), k AS (
         SELECT kw.report_week,
            kw.invoices_billed,
            t0.transits AS transits_week,
            t1.transits AS transits_prev_week
           FROM ((finance_scenario.kpi_weekly kw
             JOIN t t0 ON ((t0.week = kw.report_week)))
             JOIN t t1 ON ((t1.week = (kw.report_week - 1))))
        ), r AS (
         SELECT k.report_week,
            k.invoices_billed,
            k.transits_week,
            k.transits_prev_week,
            count(*) OVER w AS n_weeks,
            corr((k.invoices_billed)::double precision, (k.transits_week)::double precision) OVER w AS r0,
            corr((k.invoices_billed)::double precision, (k.transits_prev_week)::double precision) OVER w AS r1
           FROM k
          WINDOW w AS (ORDER BY k.report_week ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        )
 SELECT report_week,
    invoices_billed,
    (transits_week)::integer AS suez_transits_week,
    (transits_prev_week)::integer AS suez_transits_prev_week,
    (n_weeks)::integer AS n_weeks,
        CASE
            WHEN (n_weeks >= 13) THEN round((r0)::numeric, 3)
            ELSE NULL::numeric
        END AS r_lag0,
        CASE
            WHEN (n_weeks >= 13) THEN round((r1)::numeric, 3)
            ELSE NULL::numeric
        END AS r_lag1,
        CASE
            WHEN (n_weeks >= 13) THEN round((((2)::double precision / sqrt((n_weeks)::double precision)))::numeric, 3)
            ELSE NULL::numeric
        END AS r_threshold,
        CASE
            WHEN (n_weeks < 13) THEN NULL::text
            WHEN ((abs(r0) >= ((2)::double precision / sqrt((n_weeks)::double precision))) OR (abs(r1) >= ((2)::double precision / sqrt((n_weeks)::double precision)))) THEN 'link'::text
            ELSE 'no_link'::text
        END AS link,
        CASE
            WHEN (n_weeks < 13) THEN NULL::integer
            WHEN ((abs(r0) >= ((2)::double precision / sqrt((n_weeks)::double precision))) AND (abs(r0) >= COALESCE(abs(r1), (0)::double precision))) THEN 0
            WHEN (abs(r1) >= ((2)::double precision / sqrt((n_weeks)::double precision))) THEN 1
            WHEN (abs(r0) >= ((2)::double precision / sqrt((n_weeks)::double precision))) THEN 0
            ELSE NULL::integer
        END AS link_lag
   FROM r;


--
-- Name: VIEW kpi_traffic_link; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON VIEW finance_scenario.kpi_traffic_link IS 'Scenario (planted: α = 1.6 × the real 2025 Suez traffic swing) — not NileGate''s billing. M17 on the scenario; same definition as finance.kpi_traffic_link (migration 027)';


--
-- Name: COLUMN kpi_traffic_link.report_week; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_traffic_link.report_week IS 'Report week 1-52 (ISO 2025)';


--
-- Name: COLUMN kpi_traffic_link.invoices_billed; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_traffic_link.invoices_billed IS 'Invoices issued in the week (kpi_weekly.invoices_billed of this schema)';


--
-- Name: COLUMN kpi_traffic_link.suez_transits_week; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_traffic_link.suez_transits_week IS 'Suez Canal transits Monday-Sunday of the week (external.suez_transits_daily, n_total)';


--
-- Name: COLUMN kpi_traffic_link.suez_transits_prev_week; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_traffic_link.suez_transits_prev_week IS 'Suez Canal transits of the week before (lag 1; week 0 = 2024-12-23 ... 29)';


--
-- Name: COLUMN kpi_traffic_link.n_weeks; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_traffic_link.n_weeks IS 'Weeks in the year-to-date window (= report_week)';


--
-- Name: COLUMN kpi_traffic_link.r_lag0; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_traffic_link.r_lag0 IS 'Pearson r, weeks 1..w: invoice count vs the same week''s transits (3 decimals; NULL before week 13)';


--
-- Name: COLUMN kpi_traffic_link.r_lag1; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_traffic_link.r_lag1 IS 'Pearson r, weeks 1..w: invoice count vs the previous week''s transits (3 decimals; NULL before week 13)';


--
-- Name: COLUMN kpi_traffic_link.r_threshold; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_traffic_link.r_threshold IS '2 / sqrt(n_weeks): about the 5 % two-sided level for one test; two lags double the false rate (3 decimals)';


--
-- Name: COLUMN kpi_traffic_link.link; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_traffic_link.link IS 'link when |r_lag0| or |r_lag1| >= r_threshold (unrounded), else no_link; NULL before week 13. Moves with, never caused by';


--
-- Name: COLUMN kpi_traffic_link.link_lag; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_traffic_link.link_lag IS 'The lag that passes (0 or 1; the larger |r| when both do); NULL when no_link or before week 13';


--
-- Name: kpi_weekly_category; Type: VIEW; Schema: finance_scenario; Owner: -
--

CREATE VIEW finance_scenario.kpi_weekly_category AS
 WITH grid AS (
         SELECT w.report_week,
            w.week_start,
            w.week_end,
            b.vessel_category,
            b.budget_sdr
           FROM (finance.dim_week w
             JOIN public.budget_weekly b ON (((b.budget_year = 2025) AND (b.iso_week = w.report_week))))
        ), base AS (
         SELECT g.report_week,
            g.vessel_category,
            g.budget_sdr,
            count(f.invoice_id) AS invoices_billed,
            COALESCE(sum(f.amount_sdr), (0)::numeric) AS billed_sdr
           FROM (grid g
             LEFT JOIN finance_scenario.fact_invoice f ON (((f.vessel_category = g.vessel_category) AND (f.invoice_date >= g.week_start) AND (f.invoice_date <= g.week_end))))
          GROUP BY g.report_week, g.vessel_category, g.budget_sdr
        )
 SELECT report_week,
    vessel_category,
    invoices_billed,
    round(billed_sdr, 2) AS billed_sdr,
    round(budget_sdr, 2) AS budget_sdr,
    round((billed_sdr - budget_sdr), 2) AS budget_variance_sdr,
    round((((100)::numeric * (billed_sdr - budget_sdr)) / NULLIF(budget_sdr, (0)::numeric)), 2) AS budget_variance_pct,
    round(lag(billed_sdr) OVER cw, 2) AS billed_prev_sdr,
    round((billed_sdr - lag(billed_sdr) OVER cw), 2) AS billed_wow_change_sdr,
    round((((100)::numeric * (billed_sdr - lag(billed_sdr) OVER cw)) / NULLIF(lag(billed_sdr) OVER cw, (0)::numeric)), 2) AS billed_wow_pct,
    lag(invoices_billed) OVER cw AS invoices_prev
   FROM base
  WINDOW cw AS (PARTITION BY vessel_category ORDER BY report_week);


--
-- Name: VIEW kpi_weekly_category; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON VIEW finance_scenario.kpi_weekly_category IS 'Scenario (planted: α = 1.6 × the real 2025 Suez traffic swing) — not NileGate''s billing. Twin of finance.kpi_weekly_category: Billing vs budget per report week and vessel category (52 × 13 rows); the week''s drivers = largest |billed_wow_change_sdr|. Level 2, Finance.';


--
-- Name: COLUMN kpi_weekly_category.report_week; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_category.report_week IS 'Report week';


--
-- Name: COLUMN kpi_weekly_category.vessel_category; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_category.vessel_category IS 'Vessel category (13 tariff categories)';


--
-- Name: COLUMN kpi_weekly_category.invoices_billed; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_category.invoices_billed IS 'Invoices of the category dated in the week';


--
-- Name: COLUMN kpi_weekly_category.billed_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_category.billed_sdr IS 'Billed revenue of the category in the week (SDR)';


--
-- Name: COLUMN kpi_weekly_category.budget_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_category.budget_sdr IS 'Budget of the category for the week (SDR)';


--
-- Name: COLUMN kpi_weekly_category.budget_variance_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_category.budget_variance_sdr IS 'billed_sdr − budget_sdr (SDR)';


--
-- Name: COLUMN kpi_weekly_category.budget_variance_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_category.budget_variance_pct IS '(billed − budget) ÷ budget, percent';


--
-- Name: COLUMN kpi_weekly_category.billed_prev_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_category.billed_prev_sdr IS 'Billed revenue of the category in the previous week (SDR); NULL in week 1';


--
-- Name: COLUMN kpi_weekly_category.billed_wow_change_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_category.billed_wow_change_sdr IS 'billed_sdr − billed_prev_sdr (SDR)';


--
-- Name: COLUMN kpi_weekly_category.billed_wow_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_category.billed_wow_pct IS 'Change vs the previous week, percent; NULL when the previous week was 0';


--
-- Name: COLUMN kpi_weekly_category.invoices_prev; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_category.invoices_prev IS 'Invoices billed in the category in the previous report week; NULL in week 1 (shows how many invoices sit behind a WoW driver).';


--
-- Name: kpi_weekly_trend; Type: VIEW; Schema: finance_scenario; Owner: -
--

CREATE VIEW finance_scenario.kpi_weekly_trend AS
 SELECT s.report_week,
    t.report_week AS trend_week,
    (t.report_week - s.report_week) AS week_offset,
    (t.report_week = s.report_week) AS is_report_week,
    t.iso_week_label AS trend_week_label,
    t.week_end AS trend_week_end,
    t.is_warmup,
    t.invoices_billed,
    t.billed_sdr,
    t.collected_sdr,
    t.ar_sdr,
    t.overdue_sdr,
    t.dso_days,
    t.budget_sdr,
    t.budget_variance_sdr,
    t.budget_variance_pct,
    t.top10_share_13w_pct
   FROM (finance.dim_week s
     JOIN finance_scenario.kpi_weekly t ON (((t.report_week >= (s.report_week - 12)) AND (t.report_week <= s.report_week))));


--
-- Name: VIEW kpi_weekly_trend; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON VIEW finance_scenario.kpi_weekly_trend IS 'Scenario (planted: α = 1.6 × the real 2025 Suez traffic swing) — not NileGate''s billing. Twin of finance.kpi_weekly_trend: The 13-week trend of each report week (M11): one row per (report_week, trend_week) for the weeks w−12 … w (fewer in weeks 1–12), values from kpi_weekly. Filter report_week, chart over trend_week. Level 2, Finance.';


--
-- Name: COLUMN kpi_weekly_trend.report_week; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.report_week IS 'The report week the trend belongs to (filter on this)';


--
-- Name: COLUMN kpi_weekly_trend.trend_week; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.trend_week IS 'A week inside the trend window (chart axis)';


--
-- Name: COLUMN kpi_weekly_trend.week_offset; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.week_offset IS 'trend_week − report_week: −12 … 0';


--
-- Name: COLUMN kpi_weekly_trend.is_report_week; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.is_report_week IS 'True on the report week itself (offset 0)';


--
-- Name: COLUMN kpi_weekly_trend.trend_week_label; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.trend_week_label IS 'ISO label of the trend week, e.g. 2025-W23';


--
-- Name: COLUMN kpi_weekly_trend.trend_week_end; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.trend_week_end IS 'Sunday of the trend week';


--
-- Name: COLUMN kpi_weekly_trend.is_warmup; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.is_warmup IS 'The trend week is a warm-up week (1–13)';


--
-- Name: COLUMN kpi_weekly_trend.invoices_billed; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.invoices_billed IS 'kpi_weekly.invoices_billed of the trend week';


--
-- Name: COLUMN kpi_weekly_trend.billed_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.billed_sdr IS 'kpi_weekly.billed_sdr of the trend week (SDR)';


--
-- Name: COLUMN kpi_weekly_trend.collected_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.collected_sdr IS 'kpi_weekly.collected_sdr of the trend week (SDR)';


--
-- Name: COLUMN kpi_weekly_trend.ar_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.ar_sdr IS 'kpi_weekly.ar_sdr of the trend week (SDR)';


--
-- Name: COLUMN kpi_weekly_trend.overdue_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.overdue_sdr IS 'kpi_weekly.overdue_sdr of the trend week (SDR)';


--
-- Name: COLUMN kpi_weekly_trend.dso_days; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.dso_days IS 'kpi_weekly.dso_days of the trend week';


--
-- Name: COLUMN kpi_weekly_trend.budget_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.budget_sdr IS 'kpi_weekly.budget_sdr of the trend week (SDR)';


--
-- Name: COLUMN kpi_weekly_trend.budget_variance_sdr; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.budget_variance_sdr IS 'kpi_weekly.budget_variance_sdr of the trend week (SDR)';


--
-- Name: COLUMN kpi_weekly_trend.budget_variance_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.budget_variance_pct IS 'kpi_weekly.budget_variance_pct of the trend week (percent)';


--
-- Name: COLUMN kpi_weekly_trend.top10_share_13w_pct; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.kpi_weekly_trend.top10_share_13w_pct IS 'kpi_weekly.top10_share_13w_pct of the trend week (percent)';


--
-- Name: scenario_info; Type: TABLE; Schema: finance_scenario; Owner: -
--

CREATE TABLE finance_scenario.scenario_info (
    label text NOT NULL,
    alpha numeric NOT NULL,
    seed_draw integer NOT NULL,
    link_rate_52 numeric NOT NULL,
    natural_rate_52 numeric NOT NULL,
    realized_r_52 numeric NOT NULL,
    source text NOT NULL
);


--
-- Name: TABLE scenario_info; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON TABLE finance_scenario.scenario_info IS 'The one row that labels this scenario: its planted amplification and how it was chosen';


--
-- Name: COLUMN scenario_info.label; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.scenario_info.label IS 'The label every scenario output must show';


--
-- Name: COLUMN scenario_info.alpha; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.scenario_info.alpha IS 'Planted amplification of the weekly traffic swing (1 = billing follows traffic exactly)';


--
-- Name: COLUMN scenario_info.seed_draw; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.scenario_info.seed_draw IS 'Seed of the multinomial draw, the permutation and the days';


--
-- Name: COLUMN scenario_info.link_rate_52; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.scenario_info.link_rate_52 IS 'Share of 2000 seeded draws at this alpha where the link rule fires at 52 weeks';


--
-- Name: COLUMN scenario_info.natural_rate_52; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.scenario_info.natural_rate_52 IS 'The same share at alpha = 1 (the natural scenario)';


--
-- Name: COLUMN scenario_info.realized_r_52; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.scenario_info.realized_r_52 IS 'Pearson r of this draw: weekly invoice count vs weekly Suez transits, weeks 1-52, lag 0';


--
-- Name: COLUMN scenario_info.source; Type: COMMENT; Schema: finance_scenario; Owner: -
--

COMMENT ON COLUMN finance_scenario.scenario_info.source IS 'Where the traffic comes from';


--
-- Name: budget_weekly; Type: TABLE; Schema: finance_test; Owner: -
--

CREATE TABLE finance_test.budget_weekly (
    budget_year integer NOT NULL,
    iso_week integer NOT NULL,
    vessel_category text NOT NULL,
    budget_sdr numeric NOT NULL,
    CONSTRAINT budget_weekly_amount_chk CHECK ((budget_sdr >= (0)::numeric)),
    CONSTRAINT budget_weekly_category_chk CHECK ((vessel_category = ANY (ARRAY['Chemical Tankers & Other Liquid Bulk Tankers'::text, 'Containerships'::text, 'Crude Oil Tankers'::text, 'Cruise Ships'::text, 'Dry Bulk Vessels'::text, 'General Cargo / Multi-Purpose / Heavy Lift Vessels'::text, 'Liquefied Natural Gas (LNG) Carriers'::text, 'Liquefied Petroleum Gas (LPG) Carriers'::text, 'Other Vessels'::text, 'Petroleum Product Tankers'::text, 'Roll-On/Roll-Off (Ro/Ro) Vessels'::text, 'Special Floating Units'::text, 'Vehicles Carriers'::text]))),
    CONSTRAINT budget_weekly_week_chk CHECK (((iso_week >= 1) AND (iso_week <= 52))),
    CONSTRAINT budget_weekly_year_chk CHECK ((budget_year = 2025))
);


--
-- Name: TABLE budget_weekly; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON TABLE finance_test.budget_weekly IS 'Budget rows of the 4 golden weeks, one of them changed (a planted budget miss). Level 2, Finance.';


--
-- Name: invoices; Type: TABLE; Schema: finance_test; Owner: -
--

CREATE TABLE finance_test.invoices (
    invoice_number text NOT NULL,
    vessel_id integer NOT NULL,
    invoice_date date NOT NULL,
    scnt_tons numeric NOT NULL,
    billed_sdr numeric NOT NULL,
    CONSTRAINT test_invoices_amount_chk CHECK ((billed_sdr > (0)::numeric)),
    CONSTRAINT test_invoices_number_chk CHECK ((invoice_number ~ '^INV-[0-9]{7}$'::text)),
    CONSTRAINT test_invoices_scnt_chk CHECK ((scnt_tons > (0)::numeric))
);


--
-- Name: TABLE invoices; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON TABLE finance_test.invoices IS 'Invoices of 4 golden weeks as billed, some with planted errors (no label column). Level 2, Finance.';


--
-- Name: COLUMN invoices.invoice_number; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoices.invoice_number IS 'Invoice number (a planted duplicate has a new number)';


--
-- Name: COLUMN invoices.vessel_id; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoices.vessel_id IS 'The vessel (FK public.vessels)';


--
-- Name: COLUMN invoices.invoice_date; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoices.invoice_date IS 'Invoice date';


--
-- Name: COLUMN invoices.scnt_tons; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoices.scnt_tons IS 'Suez Canal Net Tonnage as billed';


--
-- Name: COLUMN invoices.billed_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoices.billed_sdr IS 'Amount billed in SDR';


--
-- Name: invoice_audit; Type: VIEW; Schema: finance_test; Owner: -
--

CREATE VIEW finance_test.invoice_audit AS
 WITH billed AS (
         SELECT i.invoice_number,
            i.vessel_id,
            i.invoice_date,
            i.scnt_tons,
            i.billed_sdr,
            NULL::numeric AS billed_rate
           FROM finance_test.invoices i
        ), inv AS (
         SELECT b.invoice_number,
            b.vessel_id,
            b.invoice_date,
            b.scnt_tons,
            b.billed_sdr,
            b.billed_rate,
            v.vessel_name,
            v.vessel_type AS vessel_category,
            v.condition,
            v.scnt_tons AS vessel_scnt,
                CASE
                    WHEN (v.vessel_type = 'Special Floating Units'::text) THEN 'Laden'::text
                    ELSE v.condition
                END AS priced_condition,
            d.report_week
           FROM ((billed b
             JOIN public.vessels v ON ((v.vessel_id = b.vessel_id)))
             JOIN finance.dim_date d ON ((d.date_day = b.invoice_date)))
        ), scenario AS (
         SELECT inv.invoice_number,
            'expected'::text AS scenario,
            inv.vessel_category AS category,
            inv.priced_condition AS cond,
            inv.vessel_scnt AS tons
           FROM inv
        UNION ALL
         SELECT inv.invoice_number,
            'invoice_tonnage'::text,
            inv.vessel_category,
            inv.priced_condition,
            inv.scnt_tons
           FROM inv
          WHERE (inv.scnt_tons <> inv.vessel_scnt)
        UNION ALL
         SELECT inv.invoice_number,
            'condition_swapped'::text,
            inv.vessel_category,
                CASE inv.condition
                    WHEN 'Laden'::text THEN 'Ballast'::text
                    ELSE 'Laden'::text
                END AS "case",
            inv.vessel_scnt
           FROM inv
          WHERE (inv.vessel_category <> 'Special Floating Units'::text)
        UNION ALL
         SELECT inv.invoice_number,
            'sfu_priced_ballast'::text,
            'Other Vessels'::text,
            'Ballast'::text,
            inv.vessel_scnt
           FROM inv
          WHERE (inv.vessel_category = 'Special Floating Units'::text)
        UNION ALL
         SELECT inv.invoice_number,
            'notes_crude_ballast'::text,
            'Crude Oil Tankers'::text,
            'Ballast'::text,
            inv.vessel_scnt
           FROM inv
          WHERE ((inv.priced_condition = 'Ballast'::text) AND (inv.vessel_category = 'Chemical Tankers & Other Liquid Bulk Tankers'::text))
        ), priced AS (
         SELECT s.invoice_number,
            s.scenario,
            sum((t.rate_sdr_per_ton * (LEAST(s.tons, COALESCE(t.band_max_tons, s.tons)) - t.band_min_tons))) AS toll_exact,
            (array_agg(t.rate_sdr_per_ton ORDER BY t.band_order DESC))[1] AS terminal_rate,
            (array_agg(t.band_label ORDER BY t.band_order DESC))[1] AS terminal_band
           FROM (scenario s
             JOIN public.toll_rate_bands t ON (((t.vessel_category = s.category) AND (t.laden_ballast = s.cond) AND (s.tons > t.band_min_tons))))
          GROUP BY s.invoice_number, s.scenario
        ), hyp AS (
         SELECT i.invoice_number,
            i.vessel_id,
            i.invoice_date,
            i.scnt_tons,
            i.billed_sdr,
            i.billed_rate,
            i.vessel_name,
            i.vessel_category,
            i.condition,
            i.vessel_scnt,
            i.priced_condition,
            i.report_week,
            e.toll_exact AS expected_exact,
            round(e.toll_exact, 2) AS expected_sdr,
            e.terminal_rate,
            e.terminal_band,
            round(it.toll_exact, 2) AS invoice_tonnage_sdr,
            round((e.terminal_rate * i.vessel_scnt), 2) AS flat_terminal_sdr,
            round(cs.toll_exact, 2) AS condition_swapped_sdr,
            round(sb.toll_exact, 2) AS sfu_ballast_sdr,
            round(nc.toll_exact, 2) AS notes_crude_sdr,
            row_number() OVER w AS dup_rank,
            first_value(i.invoice_number) OVER w AS dup_first
           FROM (((((inv i
             JOIN priced e ON (((e.invoice_number = i.invoice_number) AND (e.scenario = 'expected'::text))))
             LEFT JOIN priced it ON (((it.invoice_number = i.invoice_number) AND (it.scenario = 'invoice_tonnage'::text))))
             LEFT JOIN priced cs ON (((cs.invoice_number = i.invoice_number) AND (cs.scenario = 'condition_swapped'::text))))
             LEFT JOIN priced sb ON (((sb.invoice_number = i.invoice_number) AND (sb.scenario = 'sfu_priced_ballast'::text))))
             LEFT JOIN priced nc ON (((nc.invoice_number = i.invoice_number) AND (nc.scenario = 'notes_crude_ballast'::text))))
          WINDOW w AS (PARTITION BY i.vessel_id, i.invoice_date, i.billed_sdr ORDER BY i.invoice_number)
        ), findings AS (
         SELECT h.invoice_number,
            h.vessel_id,
            h.invoice_date,
            h.scnt_tons,
            h.billed_sdr,
            h.billed_rate,
            h.vessel_name,
            h.vessel_category,
            h.condition,
            h.vessel_scnt,
            h.priced_condition,
            h.report_week,
            h.expected_exact,
            h.expected_sdr,
            h.terminal_rate,
            h.terminal_band,
            h.invoice_tonnage_sdr,
            h.flat_terminal_sdr,
            h.condition_swapped_sdr,
            h.sfu_ballast_sdr,
            h.notes_crude_sdr,
            h.dup_rank,
            h.dup_first,
            'duplicate_charge'::text AS check_code,
            NULL::text AS probable_cause,
            (0)::numeric AS expected_charge,
            h.dup_first AS duplicate_of,
            format('same vessel, date and amount as %s: the whole charge is billed twice'::text, h.dup_first) AS evidence
           FROM hyp h
          WHERE (h.dup_rank > 1)
        UNION ALL
         SELECT h.invoice_number,
            h.vessel_id,
            h.invoice_date,
            h.scnt_tons,
            h.billed_sdr,
            h.billed_rate,
            h.vessel_name,
            h.vessel_category,
            h.condition,
            h.vessel_scnt,
            h.priced_condition,
            h.report_week,
            h.expected_exact,
            h.expected_sdr,
            h.terminal_rate,
            h.terminal_band,
            h.invoice_tonnage_sdr,
            h.flat_terminal_sdr,
            h.condition_swapped_sdr,
            h.sfu_ballast_sdr,
            h.notes_crude_sdr,
            h.dup_rank,
            h.dup_first,
            'tonnage_mismatch'::text,
            NULL::text,
            h.expected_sdr,
            NULL::text,
            format('invoice SCNT %s <> vessel SCNT %s'::text, h.scnt_tons, h.vessel_scnt) AS format
           FROM hyp h
          WHERE ((h.dup_rank = 1) AND (h.scnt_tons <> h.vessel_scnt))
        UNION ALL
         SELECT h.invoice_number,
            h.vessel_id,
            h.invoice_date,
            h.scnt_tons,
            h.billed_sdr,
            h.billed_rate,
            h.vessel_name,
            h.vessel_category,
            h.condition,
            h.vessel_scnt,
            h.priced_condition,
            h.report_week,
            h.expected_exact,
            h.expected_sdr,
            h.terminal_rate,
            h.terminal_band,
            h.invoice_tonnage_sdr,
            h.flat_terminal_sdr,
            h.condition_swapped_sdr,
            h.sfu_ballast_sdr,
            h.notes_crude_sdr,
            h.dup_rank,
            h.dup_first,
            'amount_mismatch'::text,
                CASE
                    WHEN (abs((h.billed_sdr - h.invoice_tonnage_sdr)) <= 0.01) THEN 'billed_on_invoice_tonnage'::text
                    WHEN (abs((h.billed_sdr - h.flat_terminal_sdr)) <= 0.01) THEN 'flat_terminal_rate'::text
                    WHEN (abs((h.billed_sdr - h.condition_swapped_sdr)) <= 0.01) THEN 'condition_swapped'::text
                    WHEN (abs((h.billed_sdr - h.sfu_ballast_sdr)) <= 0.01) THEN 'sfu_priced_ballast'::text
                    WHEN (abs((h.billed_sdr - h.notes_crude_sdr)) <= 0.01) THEN 'notes_crude_ballast_rate'::text
                    ELSE 'unexplained'::text
                END AS "case",
            h.expected_sdr,
            NULL::text,
            format('billed %s SDR; tariff %s / %s at %s SCNT = %s SDR (progressive, terminal band %s at %s SDR/t)'::text, h.billed_sdr, h.vessel_category, h.priced_condition, h.vessel_scnt, h.expected_sdr, h.terminal_band, h.terminal_rate) AS format
           FROM hyp h
          WHERE ((h.dup_rank = 1) AND (abs((h.billed_sdr - h.expected_exact)) > 0.01))
        UNION ALL
         SELECT h.invoice_number,
            h.vessel_id,
            h.invoice_date,
            h.scnt_tons,
            h.billed_sdr,
            h.billed_rate,
            h.vessel_name,
            h.vessel_category,
            h.condition,
            h.vessel_scnt,
            h.priced_condition,
            h.report_week,
            h.expected_exact,
            h.expected_sdr,
            h.terminal_rate,
            h.terminal_band,
            h.invoice_tonnage_sdr,
            h.flat_terminal_sdr,
            h.condition_swapped_sdr,
            h.sfu_ballast_sdr,
            h.notes_crude_sdr,
            h.dup_rank,
            h.dup_first,
            'rate_mismatch'::text,
            NULL::text,
            h.expected_sdr,
            NULL::text,
            format('stored rate %s SDR/t <> terminal band %s rate %s SDR/t'::text, h.billed_rate, h.terminal_band, h.terminal_rate) AS format
           FROM hyp h
          WHERE ((h.dup_rank = 1) AND (h.billed_rate IS NOT NULL) AND (h.billed_rate <> h.terminal_rate))
        )
 SELECT report_week,
    invoice_number,
    invoice_date,
    vessel_id,
    vessel_name,
    vessel_category,
    condition AS vessel_condition,
    check_code,
    probable_cause,
    billed_sdr,
    expected_charge AS expected_sdr,
    round((billed_sdr - expected_charge), 2) AS difference_sdr,
    duplicate_of,
    evidence,
        CASE
            WHEN (probable_cause = 'notes_crude_ballast_rate'::text) THEN 'manual_review'::text
            ELSE 'error'::text
        END AS review
   FROM findings;


--
-- Name: VIEW invoice_audit; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON VIEW finance_test.invoice_audit IS 'The same audit over the evaluation copy finance_test.invoices (Agents plan §4a R7; same SQL as finance.invoice_audit except the source CTE). Evaluation only; invisible to Power BI. Level 2, Finance.';


--
-- Name: COLUMN invoice_audit.report_week; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.report_week IS 'Report week of the invoice date (ISO 2025 week)';


--
-- Name: COLUMN invoice_audit.invoice_number; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.invoice_number IS 'The invoice with the finding';


--
-- Name: COLUMN invoice_audit.invoice_date; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.invoice_date IS 'Invoice date';


--
-- Name: COLUMN invoice_audit.vessel_id; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.vessel_id IS 'The billed vessel';


--
-- Name: COLUMN invoice_audit.vessel_name; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.vessel_name IS 'Vessel name';


--
-- Name: COLUMN invoice_audit.vessel_category; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.vessel_category IS 'Tariff category of the vessel (vessels.vessel_type)';


--
-- Name: COLUMN invoice_audit.vessel_condition; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.vessel_condition IS 'Condition of the vessel (vessels.condition); Special Floating Units are priced Laden';


--
-- Name: COLUMN invoice_audit.check_code; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.check_code IS 'duplicate_charge | tonnage_mismatch | amount_mismatch | rate_mismatch (never: the copy stores no rate)';


--
-- Name: COLUMN invoice_audit.probable_cause; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.probable_cause IS 'amount_mismatch only: billed_on_invoice_tonnage | flat_terminal_rate | condition_swapped | sfu_priced_ballast | notes_crude_ballast_rate | unexplained';


--
-- Name: COLUMN invoice_audit.billed_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.billed_sdr IS 'Amount billed (SDR)';


--
-- Name: COLUMN invoice_audit.expected_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.expected_sdr IS 'Correct charge (SDR): the progressive toll of the vessel; 0 for a duplicate';


--
-- Name: COLUMN invoice_audit.difference_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.difference_sdr IS 'billed - expected (SDR)';


--
-- Name: COLUMN invoice_audit.duplicate_of; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.duplicate_of IS 'duplicate_charge only: the original invoice number';


--
-- Name: COLUMN invoice_audit.evidence; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.evidence IS 'The numbers behind the finding';


--
-- Name: COLUMN invoice_audit.review; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.invoice_audit.review IS 'error | manual_review (a tariff Notes rule, migration 019)';


--
-- Name: kpi_weekly; Type: VIEW; Schema: finance_test; Owner: -
--

CREATE VIEW finance_test.kpi_weekly AS
 WITH weeks AS (
         SELECT w.report_week,
            w.week_start,
            w.week_end
           FROM finance.dim_week w
          WHERE (w.report_week IN ( SELECT DISTINCT budget_weekly.iso_week
                   FROM finance_test.budget_weekly
                  WHERE (budget_weekly.budget_year = 2025)))
        ), billed AS (
         SELECT w.report_week,
            count(i.invoice_number) AS invoices_billed,
            COALESCE(sum(i.billed_sdr), (0)::numeric) AS billed_sdr
           FROM (weeks w
             LEFT JOIN finance_test.invoices i ON (((i.invoice_date >= w.week_start) AND (i.invoice_date <= w.week_end))))
          GROUP BY w.report_week
        ), budget AS (
         SELECT budget_weekly.iso_week AS report_week,
            sum(budget_weekly.budget_sdr) AS budget_sdr
           FROM finance_test.budget_weekly
          WHERE (budget_weekly.budget_year = 2025)
          GROUP BY budget_weekly.iso_week
        ), prev AS (
         SELECT w.report_week,
                CASE
                    WHEN (w.report_week > 1) THEN COALESCE(sum(f.amount_sdr), (0)::numeric)
                    ELSE NULL::numeric
                END AS billed_prev_sdr
           FROM (weeks w
             LEFT JOIN finance.fact_invoice f ON (((f.invoice_date >= (w.week_start - 7)) AND (f.invoice_date <= (w.week_end - 7)))))
          GROUP BY w.report_week
        ), rolling AS (
         SELECT k_1.report_week,
            ((k_1.billed_13w_sdr - k_1.billed_sdr) + b_1.billed_sdr) AS billed_13w_sdr,
            ((k_1.budget_13w_sdr - k_1.budget_sdr) + bu_1.budget_sdr) AS budget_13w_sdr
           FROM ((finance.kpi_weekly k_1
             JOIN billed b_1 ON ((b_1.report_week = k_1.report_week)))
             JOIN budget bu_1 ON ((bu_1.report_week = k_1.report_week)))
        )
 SELECT k.report_week,
    k.iso_week_label,
    k.week_start,
    k.week_end,
    k.is_warmup,
    b.invoices_billed,
    round(b.billed_sdr, 2) AS billed_sdr,
    k.payments_received,
    k.collected_sdr,
    k.ar_invoices,
    k.ar_sdr,
    k.overdue_invoices,
    k.overdue_sdr,
    k.aging_current_sdr,
    k.aging_1_30_sdr,
    k.aging_31_60_sdr,
    k.aging_61_90_sdr,
    k.aging_90_plus_sdr,
    k.dso_window_days,
    k.dso_window_billed_sdr,
    k.dso_days,
    round(bu.budget_sdr, 2) AS budget_sdr,
    round((b.billed_sdr - bu.budget_sdr), 2) AS budget_variance_sdr,
    round((((100)::numeric * (b.billed_sdr - bu.budget_sdr)) / NULLIF(bu.budget_sdr, (0)::numeric)), 2) AS budget_variance_pct,
    k.top10_share_13w_pct,
    round((((100)::numeric * (b.billed_sdr - p.billed_prev_sdr)) / NULLIF(p.billed_prev_sdr, (0)::numeric)), 2) AS billed_wow_pct,
    k.collected_wow_pct,
    k.ar_wow_pct,
    k.overdue_wow_pct,
    k.dso_wow_days,
    k.roll_window_weeks,
    round(r.billed_13w_sdr, 2) AS billed_13w_sdr,
    round(r.budget_13w_sdr, 2) AS budget_13w_sdr,
    round((((100)::numeric * (r.billed_13w_sdr - r.budget_13w_sdr)) / NULLIF(r.budget_13w_sdr, (0)::numeric)), 2) AS budget_variance_13w_pct,
    k.dso_best_days,
    k.dso_delinquency_days,
    k.billed_wow_typical_pct,
    k.collected_wow_typical_pct,
    k.ar_wow_typical_pct,
    k.overdue_wow_typical_pct,
    k.overdue_new_sdr,
    k.overdue_paid_sdr,
    k.due_week_sdr,
    k.due_week_collected_sdr,
    k.due_week_collected_pct,
    k.ontime_13w_pct
   FROM ((((finance.kpi_weekly k
     JOIN billed b ON ((b.report_week = k.report_week)))
     JOIN budget bu ON ((bu.report_week = k.report_week)))
     JOIN prev p ON ((p.report_week = k.report_week)))
     JOIN rolling r ON ((r.report_week = k.report_week)));


--
-- Name: VIEW kpi_weekly; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON VIEW finance_test.kpi_weekly IS 'Twin of finance.kpi_weekly over the evaluation copy (Agents plan §5d, migration 017): billed and budget from the copy (planted errors and the budget miss); receivables, collections, DSO, the top-10 share and their WoW from the live view (the copy has no payments); billed WoW against the live previous week. Weeks 10, 23, 36, 49 only. Evaluation only; invisible to Power BI. Level 2, Finance.';


--
-- Name: COLUMN kpi_weekly.report_week; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.report_week IS 'ISO week of 2025 (a week of the evaluation copy)';


--
-- Name: COLUMN kpi_weekly.iso_week_label; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.iso_week_label IS 'As finance.kpi_weekly';


--
-- Name: COLUMN kpi_weekly.week_start; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.week_start IS 'As finance.kpi_weekly';


--
-- Name: COLUMN kpi_weekly.week_end; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.week_end IS 'As finance.kpi_weekly';


--
-- Name: COLUMN kpi_weekly.is_warmup; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.is_warmup IS 'As finance.kpi_weekly';


--
-- Name: COLUMN kpi_weekly.invoices_billed; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.invoices_billed IS 'Invoices of the copy dated in the week (a planted duplicate counts)';


--
-- Name: COLUMN kpi_weekly.billed_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.billed_sdr IS 'Billed in the week (SDR) as in finance_test.invoices, planted errors included';


--
-- Name: COLUMN kpi_weekly.payments_received; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.payments_received IS 'LIVE value (finance.kpi_weekly): the copy has no payments';


--
-- Name: COLUMN kpi_weekly.collected_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.collected_sdr IS 'LIVE value (finance.kpi_weekly): the copy has no payments';


--
-- Name: COLUMN kpi_weekly.ar_invoices; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.ar_invoices IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.ar_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.ar_sdr IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.overdue_invoices; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.overdue_invoices IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.overdue_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.overdue_sdr IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.aging_current_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.aging_current_sdr IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.aging_1_30_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.aging_1_30_sdr IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.aging_31_60_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.aging_31_60_sdr IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.aging_61_90_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.aging_61_90_sdr IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.aging_90_plus_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.aging_90_plus_sdr IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.dso_window_days; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.dso_window_days IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.dso_window_billed_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.dso_window_billed_sdr IS 'LIVE value (finance.kpi_weekly): the DSO base stays on the live invoices';


--
-- Name: COLUMN kpi_weekly.dso_days; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.dso_days IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.budget_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.budget_sdr IS 'Budget of the week (SDR) from finance_test.budget_weekly (week 36 carries the planted miss)';


--
-- Name: COLUMN kpi_weekly.budget_variance_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.budget_variance_sdr IS 'billed − budget (SDR), both from the copy';


--
-- Name: COLUMN kpi_weekly.budget_variance_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.budget_variance_pct IS '(billed − budget) / budget, percent, both from the copy';


--
-- Name: COLUMN kpi_weekly.top10_share_13w_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.top10_share_13w_pct IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.billed_wow_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.billed_wow_pct IS 'Billed of the copy vs billed of the LIVE previous week, percent';


--
-- Name: COLUMN kpi_weekly.collected_wow_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.collected_wow_pct IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.ar_wow_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.ar_wow_pct IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.overdue_wow_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.overdue_wow_pct IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.dso_wow_days; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.dso_wow_days IS 'LIVE value (finance.kpi_weekly)';


--
-- Name: COLUMN kpi_weekly.roll_window_weeks; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.roll_window_weeks IS 'LIVE value (finance.kpi_weekly, M9b)';


--
-- Name: COLUMN kpi_weekly.billed_13w_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.billed_13w_sdr IS 'Live 13-week billed with the report week replaced by the copy''s billed (planted errors included), M9b';


--
-- Name: COLUMN kpi_weekly.budget_13w_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.budget_13w_sdr IS 'Live 13-week budget with the report week replaced by the copy''s budget (week 36 carries the planted miss), M9b';


--
-- Name: COLUMN kpi_weekly.budget_variance_13w_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.budget_variance_13w_pct IS '(billed_13w − budget_13w) / budget_13w, percent, both as in this view';


--
-- Name: COLUMN kpi_weekly.dso_best_days; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.dso_best_days IS 'LIVE value (finance.kpi_weekly, M12)';


--
-- Name: COLUMN kpi_weekly.dso_delinquency_days; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.dso_delinquency_days IS 'LIVE value (finance.kpi_weekly, M12)';


--
-- Name: COLUMN kpi_weekly.billed_wow_typical_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.billed_wow_typical_pct IS 'LIVE value (finance.kpi_weekly, M13): the typical swing is the history of the live weeks';


--
-- Name: COLUMN kpi_weekly.collected_wow_typical_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.collected_wow_typical_pct IS 'LIVE value (finance.kpi_weekly, M13)';


--
-- Name: COLUMN kpi_weekly.ar_wow_typical_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.ar_wow_typical_pct IS 'LIVE value (finance.kpi_weekly, M13)';


--
-- Name: COLUMN kpi_weekly.overdue_wow_typical_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.overdue_wow_typical_pct IS 'LIVE value (finance.kpi_weekly, M13)';


--
-- Name: COLUMN kpi_weekly.overdue_new_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.overdue_new_sdr IS 'LIVE value (finance.kpi_weekly, M14)';


--
-- Name: COLUMN kpi_weekly.overdue_paid_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.overdue_paid_sdr IS 'LIVE value (finance.kpi_weekly, M14)';


--
-- Name: COLUMN kpi_weekly.due_week_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.due_week_sdr IS 'LIVE value (finance.kpi_weekly, M14)';


--
-- Name: COLUMN kpi_weekly.due_week_collected_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.due_week_collected_sdr IS 'LIVE value (finance.kpi_weekly, M14)';


--
-- Name: COLUMN kpi_weekly.due_week_collected_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.due_week_collected_pct IS 'LIVE value (finance.kpi_weekly, M14)';


--
-- Name: COLUMN kpi_weekly.ontime_13w_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly.ontime_13w_pct IS 'LIVE value (finance.kpi_weekly, M16)';


--
-- Name: kpi_traffic_link; Type: VIEW; Schema: finance_test; Owner: -
--

CREATE VIEW finance_test.kpi_traffic_link AS
 WITH t AS (
         SELECT ((floor((((suez_transits_daily.date - '2024-12-30'::date))::numeric / 7.0)))::integer + 1) AS week,
            sum(suez_transits_daily.n_total) AS transits
           FROM external.suez_transits_daily
          GROUP BY ((floor((((suez_transits_daily.date - '2024-12-30'::date))::numeric / 7.0)))::integer + 1)
        ), k AS (
         SELECT kw.report_week,
            COALESCE(tw.invoices_billed, kw.invoices_billed) AS invoices_billed,
            t0.transits AS transits_week,
            t1.transits AS transits_prev_week
           FROM (((finance.kpi_weekly kw
             LEFT JOIN finance_test.kpi_weekly tw ON ((tw.report_week = kw.report_week)))
             JOIN t t0 ON ((t0.week = kw.report_week)))
             JOIN t t1 ON ((t1.week = (kw.report_week - 1))))
        ), r AS (
         SELECT k.report_week,
            k.invoices_billed,
            k.transits_week,
            k.transits_prev_week,
            count(*) OVER w AS n_weeks,
            corr((k.invoices_billed)::double precision, (k.transits_week)::double precision) OVER w AS r0,
            corr((k.invoices_billed)::double precision, (k.transits_prev_week)::double precision) OVER w AS r1
           FROM k
          WINDOW w AS (ORDER BY k.report_week ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
        )
 SELECT report_week,
    invoices_billed,
    (transits_week)::integer AS suez_transits_week,
    (transits_prev_week)::integer AS suez_transits_prev_week,
    (n_weeks)::integer AS n_weeks,
        CASE
            WHEN (n_weeks >= 13) THEN round((r0)::numeric, 3)
            ELSE NULL::numeric
        END AS r_lag0,
        CASE
            WHEN (n_weeks >= 13) THEN round((r1)::numeric, 3)
            ELSE NULL::numeric
        END AS r_lag1,
        CASE
            WHEN (n_weeks >= 13) THEN round((((2)::double precision / sqrt((n_weeks)::double precision)))::numeric, 3)
            ELSE NULL::numeric
        END AS r_threshold,
        CASE
            WHEN (n_weeks < 13) THEN NULL::text
            WHEN ((abs(r0) >= ((2)::double precision / sqrt((n_weeks)::double precision))) OR (abs(r1) >= ((2)::double precision / sqrt((n_weeks)::double precision)))) THEN 'link'::text
            ELSE 'no_link'::text
        END AS link,
        CASE
            WHEN (n_weeks < 13) THEN NULL::integer
            WHEN ((abs(r0) >= ((2)::double precision / sqrt((n_weeks)::double precision))) AND (abs(r0) >= COALESCE(abs(r1), (0)::double precision))) THEN 0
            WHEN (abs(r1) >= ((2)::double precision / sqrt((n_weeks)::double precision))) THEN 1
            WHEN (abs(r0) >= ((2)::double precision / sqrt((n_weeks)::double precision))) THEN 0
            ELSE NULL::integer
        END AS link_lag
   FROM r;


--
-- Name: VIEW kpi_traffic_link; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON VIEW finance_test.kpi_traffic_link IS 'M17 on the evaluation copy: the live weeks with the 4 test weeks'' invoice counts from finance_test.kpi_weekly (the migration 017 pattern); otherwise the definition of finance.kpi_traffic_link (migration 027)';


--
-- Name: COLUMN kpi_traffic_link.report_week; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_traffic_link.report_week IS 'Report week 1-52 (ISO 2025)';


--
-- Name: COLUMN kpi_traffic_link.invoices_billed; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_traffic_link.invoices_billed IS 'Invoices issued in the week (kpi_weekly.invoices_billed of this schema)';


--
-- Name: COLUMN kpi_traffic_link.suez_transits_week; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_traffic_link.suez_transits_week IS 'Suez Canal transits Monday-Sunday of the week (external.suez_transits_daily, n_total)';


--
-- Name: COLUMN kpi_traffic_link.suez_transits_prev_week; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_traffic_link.suez_transits_prev_week IS 'Suez Canal transits of the week before (lag 1; week 0 = 2024-12-23 ... 29)';


--
-- Name: COLUMN kpi_traffic_link.n_weeks; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_traffic_link.n_weeks IS 'Weeks in the year-to-date window (= report_week)';


--
-- Name: COLUMN kpi_traffic_link.r_lag0; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_traffic_link.r_lag0 IS 'Pearson r, weeks 1..w: invoice count vs the same week''s transits (3 decimals; NULL before week 13)';


--
-- Name: COLUMN kpi_traffic_link.r_lag1; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_traffic_link.r_lag1 IS 'Pearson r, weeks 1..w: invoice count vs the previous week''s transits (3 decimals; NULL before week 13)';


--
-- Name: COLUMN kpi_traffic_link.r_threshold; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_traffic_link.r_threshold IS '2 / sqrt(n_weeks): about the 5 % two-sided level for one test; two lags double the false rate (3 decimals)';


--
-- Name: COLUMN kpi_traffic_link.link; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_traffic_link.link IS 'link when |r_lag0| or |r_lag1| >= r_threshold (unrounded), else no_link; NULL before week 13. Moves with, never caused by';


--
-- Name: COLUMN kpi_traffic_link.link_lag; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_traffic_link.link_lag IS 'The lag that passes (0 or 1; the larger |r| when both do); NULL when no_link or before week 13';


--
-- Name: kpi_weekly_category; Type: VIEW; Schema: finance_test; Owner: -
--

CREATE VIEW finance_test.kpi_weekly_category AS
 WITH weeks AS (
         SELECT w.report_week,
            w.week_start,
            w.week_end
           FROM finance.dim_week w
          WHERE (w.report_week IN ( SELECT DISTINCT budget_weekly.iso_week
                   FROM finance_test.budget_weekly
                  WHERE (budget_weekly.budget_year = 2025)))
        ), grid AS (
         SELECT w.report_week,
            w.week_start,
            w.week_end,
            b_1.vessel_category,
            b_1.budget_sdr
           FROM (weeks w
             JOIN finance_test.budget_weekly b_1 ON (((b_1.budget_year = 2025) AND (b_1.iso_week = w.report_week))))
        ), base AS (
         SELECT g.report_week,
            g.vessel_category,
            g.budget_sdr,
            count(i.invoice_number) AS invoices_billed,
            COALESCE(sum(i.billed_sdr), (0)::numeric) AS billed_sdr
           FROM (grid g
             LEFT JOIN (finance_test.invoices i
             JOIN public.vessels v ON ((v.vessel_id = i.vessel_id))) ON (((v.vessel_type = g.vessel_category) AND ((i.invoice_date >= g.week_start) AND (i.invoice_date <= g.week_end)))))
          GROUP BY g.report_week, g.vessel_category, g.budget_sdr
        ), prev AS (
         SELECT g.report_week,
            g.vessel_category,
                CASE
                    WHEN (g.report_week > 1) THEN COALESCE(sum(f.amount_sdr), (0)::numeric)
                    ELSE NULL::numeric
                END AS billed_prev_sdr
           FROM (grid g
             LEFT JOIN finance.fact_invoice f ON (((f.vessel_category = g.vessel_category) AND ((f.invoice_date >= (g.week_start - 7)) AND (f.invoice_date <= (g.week_end - 7))))))
          GROUP BY g.report_week, g.vessel_category
        )
 SELECT b.report_week,
    b.vessel_category,
    b.invoices_billed,
    round(b.billed_sdr, 2) AS billed_sdr,
    round(b.budget_sdr, 2) AS budget_sdr,
    round((b.billed_sdr - b.budget_sdr), 2) AS budget_variance_sdr,
    round((((100)::numeric * (b.billed_sdr - b.budget_sdr)) / NULLIF(b.budget_sdr, (0)::numeric)), 2) AS budget_variance_pct,
    round(p.billed_prev_sdr, 2) AS billed_prev_sdr,
    round((b.billed_sdr - p.billed_prev_sdr), 2) AS billed_wow_change_sdr,
    round((((100)::numeric * (b.billed_sdr - p.billed_prev_sdr)) / NULLIF(p.billed_prev_sdr, (0)::numeric)), 2) AS billed_wow_pct,
    lc.invoices_prev
   FROM ((base b
     JOIN prev p ON (((p.report_week = b.report_week) AND (p.vessel_category = b.vessel_category))))
     LEFT JOIN finance.kpi_weekly_category lc ON (((lc.report_week = b.report_week) AND (lc.vessel_category = b.vessel_category))));


--
-- Name: VIEW kpi_weekly_category; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON VIEW finance_test.kpi_weekly_category IS 'Twin of finance.kpi_weekly_category over the evaluation copy (Agents plan §5d, migration 017): billed from finance_test.invoices, budget from finance_test.budget_weekly (the planted budget miss), the previous week from the live invoices. Weeks 10, 23, 36, 49 only. Evaluation only; invisible to Power BI. Level 2, Finance.';


--
-- Name: COLUMN kpi_weekly_category.report_week; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly_category.report_week IS 'ISO week of 2025 (a week of the evaluation copy)';


--
-- Name: COLUMN kpi_weekly_category.vessel_category; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly_category.vessel_category IS 'Tariff category (vessels.vessel_type)';


--
-- Name: COLUMN kpi_weekly_category.invoices_billed; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly_category.invoices_billed IS 'Invoices of the copy dated in the week for the category (a planted duplicate counts)';


--
-- Name: COLUMN kpi_weekly_category.billed_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly_category.billed_sdr IS 'Billed in the week (SDR) as in finance_test.invoices, planted errors included';


--
-- Name: COLUMN kpi_weekly_category.budget_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly_category.budget_sdr IS 'Budget of the week (SDR) from finance_test.budget_weekly (one row planted: week 36)';


--
-- Name: COLUMN kpi_weekly_category.budget_variance_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly_category.budget_variance_sdr IS 'billed − budget (SDR)';


--
-- Name: COLUMN kpi_weekly_category.budget_variance_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly_category.budget_variance_pct IS '(billed − budget) / budget, percent';


--
-- Name: COLUMN kpi_weekly_category.billed_prev_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly_category.billed_prev_sdr IS 'Billed in the previous week (SDR) from the LIVE invoices (the copy holds no previous week)';


--
-- Name: COLUMN kpi_weekly_category.billed_wow_change_sdr; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly_category.billed_wow_change_sdr IS 'billed − billed_prev (SDR); the week''s drivers = the largest absolute changes';


--
-- Name: COLUMN kpi_weekly_category.billed_wow_pct; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly_category.billed_wow_pct IS 'Week-over-week change of billed, percent (NULL when the previous week billed 0)';


--
-- Name: COLUMN kpi_weekly_category.invoices_prev; Type: COMMENT; Schema: finance_test; Owner: -
--

COMMENT ON COLUMN finance_test.kpi_weekly_category.invoices_prev IS 'LIVE value (finance.kpi_weekly_category): invoices of the category in the previous week (the copy holds no previous week)';


--
-- Name: bunker_prices; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bunker_prices (
    fuel text NOT NULL,
    price_usd_per_t numeric NOT NULL,
    price_date date NOT NULL,
    price_source text NOT NULL,
    usd_per_sdr numeric NOT NULL,
    rate_date date NOT NULL,
    rate_source text NOT NULL,
    set_by text NOT NULL,
    CONSTRAINT bunker_prices_fuel_chk CHECK ((fuel = 'VLSFO'::text)),
    CONSTRAINT bunker_prices_positive_chk CHECK (((price_usd_per_t > (0)::numeric) AND (usd_per_sdr > (0)::numeric)))
);


--
-- Name: TABLE bunker_prices; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.bunker_prices IS 'Dated bunker price set by the owner with the dated USD-per-SDR rate beside it (Agents plan P9-3); money is reported in SDR (ADR-003); level 1 / Operations (migration 020)';


--
-- Name: COLUMN bunker_prices.fuel; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.bunker_prices.fuel IS 'fuel grade (VLSFO only)';


--
-- Name: COLUMN bunker_prices.price_usd_per_t; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.bunker_prices.price_usd_per_t IS 'price in US dollars per metric tonne';


--
-- Name: COLUMN bunker_prices.price_date; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.bunker_prices.price_date IS 'date the price was published';


--
-- Name: COLUMN bunker_prices.price_source; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.bunker_prices.price_source IS 'where the price was read (publication + URL)';


--
-- Name: COLUMN bunker_prices.usd_per_sdr; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.bunker_prices.usd_per_sdr IS 'US dollars per SDR on rate_date (IMF SDR valuation); SDR per tonne = price_usd_per_t / usd_per_sdr';


--
-- Name: COLUMN bunker_prices.rate_date; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.bunker_prices.rate_date IS 'date of the IMF rate';


--
-- Name: COLUMN bunker_prices.rate_source; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.bunker_prices.rate_source IS 'where the rate was read (publication + URL)';


--
-- Name: COLUMN bunker_prices.set_by; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.bunker_prices.set_by IS 'who set the row (the owner)';


--
-- Name: containers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.containers (
    container_id integer NOT NULL,
    container_number character varying(11) NOT NULL,
    container_type text NOT NULL,
    size_ft integer NOT NULL,
    status text NOT NULL,
    vessel_id integer NOT NULL,
    origin_locode character varying(5) NOT NULL,
    destination_locode character varying(5) NOT NULL,
    CONSTRAINT containers_number_format_chk CHECK (((container_number)::text ~ '^[A-Z]{3}[UJZ][0-9]{7}$'::text)),
    CONSTRAINT containers_route_chk CHECK (((origin_locode)::text <> (destination_locode)::text)),
    CONSTRAINT containers_size_ft_chk CHECK ((size_ft = ANY (ARRAY[20, 40]))),
    CONSTRAINT containers_status_chk CHECK ((status = ANY (ARRAY['Loaded'::text, 'In Transit'::text, 'At Port'::text, 'Delivered'::text, 'Empty'::text]))),
    CONSTRAINT containers_type_chk CHECK ((container_type = ANY (ARRAY['Dry'::text, 'Reefer'::text, 'Open Top'::text, 'Flat Rack'::text])))
);


--
-- Name: TABLE containers; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.containers IS 'Synthetic containers (1,000) carried by the vessels; same origin / destination as their vessel. Level 1, Operations.';


--
-- Name: COLUMN containers.container_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.containers.container_id IS 'Surrogate key';


--
-- Name: COLUMN containers.container_number; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.containers.container_number IS 'Container number in ISO 6346 form (synthetic, sequential; the check digit is not enforced)';


--
-- Name: COLUMN containers.container_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.containers.container_type IS 'Dry, Reefer, Open Top or Flat Rack';


--
-- Name: COLUMN containers.size_ft; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.containers.size_ft IS 'Length in feet: 20 or 40';


--
-- Name: COLUMN containers.status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.containers.status IS 'Loaded, In Transit, At Port, Delivered or Empty';


--
-- Name: COLUMN containers.vessel_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.containers.vessel_id IS 'Carrying vessel';


--
-- Name: COLUMN containers.origin_locode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.containers.origin_locode IS 'Port of loading (UN/LOCODE)';


--
-- Name: COLUMN containers.destination_locode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.containers.destination_locode IS 'Port of discharge (UN/LOCODE)';


--
-- Name: containers_container_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.containers_container_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: containers_container_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.containers_container_id_seq OWNED BY public.containers.container_id;


--
-- Name: departments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.departments (
    department_id integer NOT NULL,
    department_name text NOT NULL,
    description text
);


--
-- Name: TABLE departments; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.departments IS 'NileGate departments (Operations, Customs, Finance, HR, IT). Level 1, HR.';


--
-- Name: COLUMN departments.department_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.departments.department_id IS 'Surrogate key; owner department of every protected resource (ADR-006)';


--
-- Name: COLUMN departments.department_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.departments.department_name IS 'Unique department name';


--
-- Name: COLUMN departments.description; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.departments.description IS 'Optional description';


--
-- Name: departments_department_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.departments_department_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: departments_department_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.departments_department_id_seq OWNED BY public.departments.department_id;


--
-- Name: documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documents (
    document_id text NOT NULL,
    filename text NOT NULL,
    title text NOT NULL,
    source text NOT NULL,
    real_or_synthetic text NOT NULL,
    document_type text NOT NULL,
    department_id integer NOT NULL,
    sensitivity_level smallint NOT NULL,
    version_date text,
    ingestion_scope text,
    source_url text,
    sha256 character(64) NOT NULL,
    file_size_bytes bigint NOT NULL,
    page_count integer,
    chunk_count integer,
    ingested_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT documents_chunk_count_check CHECK ((chunk_count >= 0)),
    CONSTRAINT documents_file_size_bytes_check CHECK ((file_size_bytes > 0)),
    CONSTRAINT documents_page_count_check CHECK ((page_count > 0)),
    CONSTRAINT documents_real_or_synthetic_check CHECK ((real_or_synthetic = ANY (ARRAY['real'::text, 'synthetic'::text]))),
    CONSTRAINT documents_sensitivity_level_check CHECK (((sensitivity_level >= 1) AND (sensitivity_level <= 3)))
);


--
-- Name: TABLE documents; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.documents IS 'RAG document registry and lineage, one row per ingested source file (ADR-009); filled in the RAG phase. Level 1, IT.';


--
-- Name: COLUMN documents.document_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.document_id IS 'Stable slug of the source, e.g. lpi_methodology; carried in every Qdrant payload';


--
-- Name: COLUMN documents.filename; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.filename IS 'File name under Data/raw/...';


--
-- Name: COLUMN documents.title; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.title IS 'Document title';


--
-- Name: COLUMN documents.source; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.source IS 'Publisher, e.g. The World Bank';


--
-- Name: COLUMN documents.real_or_synthetic; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.real_or_synthetic IS 'real or synthetic';


--
-- Name: COLUMN documents.document_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.document_type IS 'Same values as the chunk column document_type';


--
-- Name: COLUMN documents.department_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.department_id IS 'Owner department (default; a chunk may differ, ADR-021)';


--
-- Name: COLUMN documents.sensitivity_level; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.sensitivity_level IS 'Default level 1-3; a chunk may be higher (ADR-021)';


--
-- Name: COLUMN documents.version_date; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.version_date IS 'As published; precision varies by source';


--
-- Name: COLUMN documents.ingestion_scope; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.ingestion_scope IS 'Part of the document ingested; NULL = whole document';


--
-- Name: COLUMN documents.source_url; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.source_url IS 'Where the document was obtained';


--
-- Name: COLUMN documents.sha256; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.sha256 IS 'Fingerprint of the raw file (change detection); a new version = a new row';


--
-- Name: COLUMN documents.file_size_bytes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.file_size_bytes IS 'Raw file size';


--
-- Name: COLUMN documents.page_count; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.page_count IS 'Pages of the raw file';


--
-- Name: COLUMN documents.chunk_count; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.chunk_count IS 'Chunks produced; NULL until chunked';


--
-- Name: COLUMN documents.ingested_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.ingested_at IS 'When loaded into Qdrant; NULL until then';


--
-- Name: COLUMN documents.created_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.documents.created_at IS 'Row creation time';


--
-- Name: employees; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.employees (
    employee_id integer NOT NULL,
    first_name text NOT NULL,
    last_name text NOT NULL,
    email text NOT NULL,
    role_id integer NOT NULL,
    department_id integer NOT NULL,
    hire_date date NOT NULL,
    CONSTRAINT employees_email_format_chk CHECK ((email ~ '^[a-z0-9._-]+@nilegate\.com$'::text))
);


--
-- Name: TABLE employees; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.employees IS 'Synthetic employees (Faker, seed 42). Contains personal data. Level 2, HR (ADR-006); no status column (ADR-017).';


--
-- Name: COLUMN employees.employee_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employees.employee_id IS 'Surrogate key';


--
-- Name: COLUMN employees.first_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employees.first_name IS 'First name (synthetic)';


--
-- Name: COLUMN employees.last_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employees.last_name IS 'Last name (synthetic)';


--
-- Name: COLUMN employees.email; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employees.email IS 'Unique @nilegate.com address';


--
-- Name: COLUMN employees.role_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employees.role_id IS 'Role (roles.role_id): sensitivity ceiling';


--
-- Name: COLUMN employees.department_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employees.department_id IS 'Department (departments.department_id): department grant';


--
-- Name: COLUMN employees.hire_date; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.employees.hire_date IS 'Hire date (anchored to 2026-09-13)';


--
-- Name: employees_employee_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.employees_employee_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: employees_employee_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.employees_employee_id_seq OWNED BY public.employees.employee_id;


--
-- Name: invoices_invoice_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invoices_invoice_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invoices_invoice_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invoices_invoice_id_seq OWNED BY public.invoices.invoice_id;


--
-- Name: port_call_messages; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.port_call_messages (
    message_id text NOT NULL,
    vessel_id integer NOT NULL,
    voyage_no text NOT NULL,
    port_locode character varying(5) NOT NULL,
    time_type text NOT NULL,
    location text NOT NULL,
    requested_time timestamp with time zone NOT NULL,
    sent_at timestamp with time zone NOT NULL,
    message_status text NOT NULL,
    sender text NOT NULL,
    real_or_synthetic text NOT NULL,
    source text NOT NULL,
    CONSTRAINT port_call_messages_location_chk CHECK ((location = ANY (ARRAY['berth'::text, 'pilot_boarding_place'::text]))),
    CONSTRAINT port_call_messages_order_chk CHECK ((sent_at < requested_time)),
    CONSTRAINT port_call_messages_origin_chk CHECK ((real_or_synthetic = ANY (ARRAY['real'::text, 'synthetic'::text]))),
    CONSTRAINT port_call_messages_sender_chk CHECK ((sender = ANY (ARRAY['port'::text, 'agent'::text, 'terminal'::text]))),
    CONSTRAINT port_call_messages_status_chk CHECK ((message_status = ANY (ARRAY['requested'::text, 'cancelled'::text]))),
    CONSTRAINT port_call_messages_time_type_chk CHECK ((time_type = 'RTA'::text))
);


--
-- Name: TABLE port_call_messages; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.port_call_messages IS 'Port-call messages: the Requested Time of Arrival (RTA) a port or agent sends a vessel; the RTA known at a clock = the latest message with sent_at <= the clock for the port call (JIT arrival plan D-J1); level 1 / Operations (migration 030)';


--
-- Name: COLUMN port_call_messages.message_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_call_messages.message_id IS 'the message identifier (synthetic: PCM-<vessel>-<voyage>-<n>)';


--
-- Name: COLUMN port_call_messages.vessel_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_call_messages.vessel_id IS 'the vessel the message is for (FK vessels)';


--
-- Name: COLUMN port_call_messages.voyage_no; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_call_messages.voyage_no IS 'the voyage number of the port call (the voyage file''s voyage_no)';


--
-- Name: COLUMN port_call_messages.port_locode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_call_messages.port_locode IS 'the port of the call, UN/LOCODE (FK ports)';


--
-- Name: COLUMN port_call_messages.time_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_call_messages.time_type IS 'RTA = Requested Time of Arrival (IMO JIT Arrival Guide)';


--
-- Name: COLUMN port_call_messages.location; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_call_messages.location IS 'where the requested time applies: berth (all fast) or pilot_boarding_place';


--
-- Name: COLUMN port_call_messages.requested_time; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_call_messages.requested_time IS 'the requested time of arrival at the location, UTC';


--
-- Name: COLUMN port_call_messages.sent_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_call_messages.sent_at IS 'when the message was sent, UTC: a tool at clock t reads only messages with sent_at <= t';


--
-- Name: COLUMN port_call_messages.message_status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_call_messages.message_status IS 'requested, or cancelled (the call has no RTA from then on)';


--
-- Name: COLUMN port_call_messages.sender; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_call_messages.sender IS 'port, agent or terminal';


--
-- Name: COLUMN port_call_messages.real_or_synthetic; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_call_messages.real_or_synthetic IS 'real (a received message) or synthetic (the generator)';


--
-- Name: COLUMN port_call_messages.source; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_call_messages.source IS 'where the row comes from (feed, file or generator)';


--
-- Name: port_connections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.port_connections (
    port1_locode character varying(5) NOT NULL,
    port2_locode character varying(5) NOT NULL,
    flows double precision NOT NULL,
    country1 text NOT NULL,
    country2 text NOT NULL,
    geom public.geometry(LineString,4326) NOT NULL,
    CONSTRAINT port_connections_country_codes_chk CHECK (((country1 = "left"((port1_locode)::text, 2)) AND (country2 = "left"((port2_locode)::text, 2)))),
    CONSTRAINT port_connections_flows_chk CHECK ((flows > (0)::double precision)),
    CONSTRAINT port_connections_no_self_loop_chk CHECK (((port1_locode)::text <> (port2_locode)::text))
);


--
-- Name: TABLE port_connections; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.port_connections IS 'Real port-to-port network with flows (port_flows shapefile). Both directions present. Level 1, Operations.';


--
-- Name: COLUMN port_connections.port1_locode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_connections.port1_locode IS 'From port (UN/LOCODE)';


--
-- Name: COLUMN port_connections.port2_locode; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_connections.port2_locode IS 'To port (UN/LOCODE)';


--
-- Name: COLUMN port_connections.flows; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_connections.flows IS 'Flow volume between the two ports (> 0)';


--
-- Name: COLUMN port_connections.country1; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_connections.country1 IS 'ISO 3166-1 alpha-2 country code of port1 (= left(port1_locode, 2))';


--
-- Name: COLUMN port_connections.country2; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_connections.country2 IS 'ISO 3166-1 alpha-2 country code of port2 (= left(port2_locode, 2))';


--
-- Name: COLUMN port_connections.geom; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.port_connections.geom IS 'Straight 2-point LineString from port1 to port2, SRID 4326 (not a sea lane)';


--
-- Name: roles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roles (
    role_id integer NOT NULL,
    role_name text NOT NULL,
    allowed_sensitivity_level integer NOT NULL,
    CONSTRAINT roles_allowed_sensitivity_level_chk CHECK (((allowed_sensitivity_level >= 1) AND (allowed_sensitivity_level <= 3)))
);


--
-- Name: TABLE roles; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.roles IS 'Roles and their sensitivity ceiling: employee 1, manager 2, ceo 3 (ADR-006). Level 2, IT.';


--
-- Name: COLUMN roles.role_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.roles.role_id IS 'Surrogate key';


--
-- Name: COLUMN roles.role_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.roles.role_name IS 'employee, manager or ceo';


--
-- Name: COLUMN roles.allowed_sensitivity_level; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.roles.allowed_sensitivity_level IS 'Highest sensitivity level the role may read (1-3)';


--
-- Name: roles_role_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.roles_role_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: roles_role_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.roles_role_id_seq OWNED BY public.roles.role_id;


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    version smallint NOT NULL,
    filename text NOT NULL,
    sha256 character(64),
    applied_at timestamp with time zone DEFAULT now() NOT NULL,
    applied_by text DEFAULT CURRENT_USER NOT NULL,
    note text,
    CONSTRAINT schema_migrations_filename_check CHECK (((filename ~ '^[0-9]{3}_[a-z0-9_]+\.sql$'::text) AND (("left"(filename, 3))::smallint = version))),
    CONSTRAINT schema_migrations_sha256_check CHECK (((sha256 IS NULL) OR (sha256 ~ '^[0-9a-f]{64}$'::text))),
    CONSTRAINT schema_migrations_version_check CHECK ((version > 0))
);


--
-- Name: TABLE schema_migrations; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.schema_migrations IS 'One row per db/migrations file applied to this database (migration 031, ADR-071): written by Migrate.py apply; 001-030 recorded by 031 itself. The deploy reads it to find pending files.';


--
-- Name: COLUMN schema_migrations.version; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.schema_migrations.version IS 'The migration number, the first three digits of the file name.';


--
-- Name: COLUMN schema_migrations.filename; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.schema_migrations.filename IS 'The file name in db/migrations/.';


--
-- Name: COLUMN schema_migrations.sha256; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.schema_migrations.sha256 IS 'sha256 of the file text with CRLF read as LF; NULL only for 031 until Migrate.py records it.';


--
-- Name: COLUMN schema_migrations.applied_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.schema_migrations.applied_at IS 'When the migration was applied or, for 001-030, recorded.';


--
-- Name: COLUMN schema_migrations.applied_by; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.schema_migrations.applied_by IS 'The database login that applied or recorded it.';


--
-- Name: COLUMN schema_migrations.note; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.schema_migrations.note IS 'How it was applied (by hand before 031, by Migrate.py after).';


--
-- Name: toll_rate_bands_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.toll_rate_bands_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: toll_rate_bands_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.toll_rate_bands_id_seq OWNED BY public.toll_rate_bands.id;


--
-- Name: vessel_performance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vessel_performance (
    vessel_type text NOT NULL,
    size_band smallint NOT NULL,
    scnt_min numeric NOT NULL,
    scnt_max numeric,
    imo_ship_type text NOT NULL,
    imo_size_bin text NOT NULL,
    imo_size_unit text NOT NULL,
    imo_days_at_sea numeric NOT NULL,
    imo_main_kt numeric NOT NULL,
    imo_aux_kt numeric NOT NULL,
    ref_speed_kn numeric NOT NULL,
    main_t_per_day numeric NOT NULL,
    aux_t_per_day numeric NOT NULL,
    source text NOT NULL,
    source_ref text NOT NULL,
    CONSTRAINT vessel_performance_open_band_chk CHECK (((scnt_max IS NULL) = (size_band = 3))),
    CONSTRAINT vessel_performance_positive_chk CHECK (((imo_days_at_sea > (0)::numeric) AND (imo_days_at_sea <= (365)::numeric) AND (imo_main_kt > (0)::numeric) AND (imo_aux_kt >= (0)::numeric) AND (ref_speed_kn > (0)::numeric) AND (main_t_per_day > (0)::numeric) AND (aux_t_per_day >= (0)::numeric))),
    CONSTRAINT vessel_performance_scnt_chk CHECK (((scnt_min >= (0)::numeric) AND ((scnt_max IS NULL) OR (scnt_max > scnt_min)))),
    CONSTRAINT vessel_performance_size_band_chk CHECK (((size_band >= 1) AND (size_band <= 3))),
    CONSTRAINT vessel_performance_unit_chk CHECK ((imo_size_unit = ANY (ARRAY['dwt'::text, 'teu'::text, 'cbm'::text, 'gt'::text]))),
    CONSTRAINT vessel_performance_vessel_type_chk CHECK ((vessel_type = ANY (ARRAY['Chemical Tankers & Other Liquid Bulk Tankers'::text, 'Containerships'::text, 'Crude Oil Tankers'::text, 'Cruise Ships'::text, 'Dry Bulk Vessels'::text, 'General Cargo / Multi-Purpose / Heavy Lift Vessels'::text, 'Liquefied Natural Gas (LNG) Carriers'::text, 'Liquefied Petroleum Gas (LPG) Carriers'::text, 'Other Vessels'::text, 'Petroleum Product Tankers'::text, 'Roll-On/Roll-Off (Ro/Ro) Vessels'::text, 'Special Floating Units'::text, 'Vehicles Carriers'::text])))
);


--
-- Name: TABLE vessel_performance; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.vessel_performance IS 'Fuel and speed parameters per tariff vessel category and SCNT size band (Fourth IMO GHG Study 2020, Table 35, 2018 fleet), read by the Stage 2 tool vessel_params; level 1 / Operations (migration 020)';


--
-- Name: COLUMN vessel_performance.vessel_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.vessel_type IS 'tariff vessel category (the 13 values of vessels.vessel_type, ADR-033)';


--
-- Name: COLUMN vessel_performance.size_band; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.size_band IS '1 small / 2 medium / 3 large: tertiles of our vessels'' SCNT in the category';


--
-- Name: COLUMN vessel_performance.scnt_min; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.scnt_min IS 'band lower bound in SCNT tons (inclusive; band 1 starts at 0)';


--
-- Name: COLUMN vessel_performance.scnt_max; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.scnt_max IS 'band upper bound in SCNT tons (exclusive); NULL for the open band 3';


--
-- Name: COLUMN vessel_performance.imo_ship_type; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.imo_ship_type IS 'IMO ship type the band is mapped to (rank mapping; SCNT is not convertible to dwt / TEU / cbm)';


--
-- Name: COLUMN vessel_performance.imo_size_bin; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.imo_size_bin IS 'IMO size bin of that ship type (in imo_size_unit)';


--
-- Name: COLUMN vessel_performance.imo_size_unit; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.imo_size_unit IS 'unit of the IMO size bin: dwt, teu, cbm or gt';


--
-- Name: COLUMN vessel_performance.imo_days_at_sea; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.imo_days_at_sea IS 'IMO: average days at sea per year (2018)';


--
-- Name: COLUMN vessel_performance.imo_main_kt; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.imo_main_kt IS 'IMO: average main-engine fuel consumption per vessel per year, thousand tonnes';


--
-- Name: COLUMN vessel_performance.imo_aux_kt; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.imo_aux_kt IS 'IMO: average auxiliary-engine fuel consumption per vessel per year, thousand tonnes';


--
-- Name: COLUMN vessel_performance.ref_speed_kn; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.ref_speed_kn IS 'IMO: average speed over ground at sea, knots — the speed main_t_per_day belongs to';


--
-- Name: COLUMN vessel_performance.main_t_per_day; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.main_t_per_day IS 'main-engine tonnes per sea day at ref_speed_kn = imo_main_kt × 1000 / imo_days_at_sea; scaled by (speed / ref_speed_kn)³';


--
-- Name: COLUMN vessel_performance.aux_t_per_day; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.aux_t_per_day IS 'auxiliary tonnes per day = imo_aux_kt × 1000 / 365; independent of speed';


--
-- Name: COLUMN vessel_performance.source; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.source IS 'publication the IMO figures come from';


--
-- Name: COLUMN vessel_performance.source_ref; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.vessel_performance.source_ref IS 'IMO ship type, size bin and printed page of Table 35';


--
-- Name: vessels_vessel_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vessels_vessel_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vessels_vessel_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vessels_vessel_id_seq OWNED BY public.vessels.vessel_id;


--
-- Name: containers container_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.containers ALTER COLUMN container_id SET DEFAULT nextval('public.containers_container_id_seq'::regclass);


--
-- Name: departments department_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments ALTER COLUMN department_id SET DEFAULT nextval('public.departments_department_id_seq'::regclass);


--
-- Name: employees employee_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees ALTER COLUMN employee_id SET DEFAULT nextval('public.employees_employee_id_seq'::regclass);


--
-- Name: invoices invoice_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices ALTER COLUMN invoice_id SET DEFAULT nextval('public.invoices_invoice_id_seq'::regclass);


--
-- Name: roles role_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles ALTER COLUMN role_id SET DEFAULT nextval('public.roles_role_id_seq'::regclass);


--
-- Name: toll_rate_bands id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.toll_rate_bands ALTER COLUMN id SET DEFAULT nextval('public.toll_rate_bands_id_seq'::regclass);


--
-- Name: vessels vessel_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vessels ALTER COLUMN vessel_id SET DEFAULT nextval('public.vessels_vessel_id_seq'::regclass);


--
-- Name: checkpoint_blobs checkpoint_blobs_pkey; Type: CONSTRAINT; Schema: agent_state; Owner: -
--

ALTER TABLE ONLY agent_state.checkpoint_blobs
    ADD CONSTRAINT checkpoint_blobs_pkey PRIMARY KEY (thread_id, checkpoint_ns, channel, version);


--
-- Name: checkpoint_migrations checkpoint_migrations_pkey; Type: CONSTRAINT; Schema: agent_state; Owner: -
--

ALTER TABLE ONLY agent_state.checkpoint_migrations
    ADD CONSTRAINT checkpoint_migrations_pkey PRIMARY KEY (v);


--
-- Name: checkpoint_writes checkpoint_writes_pkey; Type: CONSTRAINT; Schema: agent_state; Owner: -
--

ALTER TABLE ONLY agent_state.checkpoint_writes
    ADD CONSTRAINT checkpoint_writes_pkey PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx);


--
-- Name: checkpoints checkpoints_pkey; Type: CONSTRAINT; Schema: agent_state; Owner: -
--

ALTER TABLE ONLY agent_state.checkpoints
    ADD CONSTRAINT checkpoints_pkey PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id);


--
-- Name: llm_daily_usage llm_daily_usage_pkey; Type: CONSTRAINT; Schema: agent_state; Owner: -
--

ALTER TABLE ONLY agent_state.llm_daily_usage
    ADD CONSTRAINT llm_daily_usage_pkey PRIMARY KEY (scope, provider_day);


--
-- Name: llm_minute_usage llm_minute_usage_pkey; Type: CONSTRAINT; Schema: agent_state; Owner: -
--

ALTER TABLE ONLY agent_state.llm_minute_usage
    ADD CONSTRAINT llm_minute_usage_pkey PRIMARY KEY (scope, minute);


--
-- Name: pack_approved pack_approved_pkey; Type: CONSTRAINT; Schema: agent_state; Owner: -
--

ALTER TABLE ONLY agent_state.pack_approved
    ADD CONSTRAINT pack_approved_pkey PRIMARY KEY (report_week);


--
-- Name: pack_approved_summary pack_approved_summary_pkey; Type: CONSTRAINT; Schema: agent_state; Owner: -
--

ALTER TABLE ONLY agent_state.pack_approved_summary
    ADD CONSTRAINT pack_approved_summary_pkey PRIMARY KEY (report_week, idx);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: api; Owner: -
--

ALTER TABLE ONLY api.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: conversation_turns conversation_turns_pkey; Type: CONSTRAINT; Schema: api; Owner: -
--

ALTER TABLE ONLY api.conversation_turns
    ADD CONSTRAINT conversation_turns_pkey PRIMARY KEY (conversation_id, turn_no);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: api; Owner: -
--

ALTER TABLE ONLY api.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (conversation_id);


--
-- Name: logins logins_pkey; Type: CONSTRAINT; Schema: api; Owner: -
--

ALTER TABLE ONLY api.logins
    ADD CONSTRAINT logins_pkey PRIMARY KEY (employee_id);


--
-- Name: tokens tokens_pkey; Type: CONSTRAINT; Schema: api; Owner: -
--

ALTER TABLE ONLY api.tokens
    ADD CONSTRAINT tokens_pkey PRIMARY KEY (token_sha256);


--
-- Name: suez_transits_daily suez_transits_daily_pkey; Type: CONSTRAINT; Schema: external; Owner: -
--

ALTER TABLE ONLY external.suez_transits_daily
    ADD CONSTRAINT suez_transits_daily_pkey PRIMARY KEY (date);


--
-- Name: invoices invoices_invoice_number_key; Type: CONSTRAINT; Schema: finance_scenario; Owner: -
--

ALTER TABLE ONLY finance_scenario.invoices
    ADD CONSTRAINT invoices_invoice_number_key UNIQUE (invoice_number);


--
-- Name: invoices invoices_pkey; Type: CONSTRAINT; Schema: finance_scenario; Owner: -
--

ALTER TABLE ONLY finance_scenario.invoices
    ADD CONSTRAINT invoices_pkey PRIMARY KEY (invoice_id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: finance_scenario; Owner: -
--

ALTER TABLE ONLY finance_scenario.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (invoice_number);


--
-- Name: budget_weekly budget_weekly_pkey; Type: CONSTRAINT; Schema: finance_test; Owner: -
--

ALTER TABLE ONLY finance_test.budget_weekly
    ADD CONSTRAINT budget_weekly_pkey PRIMARY KEY (budget_year, iso_week, vessel_category);


--
-- Name: invoices invoices_pkey; Type: CONSTRAINT; Schema: finance_test; Owner: -
--

ALTER TABLE ONLY finance_test.invoices
    ADD CONSTRAINT invoices_pkey PRIMARY KEY (invoice_number);


--
-- Name: budget_weekly budget_weekly_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.budget_weekly
    ADD CONSTRAINT budget_weekly_pkey PRIMARY KEY (budget_year, iso_week, vessel_category);


--
-- Name: bunker_prices bunker_prices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bunker_prices
    ADD CONSTRAINT bunker_prices_pkey PRIMARY KEY (fuel, price_date);


--
-- Name: containers containers_container_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.containers
    ADD CONSTRAINT containers_container_number_key UNIQUE (container_number);


--
-- Name: containers containers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.containers
    ADD CONSTRAINT containers_pkey PRIMARY KEY (container_id);


--
-- Name: customers customers_customer_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_customer_name_key UNIQUE (customer_name);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (customer_id);


--
-- Name: departments departments_department_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_department_name_key UNIQUE (department_name);


--
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (department_id);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (document_id);


--
-- Name: documents documents_sha256_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_sha256_key UNIQUE (sha256);


--
-- Name: employees employees_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_email_key UNIQUE (email);


--
-- Name: employees employees_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_pkey PRIMARY KEY (employee_id);


--
-- Name: invoices invoices_invoice_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_invoice_number_key UNIQUE (invoice_number);


--
-- Name: invoices invoices_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_pkey PRIMARY KEY (invoice_id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (invoice_number);


--
-- Name: port_call_messages port_call_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.port_call_messages
    ADD CONSTRAINT port_call_messages_pkey PRIMARY KEY (message_id);


--
-- Name: port_connections port_connections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.port_connections
    ADD CONSTRAINT port_connections_pkey PRIMARY KEY (port1_locode, port2_locode);


--
-- Name: ports ports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ports
    ADD CONSTRAINT ports_pkey PRIMARY KEY (locode);


--
-- Name: roles roles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_pkey PRIMARY KEY (role_id);


--
-- Name: roles roles_role_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roles
    ADD CONSTRAINT roles_role_name_key UNIQUE (role_name);


--
-- Name: schema_migrations schema_migrations_filename_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_filename_key UNIQUE (filename);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (version);


--
-- Name: toll_rate_bands toll_rate_bands_band_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.toll_rate_bands
    ADD CONSTRAINT toll_rate_bands_band_key UNIQUE (vessel_category, laden_ballast, band_order);


--
-- Name: toll_rate_bands toll_rate_bands_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.toll_rate_bands
    ADD CONSTRAINT toll_rate_bands_pkey PRIMARY KEY (id);


--
-- Name: vessel_performance vessel_performance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vessel_performance
    ADD CONSTRAINT vessel_performance_pkey PRIMARY KEY (vessel_type, size_band);


--
-- Name: vessels vessels_imo_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vessels
    ADD CONSTRAINT vessels_imo_number_key UNIQUE (imo_number);


--
-- Name: vessels vessels_mmsi_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vessels
    ADD CONSTRAINT vessels_mmsi_key UNIQUE (mmsi);


--
-- Name: vessels vessels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vessels
    ADD CONSTRAINT vessels_pkey PRIMARY KEY (vessel_id);


--
-- Name: checkpoint_blobs_thread_id_idx; Type: INDEX; Schema: agent_state; Owner: -
--

CREATE INDEX checkpoint_blobs_thread_id_idx ON agent_state.checkpoint_blobs USING btree (thread_id);


--
-- Name: checkpoint_writes_thread_id_idx; Type: INDEX; Schema: agent_state; Owner: -
--

CREATE INDEX checkpoint_writes_thread_id_idx ON agent_state.checkpoint_writes USING btree (thread_id);


--
-- Name: checkpoints_thread_id_idx; Type: INDEX; Schema: agent_state; Owner: -
--

CREATE INDEX checkpoints_thread_id_idx ON agent_state.checkpoints USING btree (thread_id);


--
-- Name: audit_log_at_idx; Type: INDEX; Schema: api; Owner: -
--

CREATE INDEX audit_log_at_idx ON api.audit_log USING btree (at);


--
-- Name: audit_log_employee_at_idx; Type: INDEX; Schema: api; Owner: -
--

CREATE INDEX audit_log_employee_at_idx ON api.audit_log USING btree (employee_id, at);


--
-- Name: conversations_employee_id_idx; Type: INDEX; Schema: api; Owner: -
--

CREATE INDEX conversations_employee_id_idx ON api.conversations USING btree (employee_id);


--
-- Name: tokens_employee_id_idx; Type: INDEX; Schema: api; Owner: -
--

CREATE INDEX tokens_employee_id_idx ON api.tokens USING btree (employee_id);


--
-- Name: test_invoices_vessel_id_idx; Type: INDEX; Schema: finance_test; Owner: -
--

CREATE INDEX test_invoices_vessel_id_idx ON finance_test.invoices USING btree (vessel_id);


--
-- Name: containers_destination_locode_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX containers_destination_locode_idx ON public.containers USING btree (destination_locode);


--
-- Name: containers_origin_locode_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX containers_origin_locode_idx ON public.containers USING btree (origin_locode);


--
-- Name: containers_vessel_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX containers_vessel_id_idx ON public.containers USING btree (vessel_id);


--
-- Name: documents_department_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX documents_department_id_idx ON public.documents USING btree (department_id);


--
-- Name: employees_department_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX employees_department_id_idx ON public.employees USING btree (department_id);


--
-- Name: employees_role_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX employees_role_id_idx ON public.employees USING btree (role_id);


--
-- Name: invoices_toll_rate_band_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX invoices_toll_rate_band_id_idx ON public.invoices USING btree (toll_rate_band_id);


--
-- Name: invoices_vessel_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX invoices_vessel_id_idx ON public.invoices USING btree (vessel_id);


--
-- Name: port_call_messages_call_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX port_call_messages_call_idx ON public.port_call_messages USING btree (vessel_id, port_locode, voyage_no, sent_at DESC);


--
-- Name: port_connections_geom_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX port_connections_geom_gist ON public.port_connections USING gist (geom);


--
-- Name: port_connections_port2_locode_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX port_connections_port2_locode_idx ON public.port_connections USING btree (port2_locode);


--
-- Name: ports_geom_gist; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ports_geom_gist ON public.ports USING gist (geom);


--
-- Name: vessels_customer_id_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vessels_customer_id_idx ON public.vessels USING btree (customer_id);


--
-- Name: vessels_destination_locode_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vessels_destination_locode_idx ON public.vessels USING btree (destination_locode);


--
-- Name: vessels_origin_locode_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX vessels_origin_locode_idx ON public.vessels USING btree (origin_locode);


--
-- Name: pack_approved_summary pack_approved_summary_report_week_fkey; Type: FK CONSTRAINT; Schema: agent_state; Owner: -
--

ALTER TABLE ONLY agent_state.pack_approved_summary
    ADD CONSTRAINT pack_approved_summary_report_week_fkey FOREIGN KEY (report_week) REFERENCES agent_state.pack_approved(report_week) ON DELETE CASCADE;


--
-- Name: conversation_turns conversation_turns_conversation_id_fkey; Type: FK CONSTRAINT; Schema: api; Owner: -
--

ALTER TABLE ONLY api.conversation_turns
    ADD CONSTRAINT conversation_turns_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES api.conversations(conversation_id) ON DELETE CASCADE;


--
-- Name: conversations conversations_employee_id_fkey; Type: FK CONSTRAINT; Schema: api; Owner: -
--

ALTER TABLE ONLY api.conversations
    ADD CONSTRAINT conversations_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES api.logins(employee_id);


--
-- Name: logins logins_employee_id_fkey; Type: FK CONSTRAINT; Schema: api; Owner: -
--

ALTER TABLE ONLY api.logins
    ADD CONSTRAINT logins_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES public.employees(employee_id);


--
-- Name: tokens tokens_employee_id_fkey; Type: FK CONSTRAINT; Schema: api; Owner: -
--

ALTER TABLE ONLY api.tokens
    ADD CONSTRAINT tokens_employee_id_fkey FOREIGN KEY (employee_id) REFERENCES api.logins(employee_id) ON DELETE CASCADE;


--
-- Name: invoices invoices_toll_rate_band_id_fkey; Type: FK CONSTRAINT; Schema: finance_scenario; Owner: -
--

ALTER TABLE ONLY finance_scenario.invoices
    ADD CONSTRAINT invoices_toll_rate_band_id_fkey FOREIGN KEY (toll_rate_band_id) REFERENCES public.toll_rate_bands(id);


--
-- Name: invoices invoices_vessel_id_fkey; Type: FK CONSTRAINT; Schema: finance_scenario; Owner: -
--

ALTER TABLE ONLY finance_scenario.invoices
    ADD CONSTRAINT invoices_vessel_id_fkey FOREIGN KEY (vessel_id) REFERENCES public.vessels(vessel_id);


--
-- Name: payments payments_invoice_number_fkey; Type: FK CONSTRAINT; Schema: finance_scenario; Owner: -
--

ALTER TABLE ONLY finance_scenario.payments
    ADD CONSTRAINT payments_invoice_number_fkey FOREIGN KEY (invoice_number) REFERENCES finance_scenario.invoices(invoice_number);


--
-- Name: invoices invoices_vessel_id_fkey; Type: FK CONSTRAINT; Schema: finance_test; Owner: -
--

ALTER TABLE ONLY finance_test.invoices
    ADD CONSTRAINT invoices_vessel_id_fkey FOREIGN KEY (vessel_id) REFERENCES public.vessels(vessel_id);


--
-- Name: containers containers_destination_locode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.containers
    ADD CONSTRAINT containers_destination_locode_fkey FOREIGN KEY (destination_locode) REFERENCES public.ports(locode);


--
-- Name: containers containers_origin_locode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.containers
    ADD CONSTRAINT containers_origin_locode_fkey FOREIGN KEY (origin_locode) REFERENCES public.ports(locode);


--
-- Name: containers containers_vessel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.containers
    ADD CONSTRAINT containers_vessel_id_fkey FOREIGN KEY (vessel_id) REFERENCES public.vessels(vessel_id);


--
-- Name: documents documents_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(department_id);


--
-- Name: employees employees_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(department_id);


--
-- Name: employees employees_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.employees
    ADD CONSTRAINT employees_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.roles(role_id);


--
-- Name: invoices invoices_toll_rate_band_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_toll_rate_band_id_fkey FOREIGN KEY (toll_rate_band_id) REFERENCES public.toll_rate_bands(id);


--
-- Name: invoices invoices_vessel_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invoices
    ADD CONSTRAINT invoices_vessel_id_fkey FOREIGN KEY (vessel_id) REFERENCES public.vessels(vessel_id);


--
-- Name: payments payments_invoice_number_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_invoice_number_fkey FOREIGN KEY (invoice_number) REFERENCES public.invoices(invoice_number);


--
-- Name: port_call_messages port_call_messages_port_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.port_call_messages
    ADD CONSTRAINT port_call_messages_port_fk FOREIGN KEY (port_locode) REFERENCES public.ports(locode);


--
-- Name: port_call_messages port_call_messages_vessel_fk; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.port_call_messages
    ADD CONSTRAINT port_call_messages_vessel_fk FOREIGN KEY (vessel_id) REFERENCES public.vessels(vessel_id);


--
-- Name: port_connections port_connections_port1_locode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.port_connections
    ADD CONSTRAINT port_connections_port1_locode_fkey FOREIGN KEY (port1_locode) REFERENCES public.ports(locode);


--
-- Name: port_connections port_connections_port2_locode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.port_connections
    ADD CONSTRAINT port_connections_port2_locode_fkey FOREIGN KEY (port2_locode) REFERENCES public.ports(locode);


--
-- Name: vessels vessels_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vessels
    ADD CONSTRAINT vessels_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(customer_id);


--
-- Name: vessels vessels_destination_locode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vessels
    ADD CONSTRAINT vessels_destination_locode_fkey FOREIGN KEY (destination_locode) REFERENCES public.ports(locode);


--
-- Name: vessels vessels_origin_locode_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vessels
    ADD CONSTRAINT vessels_origin_locode_fkey FOREIGN KEY (origin_locode) REFERENCES public.ports(locode);


--
-- PostgreSQL database dump complete
--

