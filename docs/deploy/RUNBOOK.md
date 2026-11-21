# PortPilot deployment runbook (staging, then production on Azure)

The decisions behind it: ADR-071 (one Linux VM per environment, one Compose stack, Caddy TLS, the schedules in a
container), ADR-016 amendment 1 (migrations on deploy), the ADR-045 note of 2026-11-17 (free models, paid path). The
plan that built it: `dev/history/archive/2026-11-18_Staging_readiness_plan.md`. Commands below are PowerShell on the owner's
Windows machine (`PS>`) and bash on the Linux VM (`$`). Every secret goes through Key Vault or a prompt — never a
command line you paste into chat, never git.

**Today there is one public environment, `staging` (ADR-071 amendment 1); `production` is deferred.** §3–§8 are
written for production. For staging, use `ENV=staging`, `Standard_B2ms`, a 64 GiB disk, the vault
`portpilot-staging-kv`, the env file `staging.env` and the stack `portpilot-staging`. Before you share staging with
testers, apply the "Public staging" gates of §15.

```text
Internet ─443─▶ Caddy (TLS, HSTS, 6 MB) ─▶ web (Next.js BFF) ─▶ api (FastAPI, 1 process) ─┬─▶ postgres (PostGIS)
                 /api/*, /docs → 404                        scheduler (pack Mon 10:30,   ├─▶ mongo (AIS / EDI)
                                                             watch 10:30 + 22:30 Cairo) ─┴─▶ qdrant (127.0.0.1 only)
                                                             api + scheduler ──egress──▶ Gemini, Groq, OpenRouter,
                                                                                         Jina, Tavily, PortWatch, Open-Meteo
```

## 1. Local staging rehearsal (Docker Desktop; done on 2026-11-18, repeatable)

```powershell
PS> uv run python ops/deploy/new_env.py staging --rehearsal --copy-keys      # deploy/env/staging-rehearsal.env
PS> docker compose -f deploy/compose.yaml --env-file deploy/env/staging-rehearsal.env build api web
PS> docker compose -f deploy/compose.yaml --env-file deploy/env/staging-rehearsal.env up -d postgres mongo qdrant
PS> docker compose -f deploy/compose.yaml --env-file deploy/env/staging-rehearsal.env create api
PS> uv run python pipelines/scripts/ops/Backup.py backup --stack local --with-models
PS> uv run python pipelines/scripts/ops/Backup.py restore backups/local_<stamp> --stack portpilot-rehearsal --env-file deploy/env/staging-rehearsal.env
PS> uv run python pipelines/scripts/ops/Backup.py secure --stack portpilot-rehearsal --env-file deploy/env/staging-rehearsal.env
PS> docker compose -f deploy/compose.yaml --env-file deploy/env/staging-rehearsal.env --profile ops run --rm -v "${PWD}\models:/seed:ro" ops python -c "import shutil; shutil.copytree('/seed/onnx/bge-m3', '/app/models/onnx/bge-m3', dirs_exist_ok=True)"
PS> docker compose -f deploy/compose.yaml --env-file deploy/env/staging-rehearsal.env --profile ops run --rm ops python pipelines/scripts/ops/Migrate.py apply --yes
PS> docker compose -f deploy/compose.yaml --env-file deploy/env/staging-rehearsal.env up -d
PS> docker cp portpilot-rehearsal-proxy:/data/caddy/pki/authorities/local/root.crt backups/rehearsal-root.crt
PS> uv run python pipelines/scripts/ops/Deploy_smoke.py --origin https://localhost:8443 --http-origin http://localhost:8080 --ca-file backups/rehearsal-root.crt --stack portpilot-rehearsal
```
Open `https://localhost:8443` (accept the local CA, or import `backups/rehearsal-root.crt`). Stop it with
`docker compose -f deploy/compose.yaml --env-file deploy/env/staging-rehearsal.env down` (add `-v` to delete its volumes).
It never touches `ports-postgres` / `ports-mongo` / `ports-qdrant` (read only by the backup).
Without `--copy-keys` no model key enters the stack and no quota is used; then set `PACK_RUN_AS` and `WATCH_RUN_AS` in the
env file by hand. `Migrate.py status` exits 3 while a migration is pending: that is its answer, not a failure.

## 2. Costs (check the Azure pricing calculator for your region before creating anything)

The Azure free account gives **USD 200 of credit for 30 days**; after that everything below is billed
pay-as-you-go unless you delete it. Sizes (measured needs: PostgreSQL ≈ 1 GB, MongoDB ≈ 1.5 GB with 1.33 M
documents, Qdrant ≈ 0.5 GB, the API ≈ 1 GB + 2.2 GB when the local bge-m3 model is loaded for an upload, the web
≈ 0.3 GB; disk ≈ 15 GB of data + 5 GB of images + backups):
- **production:** `Standard_B4ms` (4 vCPU, 16 GiB) + a 128 GiB Standard SSD data disk;
- **staging:** `Standard_B2ms` (2 vCPU, 8 GiB) + 64 GiB, **deallocated when not in use** (`az vm deallocate`: no
  compute charge while stopped, disks still billed);
- Key Vault (standard): cents per month; Blob Storage (cool, LRS) for backups: ≈ 1–2 GB a night before retention;
- a domain: any registrar (Azure DNS zone optional).

## 3. Azure resources (once per environment; `ENV=staging` or `production`)

Install the Azure CLI on your PC (`winget install Microsoft.AzureCLI`), then `az login`.
```bash
ENV=production; RG=portpilot-$ENV; LOC=westeurope; VM=portpilot-$ENV; KV=portpilot-$ENV-kv; SA=portpilot${ENV}bk
az group create -n $RG -l $LOC
az vm create -g $RG -n $VM --image Ubuntu2404 --size Standard_B4ms --admin-username portpilotadmin \
   --generate-ssh-keys --public-ip-sku Standard --data-disk-sizes-gb 128 --assign-identity --nsg-rule NONE
az network nsg rule create -g $RG --nsg-name ${VM}NSG -n web --priority 100 --access Allow --protocol Tcp \
   --destination-port-ranges 80 443
# SSH only from your own address (or none: run-command needs no port)
az network nsg rule create -g $RG --nsg-name ${VM}NSG -n ssh-owner --priority 110 --access Allow --protocol Tcp \
   --destination-port-ranges 22 --source-address-prefixes <your public IP>/32
az keyvault create -g $RG -n $KV --enable-rbac-authorization true
PRINCIPAL=$(az vm show -g $RG -n $VM --query identity.principalId -o tsv)
az role assignment create --assignee $PRINCIPAL --role "Key Vault Secrets User" \
   --scope $(az keyvault show -n $KV --query id -o tsv)
# You too need a data-plane role to write the secrets of §5 (an RBAC vault grants nothing to its creator)
az role assignment create --assignee $(az ad signed-in-user show --query id -o tsv) --role "Key Vault Secrets Officer" \
   --scope $(az keyvault show -n $KV --query id -o tsv)
az storage account create -g $RG -n $SA --sku Standard_LRS --kind StorageV2 --access-tier Cool --min-tls-version TLS1_2 \
   --allow-blob-public-access false
# The management plane (your subscription role), not a blob data role: --auth-mode login would need one
az storage container-rm create --storage-account $SA -g $RG -n backups
az role assignment create --assignee $PRINCIPAL --role "Storage Blob Data Contributor" \
   --scope $(az storage account show -n $SA --query id -o tsv)
```
Point the domain's A record (e.g. `portpilot.<your domain>`, `staging.portpilot.<your domain>`) at the VM's public IP
(`az vm show -d -g $RG -n $VM --query publicIps -o tsv`). Caddy gets the certificate on its first start.
Blob retention: a lifecycle rule deleting `backups/*` older than 35 days (Portal → Storage account → Lifecycle
management), so the off-host copy mirrors the 7 + 4 local retention.

## 4. VM bootstrap (once; over SSH or `az vm run-command invoke … --scripts`)

```bash
$ sudo mkfs.ext4 /dev/disk/azure/scsi1/lun0 && sudo mkdir -p /opt/portpilot && \
  echo "/dev/disk/azure/scsi1/lun0 /opt/portpilot ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab && sudo mount -a
$ curl -fsSL https://get.docker.com | sudo sh                 # Docker Engine + compose plugin
$ curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash        # az, for Key Vault and the backup copy
$ sudo useradd --system --create-home --home-dir /opt/portpilot/home --groups docker portpilot
$ sudo mkdir -p /opt/portpilot/{env,state,backups} && sudo chown -R portpilot: /opt/portpilot
$ echo '{"data-root": "/opt/portpilot/docker"}' | sudo tee /etc/docker/daemon.json   # images + volumes on the data disk
$ sudo systemctl restart docker
$ sudo -u portpilot ssh-keygen -t ed25519 -N "" -f /opt/portpilot/home/.ssh/id_ed25519
$ sudo cat /opt/portpilot/home/.ssh/id_ed25519.pub   # GitHub → repository → Settings → Deploy keys → add (read-only)
$ sudo -u portpilot git clone git@github.com:mahmoudsameh00/portpilot.git /opt/portpilot/repo
$ echo portpilot-production-kv | sudo -u portpilot tee /opt/portpilot/env/vault    # the vault of THIS environment
```
Docker's daemon log rotation is set per service in the compose file; the host needs nothing else.

## 5. Secrets into Key Vault (once per environment, from your PC)

```powershell
PS> uv run python ops/deploy/new_env.py production --site portpilot.<your domain> --tls <your email> --copy-keys
PS> # fill any key the script lists as empty (deploy/env/production.env), then upload every line:
PS> Get-Content deploy/env/production.env | Where-Object { $_ -match '^([A-Z_]+)=(.+)$' } | ForEach-Object {
      $name = 'production-' + ($Matches[1] -replace '_','-'); $val = $Matches[2]
      az keyvault secret set --vault-name portpilot-production-kv --name $name --value $val --output none }
PS> Remove-Item deploy/env/production.env       # the vault is the copy of record
```
`deploy.sh` renders `/opt/portpilot/env/production.env` (mode 600) from the vault when it is missing; to change a
secret, set it in the vault, delete that file on the VM, deploy again. `--copy-keys` copies the external API keys
from your `.env` — for production prefer **new keys** created for that environment (Gemini, Groq, OpenRouter, Jina,
Tavily, LangSmith, Sentry each allow several keys), so revoking one environment never breaks the other.

## 6. First deploy and seed (once per environment)

On your PC: a fresh backup of the local stores **with** the model, then copy it to the VM.
```powershell
PS> uv run python pipelines/scripts/ops/Backup.py backup --stack local --with-models
PS> scp -r backups/local_<stamp> portpilotadmin@<vm ip>:/tmp/seed     # or azcopy through the backup container
```
On the VM:
```bash
$ sudo mv /tmp/seed /opt/portpilot/backups/ && sudo chown -R portpilot: /opt/portpilot/backups
$ sudo -iu portpilot
$ cd /opt/portpilot/repo && git checkout <tag>
$ bash ops/deploy/render_env.sh production /opt/portpilot/env/production.env
$ export PORTPILOT_TAG=$(git rev-parse --short=12 HEAD); C="docker compose -f deploy/compose.yaml --env-file /opt/portpilot/env/production.env"
$ $C build api web && $C up -d postgres mongo qdrant && $C create api
$ python3 pipelines/scripts/ops/Backup.py restore /opt/portpilot/backups/seed --stack portpilot-production --env-file /opt/portpilot/env/production.env
$ python3 pipelines/scripts/ops/Backup.py secure --stack portpilot-production --env-file /opt/portpilot/env/production.env
$ tar -xzf /opt/portpilot/backups/seed/files/runtime.tar.gz -C /tmp models && \
  $C --profile ops run --rm -v /tmp/models:/seed:ro ops python -c "import shutil; shutil.copytree('/seed/onnx/bge-m3', '/app/models/onnx/bge-m3', dirs_exist_ok=True)" && rm -rf /tmp/models
$ $C --profile ops run --rm ops python pipelines/scripts/ops/Migrate.py apply --yes      # records 031 (the seed has 001–030)
$ $C up -d && echo $PORTPILOT_TAG > /opt/portpilot/state/production.tag
$ python3 pipelines/scripts/ops/Deploy_smoke.py --origin https://portpilot.<your domain> --stack portpilot-production
```
**Real users (S7):** `secure` disabled every login the seed carried. Create one per real person, on an existing
employee of the right role / department (`Api_admin.py list` shows them):
```bash
$ $C --profile ops run --rm ops python pipelines/scripts/api/Api_admin.py create --employee <id>   # asks twice, ≥ 12 chars
```
Never re-enable the test identities of the web stack E2E / CI fixtures; they exist only in their test databases.

## 7. GitHub: the deploy workflow (once)

1. Azure: an app registration for GitHub with **federated credentials** (no secret): Entra ID → App registrations →
   New → Certificates & secrets → Federated credentials → "GitHub Actions deploying Azure resources", organization
   `mahmoudsameh00`, repository `portpilot`, entity "Environment", names `staging` and `production` (one
   credential each). Give it the role **Virtual Machine Contributor** on each resource group (run-command only).
2. GitHub → Settings → Environments: create `staging`, `production`, `staging-migrations`, `production-migrations`;
   on each, **Required reviewers = you**; on `production`, also "Deployment branches and tags: selected tags `v*`".
3. Repository variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`; environment variables on
   `staging` / `production`: `AZURE_RESOURCE_GROUP`, `AZURE_VM_NAME`.
4. Deploy: Actions → Deploy → Run workflow → environment, ref (a tag whose CI is green), `apply_migrations` only when
   `Migrate.py status` lists pending files. You approve the job (and the migrations job) in the run page.

Rollback of the application: run the workflow with the previous tag (images rebuild from that ref). `deploy.sh`
already puts the previous images back by itself when the smoke fails. The **database** is never rolled back
automatically: restore (§9).

## 8. Backups (nightly on each VM)

```bash
$ sudo tee /etc/systemd/system/portpilot-backup.service <<'EOF'
[Unit]
Description=PortPilot nightly backup
[Service]
Type=oneshot
User=portpilot
WorkingDirectory=/opt/portpilot/repo
ExecStart=/usr/bin/python3 pipelines/scripts/ops/Backup.py backup --stack portpilot-production --env-file /opt/portpilot/env/production.env --out /opt/portpilot/backups
ExecStartPost=/usr/bin/python3 pipelines/scripts/ops/Backup.py prune --out /opt/portpilot/backups
ExecStartPost=/bin/bash -c 'az login --identity --allow-no-subscriptions -o none && az storage blob upload-batch --account-name portpilotproductionbk -d backups --destination-path $(hostname) -s /opt/portpilot/backups --auth-mode login --overwrite false -o none'
EOF
$ sudo tee /etc/systemd/system/portpilot-backup.timer <<'EOF'
[Unit]
Description=PortPilot nightly backup at 02:30 Cairo
[Timer]
OnCalendar=*-*-* 02:30 Africa/Cairo
Persistent=true
[Install]
WantedBy=timers.target
EOF
$ sudo systemctl daemon-reload && sudo systemctl enable --now portpilot-backup.timer
$ systemctl list-timers portpilot-backup.timer
```
A backup folder holds password **hashes** (roles.sql): the folder and the blob container stay private.

## 9. Restore (a lost VM, a bad migration, a drill)

```bash
$ python3 pipelines/scripts/ops/Backup.py verify /opt/portpilot/backups/<folder>         # hashes = the manifest
$ $C stop api scheduler web
$ python3 pipelines/scripts/ops/Backup.py restore /opt/portpilot/backups/<folder> --stack portpilot-production --env-file /opt/portpilot/env/production.env --yes
$ $C up -d && python3 pipelines/scripts/ops/Deploy_smoke.py --origin https://portpilot.<your domain> --stack portpilot-production
```
`restore` compares every table count, the `finance.kpi_weekly` digest, every MongoDB count and the Qdrant points /
digest with the backup and fails on any difference. From the blob copy:
`az storage blob download-batch --account-name <SA> -s backups --pattern '<host>/<folder>/*' -d /opt/portpilot/backups --auth-mode login`.
Drill: once a quarter on staging (the local drill: `uv run python pipelines/scripts/ops/Backup.py drill`).

## 10. Credential rotation

**Local first (your machine; the old password is in git history and the superuser's password is the word
`postgres`):**
```powershell
PS> $new = [Convert]::ToBase64String((1..24 | ForEach-Object { Get-Random -Max 256 }) -as [byte[]])
PS> docker exec -i ports-postgres psql -U postgres -c "ALTER ROLE postgres PASSWORD '$new'"
PS> # then set PGPASSWORD=<the new value> in .env (open it in your editor); repeat for PG_RO / PG_BI / PG_AGENT / PG_API
PS> # with db/create_readonly_user.ps1, db/create_finance_bi_user.ps1, db/create_agent_user.ps1, db/create_api_user.ps1
PS> #   (each runs ALTER ROLE … PASSWORD for an existing login — read its header for where the value comes from),
PS> #   and for MongoDB: .\db\mongo\run.ps1 001_create_app_user.js / 005_create_reader_user.js (update the user's password)
PS> uv run python dev/tools/secrets_scan.py        # no WEAK line, 0 findings
```
Power BI Desktop asks for the new `ports_bi` password on the next refresh.
**An environment:** set the new value in its Key Vault, delete `/opt/portpilot/env/<env>.env` on the VM, then
```bash
$ bash ops/deploy/render_env.sh production /opt/portpilot/env/production.env
$ python3 pipelines/scripts/ops/Backup.py secure --stack portpilot-production --env-file /opt/portpilot/env/production.env
$ $C up -d --force-recreate api scheduler web
```
`secure` also disables every API login: re-enable the real people with `Api_admin.py enable --employee <id>`.
External keys (Gemini, Groq, …): create the new key at the provider, set it in the vault, recreate, then delete the
old key at the provider.

## 11. Secrets in the git history (owner)

```powershell
PS> docker run --rm -v "${PWD}:/repo:ro" zricethezav/gitleaks:v8.28.0 git /repo --config /repo/.gitleaks.toml --redact --no-banner
```
Every finding = a value to rotate (§10), even if the file was deleted later — history is public to anyone who can
clone. Rewriting history is not needed once the value is rotated. The working tree is scanned by the CI
(`dev/tools/secrets_scan.py`) and by `gitleaks dir` (0 leaks on 2026-11-17).

## 12. Observability

- **Sentry:** events carry `environment` = `staging` / `production` (from `PORTPILOT_ENV`). Sentry → Alerts → the
  existing "new issue" rule: add the filter "environment equals production" and a second rule for staging (or none).
  The cron monitor `nilegate-weekly-pack` (Monday 10:30 Cairo) now receives check-ins from the scheduler container.
  **Uptime:** Sentry → Uptime → add `https://portpilot.<your domain>/healthz` (expects 200; 503 = the API is not
  ready). Turn on "Prevent Storing of IP Addresses" (THREAT_MODEL LLM02 gap).
- **LangSmith:** project `nilegate-agents`; traces of an environment carry the tag `env:staging` / `env:production`.
- **Logs:** `$C logs --since 1h api` (json-file, 10 MB × 5 per service); the API's access log and the scheduler's
  journal live on the `reports` volume: `$C exec api tail -n 50 reports/_log/api.jsonl`,
  `$C exec api tail -n 20 reports/_log/scheduler.jsonl`.
- **Health:** `/healthz` (public, the web + the API's readiness); inside: `/api/v1/health/status` (open on the internal
  network), `/api/v1/health/ready` (a token: components and today's LLM counts).

## 13. Paid models (when a trigger fires — ADR-045 note)

Triggers: real or personal data (mandatory before it arrives), or the shared daily quota exhausted two days in a row.
1. Google AI Studio → the project of the production key → enable billing (the same model ids, higher limits, inputs
   not used for training).
2. In `pipelines/agents/models.toml`, on `[models.flash_lite]`: raise `limits` to the paid tier's, add
   `price_usd_per_mtok` and `max_usd_per_day` (ADR-045 amendment 4); `docs/model_swap.md`: probe → fake-model checks →
   a small real run → ADR-052 → deploy.

## 14. Sign-in rules (for the people you create)

Passwords ≥ 12 characters (enforced by `Api_admin.py`); 5 wrong passwords in a row lock the login for 15 minutes;
behind the proxy one address gets 10 failed sign-ins per 10 minutes; a session lasts 8 hours (httpOnly, Secure,
SameSite=Strict cookie); sign-out revokes the token. `Api_admin.py reset / disable / enable / list`.

## 15. Production gates (S7) — all before the first production deploy

**Public staging (testers), ADR-071 amendment 1:** before you share staging, check the first box, the second, the
sixth and the last one below. Also give one login to each tester (§6, `Api_admin.py create`) and give staging its
own new model keys, not `--copy-keys`.

- [ ] the CI of the tag is green (the `Deploy` workflow refuses otherwise);
- [ ] staging deployed from the same tag and `Deploy_smoke.py` passed there, with a real sign-in (`--email`, the
      password in `SMOKE_PASSWORD`);
- [ ] **your review of the skill `arrival-advice`** (`pipelines/agents/skills/arrival-advice/SKILL.md`, then
      `reviewed_by_owner: yes`);
- [ ] **one real revise on a staging pack** (the targeted-revise plan's open "uncertain" point): Reports → the
      waiting pack → Request "revise …" → confirm → the re-drafted slides shown → approve or reject;
- [ ] a restore drill on staging (§9) since the last migration;
- [ ] the local credentials rotated (§10) and the history scan (§11) clean or its values rotated;
- [ ] the Sentry uptime monitor and the production alert filter set (§12).
