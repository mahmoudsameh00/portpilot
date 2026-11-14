-- =====================================================================
-- 023 — Schema api + role api_writer for the NileGate API; the shared LLM counters in agent_state
--       (FastAPI plan P1, docs/plans/FastAPI_plan.md §4 / §6 / §6a, approved 2026-11-03; owner A1 local login,
--       A2 PostgreSQL only, A3 conversation memory)
-- Why: the API logs employees in, keeps conversations and their memory, and records who saw what (ADR-014's
-- audit_log); several processes (the API + the scheduled CLIs) must share one daily LLM counter and one per-minute
-- limiter instead of a file per process (ROADMAP concurrency requirements 1 and 2).
-- Least privilege (as 016):
--   * schema and tables belong to postgres; logins are created by the owner (pipelines/scripts/api/Api_admin.py, as
--     the owner account), never by the API;
--   * api_writer (NOLOGIN) gets explicit, per-table grants — the runtime reads a password hash but never writes one,
--     counts failed logins, issues / revokes tokens, keeps conversations, and appends to audit_log (no UPDATE, no
--     DELETE there: the log is append-only); no DDL, no TRUNCATE, nothing in public / finance / agent_state;
--   * the runtime login ports_api joins api_writer (db/create_api_user.ps1, from .env), search_path = api;
--   * the two agent_state tables get agent_writer's DML through 016's default privileges (the CLIs and the API both
--     use the checkpointer login ports_agent for them).
-- ports_readonly and finance_bi get nothing here (their default privileges are scoped to other schemas).
-- Decisions: ADR-016 (migrations), ADR-034, ADR-014 (audit_log redesign), ADR-064 (the API). Written by hand; never
-- edited after applying.
-- =====================================================================
BEGIN;

CREATE SCHEMA api AUTHORIZATION postgres;
COMMENT ON SCHEMA api IS 'The NileGate API (FastAPI plan, ADR-064): logins, bearer tokens, conversations with their memory, and the audit log. Written only through the role api_writer; logins are created by the owner (Api_admin.py). Conversation turns hold masked answers (no numbers) and entity frames: level 2 / Finance at rest at most.';
REVOKE ALL ON SCHEMA api FROM PUBLIC;

-- logins ---------------------------------------------------------------
CREATE TABLE api.logins (
    employee_id     integer PRIMARY KEY REFERENCES public.employees (employee_id),
    password_hash   text NOT NULL CHECK (password_hash LIKE 'scrypt$%'),
    disabled        boolean NOT NULL DEFAULT false,
    failed_attempts integer NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
    locked_until    timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    password_set_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE api.logins IS 'One API login per employee (FastAPI plan §6, owner A1): the employee signs in with the employees.email of this id and a password. Created / reset / disabled by the owner with Api_admin.py; the API only reads the hash and counts failures.';
COMMENT ON COLUMN api.logins.employee_id IS 'The employee this login signs in as (employees.employee_id); role, ceiling and department are read from employees at every request, never stored here';
COMMENT ON COLUMN api.logins.password_hash IS 'scrypt$<n>$<r>$<p>$<salt base64>$<hash base64> (hashlib.scrypt, a random 16-byte salt per login); the password itself is never stored or logged';
COMMENT ON COLUMN api.logins.disabled IS 'true = this login cannot sign in (set by the owner); its tokens are refused too';
COMMENT ON COLUMN api.logins.failed_attempts IS 'Wrong passwords since the last successful sign-in; at 5 the login is locked for 15 minutes';
COMMENT ON COLUMN api.logins.locked_until IS 'Sign-in refused until this instant (after 5 failures); NULL = not locked';
COMMENT ON COLUMN api.logins.created_at IS 'When the owner created the login';
COMMENT ON COLUMN api.logins.password_set_at IS 'When the password was last set by the owner';

-- tokens ---------------------------------------------------------------
CREATE TABLE api.tokens (
    token_sha256 bytea PRIMARY KEY CHECK (octet_length(token_sha256) = 32),
    employee_id  integer NOT NULL REFERENCES api.logins (employee_id) ON DELETE CASCADE,
    issued_at    timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    revoked_at   timestamptz,
    CHECK (expires_at > issued_at)
);
CREATE INDEX tokens_employee_id_idx ON api.tokens (employee_id);
COMMENT ON TABLE api.tokens IS 'Bearer tokens issued at sign-in (FastAPI plan §6): only the SHA-256 of the 32 random bytes is stored, so a copy of this table signs nobody in. Valid while not revoked and before expires_at (8 h).';
COMMENT ON COLUMN api.tokens.token_sha256 IS 'SHA-256 of the token the client holds (32 bytes)';
COMMENT ON COLUMN api.tokens.employee_id IS 'The login the token belongs to (api.logins)';
COMMENT ON COLUMN api.tokens.issued_at IS 'Sign-in instant';
COMMENT ON COLUMN api.tokens.expires_at IS 'The token is refused from this instant (issued_at + 8 h)';
COMMENT ON COLUMN api.tokens.revoked_at IS 'Set at logout (or by the owner); NULL = not revoked';

-- conversations and their memory (§6a) ----------------------------------
CREATE TABLE api.conversations (
    conversation_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     integer NOT NULL REFERENCES api.logins (employee_id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    last_turn_at    timestamptz,
    closed_at       timestamptz
);
CREATE INDEX conversations_employee_id_idx ON api.conversations (employee_id);
COMMENT ON TABLE api.conversations IS 'A conversation of one employee (FastAPI plan §3.2 / §6a): its question turns and their memory; the uploads of the conversation live only in the API process memory (ADR-043). Only its owner continues it; the CEO may read it.';
COMMENT ON COLUMN api.conversations.conversation_id IS 'Random id (also the upload session id)';
COMMENT ON COLUMN api.conversations.employee_id IS 'The owner (api.logins)';
COMMENT ON COLUMN api.conversations.created_at IS 'Opened at';
COMMENT ON COLUMN api.conversations.last_turn_at IS 'The last question''s instant; NULL before the first question';
COMMENT ON COLUMN api.conversations.closed_at IS 'Closed by its owner or after 8 h idle; NULL = open. Closing deletes its turns (the memory)';

CREATE TABLE api.conversation_turns (
    conversation_id     uuid NOT NULL REFERENCES api.conversations (conversation_id) ON DELETE CASCADE,
    turn_no             integer NOT NULL CHECK (turn_no >= 1),
    question            text NOT NULL CHECK (char_length(question) BETWEEN 1 AND 2000),
    standalone_question text,
    resolved_by         text NOT NULL CHECK (resolved_by IN ('none', 'code', 'model', 'clarify')),
    lang                text NOT NULL CHECK (lang IN ('en', 'ar')),
    as_of               timestamptz NOT NULL,
    status              text,
    thread_id           text,
    answer_masked       text,
    frame               jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(frame) = 'object'),
    refused             text[] NOT NULL DEFAULT '{}',
    created_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (conversation_id, turn_no)
);
COMMENT ON TABLE api.conversation_turns IS 'The memory of a conversation (FastAPI plan §6a, ADR-065): one row per question. Never a number of an earlier answer (answer_masked), never upload / document / web text, never an entity of a refused part.';
COMMENT ON COLUMN api.conversation_turns.conversation_id IS 'The conversation (api.conversations)';
COMMENT ON COLUMN api.conversation_turns.turn_no IS '1, 2, … in the order asked';
COMMENT ON COLUMN api.conversation_turns.question IS 'The employee''s words as asked (≤ 2,000 characters)';
COMMENT ON COLUMN api.conversation_turns.standalone_question IS 'The follow-up rewritten as a full question by the memory step (what was routed and answered); NULL when the question was routed as asked';
COMMENT ON COLUMN api.conversation_turns.resolved_by IS 'none = not a follow-up; code = resolved by the rules; model = one guarded rewrite call; clarify = the API asked the employee back (no tool ran)';
COMMENT ON COLUMN api.conversation_turns.lang IS 'en or ar (Egyptian Arabic), detected or asked';
COMMENT ON COLUMN api.conversation_turns.as_of IS 'The clock the turn ran at (RunContext.as_of)';
COMMENT ON COLUMN api.conversation_turns.status IS 'The supervisor''s status (answered, partial, not_permitted, not_in_data, validation_failed, output_invalid) or clarify; NULL while running';
COMMENT ON COLUMN api.conversation_turns.thread_id IS 'The agent_state thread of the answer (ask:<employee>:<as_of>:<n>); NULL for clarify';
COMMENT ON COLUMN api.conversation_turns.answer_masked IS 'The rendered answer with every slot replaced by ⟨n⟩: context for a later rewrite, never a source of a figure';
COMMENT ON COLUMN api.conversation_turns.frame IS 'The entity frame built by code from this turn''s cited evidence rows (vessel ids, report weeks, customer ids, LOCODEs, routes, invoice numbers, document ids, alert ids, topic)';
COMMENT ON COLUMN api.conversation_turns.refused IS 'Tools the router dropped for this asker on this turn (their entities never enter the frame)';
COMMENT ON COLUMN api.conversation_turns.created_at IS 'Asked at';

-- audit log (ADR-014 redesign) -------------------------------------------
CREATE TABLE api.audit_log (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at            timestamptz NOT NULL DEFAULT now(),
    employee_id   integer,
    request_id    uuid,
    trace_id      text,
    resource_type text NOT NULL,
    resource_id   text,
    action        text NOT NULL,
    decision      text NOT NULL CHECK (decision IN ('allowed', 'denied')),
    detail        jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(detail) = 'object')
);
CREATE INDEX audit_log_employee_at_idx ON api.audit_log (employee_id, at);
CREATE INDEX audit_log_at_idx ON api.audit_log (at);
COMMENT ON TABLE api.audit_log IS 'Who did or was refused what through the API (ADR-014 redesign; THREAT_MODEL LLM02 / T8). Append-only for the runtime (INSERT, SELECT). Never a password, a token, a question''s text or an answer.';
COMMENT ON COLUMN api.audit_log.id IS 'Surrogate key, in insertion order';
COMMENT ON COLUMN api.audit_log.at IS 'When';
COMMENT ON COLUMN api.audit_log.employee_id IS 'The signed-in employee; NULL for a failed sign-in with an unknown email (no FK: rows outlive a login)';
COMMENT ON COLUMN api.audit_log.request_id IS 'The X-Request-ID of the HTTP request (also in the access log, Sentry and LangSmith)';
COMMENT ON COLUMN api.audit_log.trace_id IS 'The agent_state thread id of a run (= the LangSmith trace''s thread_id metadata), when there is one';
COMMENT ON COLUMN api.audit_log.resource_type IS 'login, token, conversation, question, upload, pack, route_advice, voyage_watch, tool';
COMMENT ON COLUMN api.audit_log.resource_id IS 'Its id (a thread id, a document id, a tool name …); NULL when none';
COMMENT ON COLUMN api.audit_log.action IS 'sign_in, sign_out, read, ask, refused_part, upload, decide, promote, …';
COMMENT ON COLUMN api.audit_log.decision IS 'allowed or denied';
COMMENT ON COLUMN api.audit_log.detail IS 'Small structured facts (status, counts, reasons); redacted, no free text from a model or a user';

-- the runtime role -------------------------------------------------------
CREATE ROLE api_writer NOLOGIN;
COMMENT ON ROLE api_writer IS 'Least privilege for the NileGate API (FastAPI plan P1, ADR-064): per-table grants in schema api only — read login hashes and count failures, issue / revoke tokens, keep conversations and their turns, append to audit_log. No password writes, no DDL, no TRUNCATE, nothing in other schemas. The login ports_api joins it (db/create_api_user.ps1) and sets search_path = api itself.';
GRANT CONNECT ON DATABASE ports_logistics TO api_writer;
GRANT USAGE ON SCHEMA api TO api_writer;
GRANT SELECT ON api.logins TO api_writer;
GRANT UPDATE (failed_attempts, locked_until) ON api.logins TO api_writer;
GRANT SELECT, INSERT, DELETE ON api.tokens TO api_writer;
GRANT UPDATE (revoked_at) ON api.tokens TO api_writer;
GRANT SELECT, INSERT, DELETE ON api.conversations TO api_writer;
GRANT UPDATE (last_turn_at, closed_at) ON api.conversations TO api_writer;
GRANT SELECT, INSERT, UPDATE, DELETE ON api.conversation_turns TO api_writer;
GRANT SELECT, INSERT ON api.audit_log TO api_writer;

-- the shared LLM counters (agent_state; agent_writer's DML from migration 016's default privileges) ---------------
CREATE TABLE agent_state.llm_daily_usage (
    scope        text NOT NULL,
    provider_day date NOT NULL,
    requests     integer NOT NULL DEFAULT 0 CHECK (requests >= 0),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scope, provider_day)
);
COMMENT ON TABLE agent_state.llm_daily_usage IS 'The daily LLM request count shared by every process (FastAPI plan C1, ADR-045): a call is reserved by one atomic INSERT … ON CONFLICT DO UPDATE … WHERE requests < limit RETURNING before it is sent; no row back = the daily quota is spent. Written by pipelines/agents/llm.py as ports_agent.';
COMMENT ON COLUMN agent_state.llm_daily_usage.scope IS 'What the provider counts per day: a model (Gemini, Groq: provider/model) or a whole provider (OpenRouter), as llm.py''s scope()';
COMMENT ON COLUMN agent_state.llm_daily_usage.provider_day IS 'The provider''s day (its own time zone, llm.PROVIDERS day_tz)';
COMMENT ON COLUMN agent_state.llm_daily_usage.requests IS 'Requests reserved that day (sent or being sent)';
COMMENT ON COLUMN agent_state.llm_daily_usage.updated_at IS 'Last reservation';

CREATE TABLE agent_state.llm_minute_usage (
    scope    text NOT NULL,
    minute   timestamptz NOT NULL CHECK (minute = date_trunc('minute', minute)),
    requests integer NOT NULL DEFAULT 0 CHECK (requests >= 0),
    tokens   integer NOT NULL DEFAULT 0 CHECK (tokens >= 0),
    PRIMARY KEY (scope, minute)
);
COMMENT ON TABLE agent_state.llm_minute_usage IS 'The per-minute LLM budget shared by every process (FastAPI plan C2, ADR-045): requests and estimated tokens reserved in the current minute, atomically; over the limit → the caller waits for the next minute. Rows older than a day are deleted by llm.py.';
COMMENT ON COLUMN agent_state.llm_minute_usage.scope IS 'The rate scope (llm.py: a provider or provider/model)';
COMMENT ON COLUMN agent_state.llm_minute_usage.minute IS 'The UTC minute (truncated)';
COMMENT ON COLUMN agent_state.llm_minute_usage.requests IS 'Requests reserved in that minute';
COMMENT ON COLUMN agent_state.llm_minute_usage.tokens IS 'Estimated tokens reserved in that minute';

COMMIT;
