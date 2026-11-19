# PortPilot

Port and logistics intelligence: governed Q&A, weekly finance packs, voyage monitoring and route advice.
Every financial number comes from checked data; packs require human review before publication.

![PortPilot logo](docs/brand/portpilot-logo.svg)

An educational project using synthetic company data and public shipping sources. Python agents and FastAPI
connect PostgreSQL/PostGIS, MongoDB and Qdrant; the Next.js frontend and Power BI present the results.

## Repository layout

| Folder | What it is |
|---|---|
| `pipelines/` | the runtime: agents (LangGraph), the API (FastAPI), the shared library, the command-line entry points |
| `web/` | the Next.js frontend |
| `powerbi/` | the Power BI finance dashboard (PBIP) |
| `db/` | database migrations, reference data, login and audit scripts |
| `deploy/`, `ops/` | the Compose stack, the container image, the deploy script, the scheduled tasks |
| `Data/` | processed data and frozen evaluation sets |
| `docs/` | architecture, decisions, roadmap, runbook, API schema |
| `dev/` | development and building only: checks, evaluations, the data builders, run tooling, history |

## Run

Run the API from the project root with `uv run python pipelines/scripts/api/Serve.py`, and the web app with
`npm --prefix web run dev`. See the setup docs for credentials and database prerequisites.
Open `powerbi/PortPilot_Finance.pbip` for the finance dashboard. Production runs as one Compose stack
(`deploy/compose.yaml`, `docs/deploy/RUNBOOK.md`).

## Checks

```text
uv run python dev/tools/lint_ratchet.py
uv run python dev/tools/run.py dev/checks/ops/Deploy_check.py
uv run python dev/tools/path_refs_check.py
npm --prefix web run check -- --static
```

The full list is the CI workflow (`.github/workflows/ci.yml`); `dev/README.md` describes every check and builder.

- [Architecture](ARCHITECTURE.md)
- [Current status and next steps](docs/ROADMAP.md)
- [Runtime entry points](pipelines/README.md) · [Development and building](dev/README.md)
- [Database setup](db/README.md)
- [PortPilot branding and compatibility](docs/brand/README.md)
- [Approved-pack publication and recovery](docs/publication_recovery.md)
