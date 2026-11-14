# PortPilot

Port and logistics intelligence: governed Q&A, weekly finance packs, voyage monitoring and route advice.
Every financial number comes from checked data; packs require human review before publication.

![PortPilot logo](docs/brand/portpilot-logo.svg)

An educational project using synthetic company data and public shipping sources. Python agents and FastAPI
connect PostgreSQL/PostGIS, MongoDB and Qdrant; the Next.js frontend and Power BI present the results.

- [Architecture](ARCHITECTURE.md)
- [Current status and next steps](docs/ROADMAP.md)
- [Pipeline run order](pipelines/README.md)
- [Database setup](db/README.md)
- [PortPilot branding and compatibility](docs/brand/README.md)
- [Approved-pack publication and recovery](docs/publication_recovery.md)

Run the API from the project root with `uv run python pipelines/scripts/api/Serve.py`, and the web app with
`npm --prefix web run dev`. See the existing setup docs for credentials and database prerequisites.
Open `powerbi/PortPilot_Finance.pbip` for the finance dashboard.
