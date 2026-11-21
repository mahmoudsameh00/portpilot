# Repository layout and hygiene plan — runtime vs development, local tool files, `.gitignore`, GitHub, SSH

**Status: IMPLEMENTED (2026-11-19).** Approved 2026-11-19 by the owner with every recommended option (D-RL-1 … D-RL-4).
ADR-072. The owner's git / GitHub steps (§9) were done 2026-11-19 / 20 (history rewritten, renamed `portpilot`, PR 9
merged, old branches deleted); step 10 (`master` protection) was refused by GitHub on a private free repository (403)
and skipped.

## Implementation record

- **Moved (65 files + 14 folders; map `dev/tools/layout_map.json`):** 46 checks / evaluations / smoke tests / probes →
  `dev/checks/<area>/` (with `agents/fixtures/`, `api/integration_fixture.py`, `api/Web_stack_fixture.py`); 15 builders
  + the four notebook-derived areas (`rag`, `structured`, `synthetic`, `semi_structured`) + `db/export_vessels_mirror.py`
  → `dev/build/<area>/`; `pipelines/checkpoints/` → `dev/checkpoints/`; `tools/` → `dev/tools/`; `ops/tests/` →
  `dev/tests/`; `db/audit`, `db/mongo/audit`, `db/qdrant/audit` → `dev/db_audit/postgres|mongo|qdrant/`;
  `docs/archive/`, the four `CHECKPOINT_*.md`, `docs/analysis/` → `dev/history/`; the run logs → `dev/_scratch/`
  (git-ignored; `Notebooks/` is gone). Runtime unchanged: `pipelines/agents|api|lib`, the 14 runtime CLIs in
  `pipelines/scripts/<area>/`, `db/`, `deploy/`, `ops/docker|deploy|scheduler`, `web/`, `powerbi/`, `Data/`.
- **References:** 1,626 path references rewritten in 160 files from the map (exact path tokens; the archive and the
  saved audits keep their paths as written). By hand: `parents[1]` → `parents[2]` in the moved tools, every
  `ROOT / "Notebooks" / "_scratch"` (18), `run.py`'s `all` order and archived-notebook lookup, `nb_to_script.py`'s
  folders, the lint baseline path and ruff targets (`pipelines dev db`), ruff `extend-exclude`, `probe_qdrant.py`'s
  audit folder, three dotted imports `pipelines.scripts.api.integration_fixture` → `dev.checks.api.integration_fixture`,
  the web tests' screenshot folder.
- **Kept byte-identical on purpose (D-RL-5):** the applied migrations — a first rewrite pass touched eight of them
  (681 times in 030, the `source` column of its rows); they were restored at once and `Migrate.py status` confirmed
  31 of 31 checksums equal to the recorded ones. The strings that builders write into migrations and manifests
  (`Port_call_generator.py` `SOURCE` and manifest, `Finance_generator.py` manifest + SQL headers, the two SQL headers of
  `Suez_transits_loader.py` / `Finance_scenario_generator.py`) keep the path the files were generated from, so a re-run
  writes identical bytes. `db/migrations/` is now outside every rewrite and outside the path rule.
- **Image:** `ops/docker/api.Dockerfile` no longer copies the run tool; with the checks outside `pipelines/` the image
  carries no check, evaluation or builder script.
- **Web:** the sample-data concept gate left the build (three pages, their fixtures, the concept top bar, the concept
  test; the three charts only it used); `StatusBadge.tsx` moved to `components/packs/`; the test-only `spansFor` helper
  moved into its test; the concept test's CSP-violation and page-error assertions now run on every production page in
  `security.e2e.spec.ts`.
- **Local tool files:** listed in `.git/info/exclude` (never versioned); the tracked `.gitignore` was rewritten
  (§5); `secrets_scan.py` also skips the folders listed in that local file; `.gitleaks.toml` lost the graph folder; the
  Power BI model annotation names only `DevMode`; tool mentions in every tracked text (the archive included) were
  reworded without changing a fact, e.g. who ran a step is now written in the passive or as "the developer".
- **New check:** `dev/tools/path_refs_check.py` (CI step after the secrets scan): every repository path written in a
  tracked text file exists or is git-ignored, every relative Markdown link resolves, no local tool name; the 110
  references that already pointed at removed files before the move (old plan names, the archived notebooks, prose
  shorthands such as `tools/eta.py` for `pipelines/agents/tools/eta.py`) are listed in `dev/tools/path_refs_allow.txt`.
- **Docs:** ADR-072; ARCHITECTURE §1.2 (repository layout), §2, §9; ROADMAP; `README.md` (layout, run, checks);
  `pipelines/README.md` (runtime only) and `dev/README.md` (every builder and check); RUNBOOK (the repository name in the
  clone line and the federated credential); the local rules file.
- **Results (§8):** see the table at the end of this record.

### Deviations

- D-RL-5 (above): the migrations and the builders' output strings were excluded from the rewrite after the first pass.
- D-RL-6: the secrets scan reads 974 files instead of 1,278: the 302 files of the local tool folders are skipped (they
  are never versioned), six concept files are gone, four new files exist (`dev/README.md`, the path check, its
  allow-list, the layout map).
- D-RL-7: one ✅ text changed on purpose — `Monitoring_check.py` Phase 6 (live only, not in the baseline) now says
  "read back in Sentry".
- D-RL-8: the first CI run after the push (PR 9) failed the path check on 14 references that resolve on the owner's
  machine only: git-ignored folders absent from a fresh clone (`Data/raw`, the model and tool caches, the query-vector
  cache, `Data/incoming`; a folder-only ignore rule needs to know the path is a folder) and the empty `docs/plans/`
  (git keeps no empty folder). Fixed: a missing path counts as ignored when git would ignore it as a file or as a
  folder; `docs/plans/.gitkeep` keeps the folder. A skeleton checkout with only the ignore files reproduced the failure
  before the fix and passed after it.

### Verification (before = the tree of 2026-11-19 morning, after = the new layout)

| Check | Before | After |
|---|---|---|
| Lint ratchet (ruff + pyright) | ✅ | ✅ same line |
| 13 CI 0-network checks (Monitoring, LangSmith mirror, OpenAPI snapshot, run lifecycle, integration guard, scheduled outcomes, publication, approval safety, traffic claims, brand compatibility, approval cases, Deploy_check, secrets scan) | 13 / 13 rc 0 | 13 / 13 rc 0, same ✅ lines (secrets: file count, D-RL-6) |
| Database-backed, no model call (Tools, Finance views, Lib selftest, Models config, Traffic link, Deck, External context, Approver request) | 8 / 8 rc 0 | 8 / 8 rc 0, same ✅ lines |
| `Migrate.py status` | 31 / 31 | 31 / 31, no file edited |
| Web static (allow-list, Orval, tsc, eslint, prettier, audit) | 6 / 6 | 6 / 6 |
| Playwright (production build + mock API) | 160 passed, 58 skipped | 142 passed, 58 skipped, 0 failed (the 18 concept runs = 9 tests × 2 projects removed; the CSP / page-error assertions now on every production page) |
| `nb_to_script.py check` (the 15 notebook-derived builders) | — | ALL OK after the 10 path-only changes were recorded (`evolve`; reverting the map reproduces the 2026-11-17 fingerprints exactly) |
| Images: API + web build, API runs as `portpilot`, `create_app` imports, `--fake-roles` refused, web runs as `node`; compose config with the example env | — | all pass; the API image holds the 14 runtime CLIs, 0 `*_check` / `*_eval` files, no `tools/`, no `dev/` |
| Every `.py` compiles (200 files) | — | 200 / 200 |
| `path_refs_check.py` | — (new) | ✅ 647 text files, 114 allowed historical entries, no local tool name |
| Registered Windows tasks | `Weekly_pack.py`, `Voyage_watch.py` | unchanged paths (both files stayed in `pipelines/scripts/agents/`) |

---

## The approved plan (condensed)

**Goal.** Split what the run / production needs from what was made for development and building; adjust the GitHub
repository; remove every sign of the local tools used during development; review `.gitignore`; connect GitHub over
SSH. Every path inside every file must still resolve and everything must work exactly as before.

**Decisions (owner, 2026-11-19, one round).** D-RL-1 `dev/` for the development code and the history, `Data/`
unchanged. D-RL-2 local tool files kept on disk, untracked, words reworded everywhere. D-RL-3 the git history rewritten
after a mirror + bundle backup, then a force push. D-RL-4 the repository renamed to `portpilot`, description + topics,
one PR `feat/agents` → `master`, merged old branches deleted, `master` protected after the history step, a README
layout section.

**Method.** (1) A baseline of every check before any move; (2) one move map; (3) a text rewrite from the map, longest
path first, exact tokens only; (4) the paths built from segments fixed by hand; (5) a permanent path-references check
in CI; (6) the same checks after the move, line by line.

**`.gitignore` (§5).** Kept: environment and caches, secrets (`.env*` except the templates), temporary files and logs,
raw data, generated data (vectors, local models, uploads awaiting review, the model and tool caches, reports), Power BI
local files, deployment backups and env files. Added: `.ruff_cache/`, `.pytest_cache/`, `.vscode/`, `.idea/`,
`dev/_scratch/`. Moved to the local exclude file: the local tool output folders. `Data/processed/rag/ocr_cache/` stays
tracked (the OCR results make the USCG chunking reproducible without the OCR model, ADR-025).

**SSH (§7).** An HTTPS push uses a stored token: whoever copies it can push from anywhere until it is revoked. With
SSH the private key never leaves the laptop and never crosses the network — the laptop proves it holds the key by
signing a one-time challenge; the key has a passphrase and is loaded once per session by the Windows `ssh-agent`;
one laptop's key is revoked on GitHub alone; GitHub's pinned host key refuses a fake server. The same key signs
commits (GitHub's "Verified" badge). The private key is created by the owner only.

**§9 Owner steps (in order).** 0 backups (bundle of every branch, a GitHub mirror, a zip of the local tool files);
1 the local tool files leave the index; 2 stage and review (the migrations must show no change); 3 one commit, no
attribution line; 4 a look at the old messages; 5 SSH (key, agent, `gh ssh-key add` for authentication and signing,
`ssh -T`, signing config); 6 the history rewrite with `git filter-repo` (the local tool paths out of every commit, the
attribution lines out of every message) — risks: every commit id changes, other clones must be cloned again, open PRs
and forks break, GitHub keeps merged PR 1's old commits under `refs/pull/` until GitHub Support purges them, the
backups undo everything; 7 rename to `portpilot`, the SSH remote, force push, description and topics; 8 the PR and its
merge after a green CI; 9 the merged old branches deleted; 10 `master` protected (on a private free repository GitHub
refuses: skip). The exact commands were handed to the owner in a local file.
