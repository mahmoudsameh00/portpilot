# Plan — Azure staging: the one public environment for testers (owner steps O4–O10)

**Status: APPROVED (2026-11-22)** — the owner: "موافق على الكل" (the plan and every recommendation of §3, D-AZ-1 …
D-AZ-6). The local readiness audit and the D-AZ-4 skill review are recorded in §7. Azure provisioning is still
pending. The owner supplies the staging hostname during A0.

## 1. Goal and done-when

PortPilot reachable at `https://staging.portpilot.<domain>` for a small group of testers, each with their own login,
running the same Compose stack as the local rehearsal, with its own secrets and model keys, nightly backups, Sentry
and LangSmith tagged `staging`, and a repeatable GitHub deploy.

**Done when:** `Deploy_smoke.py` passes against the public origin with a real sign-in; the GitHub `Deploy` workflow
has deployed one tag end to end; one nightly backup reached Blob storage; the Sentry uptime monitor is green; the A11
pre-share gates are ticked; the tester guide link is shared; the VM can be deallocated and started again with the
site coming back (cost control proven).

## 2. Context and decisions already made

- ADR-071 (one Linux VM, one Compose stack, Caddy TLS, Key Vault, schedules in a container) and **ADR-071 amendment 1**
  (2026-11-21): **one public environment, `staging`; `production` deferred** until real users or real data.
- Runbook: `docs/deploy/RUNBOOK.md` §1–§15 (written for production; §3 corrected on 2026-11-21 with the owner's Key
  Vault data role and `az storage container-rm create`). This plan is the staging instance of §2–§8 and §12.
- Size `Standard_B2ms` (2 vCPU, 8 GiB) + a 64 GiB Standard SSD data disk, deallocated between test sessions.
- One login per tester (`Api_admin.py create`), on an existing employee of the right role / department.
- The tester guide: the owner's private artifact "Try PortPilot", shared from its Share menu.
- The owner runs the deployment commands in PowerShell on the PC (`PS>`) and bash on the VM (`$`). Review the
  output at each checkpoint before continuing. Keep credentials in the password manager or vault.

## 3. Decisions approved on 2026-11-22

| # | Decision | Recommendation | Why |
|---|---|---|---|
| D-AZ-1 | Region | `westeurope` (fallback `northeurope`) | close to Cairo; B-series usually open to free-trial subscriptions; A1 checks it |
| D-AZ-2 | Domain | a subdomain the owner already controls: `staging.portpilot.<domain>` | Caddy needs a real name for Let's Encrypt; no Azure DNS zone needed |
| D-AZ-3 | Model keys for staging | **new** Gemini / Groq / OpenRouter / Jina / Tavily / LangSmith keys (not `--copy-keys`) | testers never spend the development quota; one environment can be revoked alone (RUNBOOK §5) |
| D-AZ-4 | The skill `arrival-advice` | review it **before sharing staging** (50 lines) | testers see its output in Voyages and Ask; every other skill is reviewed |
| D-AZ-5 | SSH | from the owner's IP only (NSG rule), with `az vm run-command` as the fallback when the IP changes | RUNBOOK §3 |
| D-AZ-6 | Budget alert | a Cost Management budget of USD 50 / month with e-mail at 50 % / 80 % / 100 % | the free credit ends after 30 days; an alert before a surprise bill |

## 4. Phases

Each phase lists its commands and the evidence to review before starting the next phase. Names used throughout:

```powershell
PS> $E="staging"; $RG="portpilot-$E"; $LOC="westeurope"; $VM="portpilot-$E"; $KV="portpilot-$E-kv"; $SA="portpilot${E}bk"
```
(set again in every new PowerShell window; `$LOC` = the D-AZ-1 answer.)

### Phase A0 — Before anything costs money

1. Azure pricing calculator: `Standard_B2ms` (Linux) + 64 GiB Standard SSD + a Standard public IP, in `$LOC`; note the
   monthly figure for 24/7 and for ~40 h / month (deallocated otherwise).
2. Portal → Cost Management → Budgets → New: D-AZ-6.
3. The domain's DNS panel open (A record added in A3).
4. New provider keys created per D-AZ-3 (kept in the password manager, never in chat).
5. **Done 2026-11-22.** The owner reviewed the arrival-advice skill. The changes and live check results are in §7.

**Cost estimate, 2026-11-22.** West Europe USD retail rates give a base of **$14.69/month at 40 VM hours** or
**$80.93/month at 730 VM hours**. Linux B2ms is $0.096 per running hour. Both scenarios retain a 32 GiB Standard SSD
OS disk ($2.40/month), the 64 GiB Standard SSD data disk ($4.80/month) and one static Standard IPv4 address
($0.005/hour for 730 hours). The estimate excludes backup storage, disk transactions, egress, Key Vault operations,
tax and subscription credits. Confirm the subscription estimate and budget at A0.
[Microsoft retail rates](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices)

**Check:** the owner confirms 1–5 in words (no figures needed in chat beyond the monthly estimate if he wants it checked).

### Phase A1 — Read-only checks (no cost)

```powershell
PS> winget install Microsoft.AzureCLI          # if `az version` fails; then reopen PowerShell
PS> az login
PS> az account show -o table
PS> az vm list-skus --location $LOC --size Standard_B2ms --all -o table
PS> az vm list-usage --location $LOC -o table | Select-String "Total Regional vCPUs|Standard BS Family"
PS> az keyvault check-name --name $KV -o table
PS> az storage account check-name --name $SA -o table
PS> foreach ($p in "Microsoft.KeyVault","Microsoft.Storage","Microsoft.Compute","Microsoft.Network") { "$p " + (az provider show -n $p --query registrationState -o tsv) }
```
**Check:** subscription `Enabled`; `Restrictions` = `None` for B2ms; BS family and regional vCPU limits ≥ 2; both
names available (else add two letters, e.g. `portpilot-staging-kv2`, and use them below); the four providers
`Registered` (else `az provider register -n <name>` and wait). Subscription / tenant ids are not sent to chat.

### Phase A2 — Azure resources (cost starts here)

```powershell
PS> az group create -n $RG -l $LOC
PS> az vm create -g $RG -n $VM --image Ubuntu2404 --size Standard_B2ms --admin-username portpilotadmin --generate-ssh-keys --public-ip-sku Standard --storage-sku StandardSSD_LRS --os-disk-size-gb 32 --data-disk-sizes-gb 64 --assign-identity --nsg-rule NONE
PS> az network nsg rule create -g $RG --nsg-name "${VM}NSG" -n web --priority 100 --access Allow --protocol Tcp --destination-port-ranges 80 443
PS> az network nsg rule create -g $RG --nsg-name "${VM}NSG" -n ssh-owner --priority 110 --access Allow --protocol Tcp --destination-port-ranges 22 --source-address-prefixes "<your public IP>/32"
PS> az keyvault create -g $RG -n $KV --enable-rbac-authorization true
PS> $KVID = az keyvault show -n $KV --query id -o tsv; $PRINCIPAL = az vm show -g $RG -n $VM --query identity.principalId -o tsv
PS> az role assignment create --assignee $PRINCIPAL --role "Key Vault Secrets User" --scope $KVID
PS> az role assignment create --assignee (az ad signed-in-user show --query id -o tsv) --role "Key Vault Secrets Officer" --scope $KVID
PS> az storage account create -g $RG -n $SA --sku Standard_LRS --kind StorageV2 --access-tier Cool --min-tls-version TLS1_2 --allow-blob-public-access false
PS> az storage container-rm create --storage-account $SA -g $RG -n backups
PS> az role assignment create --assignee $PRINCIPAL --role "Storage Blob Data Contributor" --scope (az storage account show -n $SA --query id -o tsv)
PS> az vm show -d -g $RG -n $VM --query "{ip:publicIps, state:powerState}" -o table
PS> az resource list -g $RG -o table
```
Portal → the storage account → Lifecycle management: delete `backups/*` older than 35 days.

**Check:** `az vm create` ends with `"powerState": "VM running"`; the resource list holds exactly the VM, its OS and
data disks, NIC, NSG, public IP, VNet, the vault and the storage account; three role assignments made. A failure
mid-way: stop and send the error; never re-run `az vm create` blindly (it may leave a half-built group; the clean-up is
`az group delete -n $RG`, asked first).

### Phase A3 — DNS

The domain's panel: an **A record** `staging.portpilot` → the VM's IP (TTL 300).
```powershell
PS> Resolve-DnsName staging.portpilot.<domain> -Type A
```
**Check:** the answer is the VM's IP (may take minutes). Caddy fetches the certificate only once this resolves.

### Phase A4 — VM bootstrap (RUNBOOK §4)

```powershell
PS> ssh portpilotadmin@<vm ip>
```
On the VM:
```bash
$ sudo mkfs.ext4 /dev/disk/azure/scsi1/lun0 && sudo mkdir -p /opt/portpilot && \
  echo "/dev/disk/azure/scsi1/lun0 /opt/portpilot ext4 defaults,nofail 0 2" | sudo tee -a /etc/fstab && sudo mount -a
$ curl -fsSL https://get.docker.com | sudo sh
$ curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
$ sudo useradd --system --create-home --home-dir /opt/portpilot/home --groups docker portpilot
$ sudo mkdir -p /opt/portpilot/{env,state,backups} && sudo chown -R portpilot: /opt/portpilot
$ echo '{"data-root": "/opt/portpilot/docker"}' | sudo tee /etc/docker/daemon.json && sudo systemctl restart docker
$ sudo -u portpilot ssh-keygen -t ed25519 -N "" -f /opt/portpilot/home/.ssh/id_ed25519
$ sudo cat /opt/portpilot/home/.ssh/id_ed25519.pub
```
GitHub → `mahmoudsameh00/portpilot` → Settings → Deploy keys → Add (read-only) with that public key. Then:
```bash
$ sudo -u portpilot git clone git@github.com:mahmoudsameh00/portpilot.git /opt/portpilot/repo
$ echo portpilot-staging-kv | sudo -u portpilot tee /opt/portpilot/env/vault      # the D-AZ name if it changed
$ df -h /opt/portpilot && docker info --format '{{.DockerRootDir}}' && docker compose version && az version -o tsv | head -1
```
**Check:** `/opt/portpilot` on the 64 GiB disk; Docker root `/opt/portpilot/docker`; compose and az present; the clone
succeeded (only the public key is sent to chat, never the private one).

### Phase A5 — Secrets into Key Vault (RUNBOOK §5, staging)

```powershell
PS> uv run python ops/deploy/new_env.py staging --site staging.portpilot.<domain> --tls <your email>
```
Open `deploy/env/staging.env` in the editor and fill the empty keys: the D-AZ-3 keys (`GEMINI_API_KEY`,
`JINA_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`, `TAVILY_API_KEY`, `LANGSMITH_API_KEY`), `SENTRY_DSN` (the same
DSN is fine: events carry `environment=staging`), `PACK_RUN_AS` (a Finance manager's employee id) and `WATCH_RUN_AS`
(an Operations manager's). Then:
```powershell
PS> Get-Content deploy/env/staging.env | Where-Object { $_ -match '^([A-Z_]+)=(.+)$' } | ForEach-Object {
      $name = 'staging-' + ($Matches[1] -replace '_','-'); $val = $Matches[2]
      az keyvault secret set --vault-name $KV --name $name --value $val --output none }
PS> az keyvault secret list --vault-name $KV --query "length(@)"
PS> Remove-Item deploy/env/staging.env
```
**Check:** the script's list of empty keys is empty after filling; the secret count equals the number of non-empty
lines; the local file is gone (the vault is the copy of record). A Forbidden error = the "Secrets Officer" assignment
of A2 has not propagated yet: wait two minutes and retry.

### Phase A6 — First deploy and seed (RUNBOOK §6, staging)

At A6 select the reviewed staging candidate on remote `master` and confirm CI passed for that exact commit.
Run the local rehearsal (RUNBOOK §1) on that revision, then tag that same commit
(`git tag v0.1.0-staging <checked-commit>`), push the tag and wait for its CI to pass. Make a fresh backup with
the model while the local stores are running:
```powershell
PS> uv run python pipelines/scripts/ops/Backup.py backup --stack local --with-models
PS> scp -r backups/local_<stamp> portpilotadmin@<vm ip>:/tmp/seed
```
On the VM:
```bash
$ sudo mv /tmp/seed /opt/portpilot/backups/ && sudo chown -R portpilot: /opt/portpilot/backups
$ sudo -iu portpilot
$ cd /opt/portpilot/repo && git fetch --tags && git checkout <tag>     # the tag made at the start of this phase
$ bash ops/deploy/render_env.sh staging /opt/portpilot/env/staging.env
$ export PORTPILOT_TAG=$(git rev-parse --short=12 HEAD); C="docker compose -f deploy/compose.yaml --env-file /opt/portpilot/env/staging.env"
$ $C build api web && $C up -d postgres mongo qdrant && $C create api
$ python3 pipelines/scripts/ops/Backup.py restore /opt/portpilot/backups/seed --stack portpilot-staging --env-file /opt/portpilot/env/staging.env
$ python3 pipelines/scripts/ops/Backup.py secure --stack portpilot-staging --env-file /opt/portpilot/env/staging.env
$ tar -xzf /opt/portpilot/backups/seed/files/runtime.tar.gz -C /tmp models && \
  $C --profile ops run --rm -v /tmp/models:/seed:ro ops python -c "import shutil; shutil.copytree('/seed/onnx/bge-m3', '/app/models/onnx/bge-m3', dirs_exist_ok=True)" && rm -rf /tmp/models
$ $C --profile ops run --rm ops python pipelines/scripts/ops/Migrate.py status && \
  $C up -d && echo $PORTPILOT_TAG > /opt/portpilot/state/staging.tag
$ $C ps
$ python3 pipelines/scripts/ops/Deploy_smoke.py --origin https://staging.portpilot.<domain> --stack portpilot-staging
```

**Check:** `render_env.sh` lists no missing required key; `restore` reports every count and digest equal; `secure`
re-keyed the logins and disabled the inherited API logins. A restore of the rehearsed seed has 031 recorded and zero
pending migrations (exit 0). If status exits 3, pause before starting the services, review the listed migrations
with the owner, apply the approved set with `Migrate.py apply --yes` and recheck status. Exit 4 requires investigating
a changed migration. Start the services after status is clear. Verify that every service with a health check is
healthy and the smoke passes (TLS, `/healthz` 200, `/api/*` and `/docs` 404).

### Phase A7 — Logins and a real sign-in

```bash
$ $C --profile ops run --rm ops python pipelines/scripts/api/Api_admin.py list
$ $C --profile ops run --rm ops python pipelines/scripts/api/Api_admin.py create --employee <your test employee>
```
On the PC:
```powershell
PS> $env:SMOKE_PASSWORD = Read-Host -AsSecureString "password" | ConvertFrom-SecureString -AsPlainText
PS> uv run python pipelines/scripts/ops/Deploy_smoke.py --origin https://staging.portpilot.<domain> --email <that login>
PS> Remove-Item Env:SMOKE_PASSWORD
```
(`ConvertFrom-SecureString -AsPlainText` needs PowerShell 7; in Windows PowerShell 5.1, set `$env:SMOKE_PASSWORD` by
typing it in the window — never in chat.)

**Check:** the smoke with sign-in passes; the owner signs in from the browser and sees the menu of that role.

### Phase A8 — GitHub deploy workflow (RUNBOOK §7, staging only)

GitHub reported the repository as public on 2026-11-22. Required reviewers are available for public repositories
on GitHub Free. Neither staging environment was listed yet. [GitHub deployment protection rules](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments#required-reviewers)

1. Entra ID → App registrations → New "portpilot-github-deploy" → Federated credentials → GitHub Actions, organization
   `mahmoudsameh00`, repository `portpilot`, entity Environment, names `staging` and `staging-migrations`.
2. Role **Virtual Machine Contributor** on `$RG` for that app.
3. GitHub → Settings → Environments: `staging`, `staging-migrations`, each with the owner as required reviewer.
   Allow self-review so the owner who starts the workflow can also approve it.
4. Repository variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`; environment variables on
   `staging`: `AZURE_RESOURCE_GROUP` = `portpilot-staging`, `AZURE_VM_NAME` = `portpilot-staging`.
5. Actions → Deploy → Run workflow: environment `staging`, ref = the same tag, `apply_migrations` off.

**Check:** the gate resolves the tag to a commit and verifies that its latest push run of `ci.yml` completed
successfully. The owner approves the deployment, the smoke passes and `staging.tag` on the VM matches
`git rev-parse --short=12 HEAD` for that commit. This is the first live use of the deploy workflow.

### Phase A9 — Nightly backup (RUNBOOK §8, staging names)

The two systemd units of §8 with `portpilot-staging`, `/opt/portpilot/env/staging.env` and the account `$SA`
(`portpilotstagingbk`). Then one manual run:
```bash
$ sudo systemctl start portpilot-backup.service && journalctl -u portpilot-backup.service -n 30 --no-pager
$ systemctl list-timers portpilot-backup.timer
```
**Check:** a backup folder with its manifest; the Blob container lists it (`az storage blob list --account-name $SA -c
backups --auth-mode login -o table`, after giving the owner "Storage Blob Data Reader"); `Persistent=true` makes a
deallocated night run on the next start.

### Phase A10 — Observability (RUNBOOK §12)

Sentry: the "new issue" alert filtered `environment equals staging`; Uptime → `https://staging.portpilot.<domain>/healthz`
(paused while the VM is deallocated, or accept its alerts); Settings → "Prevent Storing of IP Addresses" on. LangSmith:
a trace tagged `env:staging` after the first question.

**Check:** a test error from the VM appears under `staging`; the uptime check is green; one trace with the tag.

### Phase A11 — Pre-share gates, testers, cost control

- [ ] the tag's CI green; the smoke with a real sign-in passed (A7, A8);
- [x] O1 / O2 done (2026-11-18): local credentials rotated, history scan clean;
- [ ] Sentry uptime + IP storage off (A10);
- [x] D-AZ-4: the owner reviewed the `arrival-advice` skill on 2026-11-22 (§7);
- [ ] one login per tester (A7 commands), ≤ 10 people while on the free model quota;
- [ ] the tester guide shared with each tester, with the link and their login;
- [ ] cost control proven once: `az vm deallocate -g $RG -n $VM`, then `az vm start -g $RG -n $VM`, the site back
      without any command on the VM (`restart: unless-stopped`), the IP unchanged (static Standard IP).

**Check:** each box ticked with its evidence in §7.

## 5. Rollback and teardown

- A bad deploy: the workflow with the previous tag; `deploy.sh` already restores the previous images on a failed smoke.
- A bad migration or lost data: RUNBOOK §9 restore.
- Stop paying entirely: `az group delete -n portpilot-staging` (asked first: it deletes the VM, disks, vault — soft-
  deleted 90 days — and the backups). The local machine keeps everything.

## 6. What changes in the repository

The readiness changes include the reviewed arrival-advice skill, its Validator and tests, the checkpoint and the
audit documents. On 2026-11-22 the owner brought the candidate push forward so remote CI can run during Azure
preparation. First exercise the reviewed skill in the live local web app, then publish the reviewed files on
`master`. Create the staging tag at A6. Record deployment evidence in §7 and archive the plan after A11.

## 7. Progress / deviations

(filled phase by phase: date, what ran, the evidence, deviations, next step)

### Live web acceptance, 2026-11-23

The owner requested a live web test before the candidate push. The Operations user submitted two pilot-boarding
requests. Vessel 28 returned a catch-up option. For vessel 38 the JIT ETA was 07:47 UTC, the planning target was
07:45 and the requested time was 09:45. The writer called the planning target met. The validator now reserves that
comparison for code when rounding changes the displayed minute. A further check rejects a planned wait described
as the time before the port deadline. The normalizer can copy explicitly cited UTC fields. Evaluation cleanup uses
a unique namespace per run to preserve saved advice in the application.
Vessel 38's final replay returned two options, three reasons, two provider calls and zero cache hits. The web
result persisted on reload. Its JIT option reached SAJUB at 07:47 with zero lateness; keeping speed incurred
55.1 hours of planned waiting. The separate eight-case model check encountered provider overload and a daily
fallback limit. The owner raised further Voyage Watch issues before publication.

### Voyage Watch corrections before publication — IMPLEMENTED (2026-11-23)

The owner approved all five corrections, removal of the standalone arrival form, and keeping Voyages in navigation.

The latest saved run (replay clock 2026-09-13 00:00 UTC, run 2) contains 219 ETA-board vessels. Of these, 175
have no RTA, 41 have timing alerts and 3 have an RTA without a timing alert. Before correction all 219 had an arrival action.
Three of seven high alerts are weather alerts on vessels without an RTA. Of 17 late alerts, 12 have only the current
speed available. Vessels 2, 351 and 352 lose a real one-, four- or three-minute improvement because the ranking compares
rounded delay. Vessel 157 has computed options but the writer failed validation. Fifteen of the 16 saved runs lack
embedded arrival advice. Historic files are the record of what their run produced.

1. Present arrival advice in the context of a vessel's timing alert and its watch run. Remove the standalone request
   panel from the watch and the generic action for every ETA row. Keep weather alerts useful as weather alerts.
   Use the full run for eligibility independently of the severity filter. Preserve access checks and saved links.
2. Rank all-late options by actual estimated arrival before the cost tie-break. When an allowed higher speed reduces
   delay, show how much it recovers. When no speed can recover time, show the earliest ETA and advise notifying the
   port to agree a revised time. Distinguish making the deadline from merely reducing lateness.
3. Give eligible vessels a usable result from the run's checked option data if the writer is unavailable or its
   narrative fails validation. Label the computed basis and preserve risk uncertainty. For older snapshots use only
   facts available at their own clock; surface a specific operational next action if essential inputs are missing.
4. Keep the operational brief, ETA, clock and alerts visible. Remove the brief's internal provenance, diagnostics,
   file paths, model counts and the matching browser-response fields. Retain internal records for operators.
5. Validate all timing alerts in the latest saved run and fixtures covering older runs, a missing RTA, stationary
   vessels, weather-only and mixed alerts, recoverable and unrecoverable delay, and provider failure. Verify browser
   payloads, access restrictions, mobile navigation and the real signed-in page before publishing.

**Implementation record.** The right-hand vessel-ID form was removed. Voyages remains in navigation. The signed-in
replay showed 24 JIT and 17 late decisions, including all 41 after filtering the alert list to high severity.
Weather-only vessels 234, 339 and 420 had no arrival action. Vessel 351 could recover four minutes. Twelve late
vessels had no faster option and were directed to contact the port. The browser payload omitted the brief's
internal fields. Mobile verification at 375 pixels showed no horizontal overflow. Phases 1–7 passed. In a fresh
real-model repeat the validator accepted 6/8 written recommendations. The English supervisor response failed
validation, the Arabic response succeeded and the watch brief passed. The earlier staging acceptance stands.
All 12 desktop and mobile Voyage Watch tests passed. The isolated application suite passed all 17 tests, including
role-based access, the watch and saved advice ownership. Its setup and teardown now use the fixture's current path.

### Readiness audit 2026-11-22 (before Phase A0; no Azure command run)

**D-AZ-4 done (2026-11-22).** The owner read the skill `arrival-advice` section by section (explained in Egyptian
Arabic: the five options computed in `pipelines/agents/tools/arrival.py`, the rule, the risk overrule, the slots) and
chose "edits + the risk's direction": the skill text (the RTA's location, the tie order, "RTA" = `rta_utc` only, the
risk directions) and a code rule in the Validator (a storm → an earlier arrival than the rule's, never the Cape; a
Suez drop ≤ −20 % → the Cape only). `reviewed_by_owner: 2026-11-22`. ADR-052's two real runs of
`Arrival_advice_check.py`: run 1 7 / 8 (Gemini 503 "high demand" → the fallback `nemotron` wrote most advices; one
`output_invalid` on its evidence-id format), run 2 8 / 8; every passing advice = the rule; the baseline 8 / 8. Record:
ADR-070 note 2026-11-22. Deviation: this is a code change (§6 expected docs only), with its checks.

**Checks on 2026-11-22 (`master` and the local readiness changes)**

| Check | Result |
|---|---|
| Local and remote `master` before the candidate commit | Both pointed at `4f3c600` on 2026-11-22. GitHub reported success for `checks`, `images`, `api-integration` and `web` on that commit. |
| CI job `checks`, 16 steps (`uv sync --frozen` → `path_refs_check.py`), on the owner's `.env` instead of the CI's empty copy | ✅ 16 / 16 |
| `npm --prefix web run check` (allow-list, Orval, tsc, eslint, prettier, audit, Playwright) | ✅ 7 / 7 |
| `Finance_views_check.py` (full data) | ✅ Phases 1–8 + Final |
| `Stage2_tools_check.py` (full data) | ✅ S1–S8, pending none |
| `Tools_check.py` | ✅ S1–S9, pending none |
| `Scheduler_check.py` (fake models) | ✅ 6 / 6 |
| `Voyage_watch_check.py` (Phase 6 on cached replies, 0 fresh calls) | ✅ 9 phases, pending none |
| `Arrival_advice_check.py` Phases 1–7 (0 model calls), after the edits | ✅ (Phase 4: 60 plants, 6 / 6 directions) |
| `Arrival_advice_check.py` Phase 8, two real runs (ADR-052) | run 1 ❌ 7 / 8 (fallback model, provider overload) · run 2 ✅ 8 / 8 |
| Owner's fresh Phase 8 retry (`EVAL_REPEAT=3`) | ❌ 6 / 8, 23 calls, 0 cache hits. Case 1 supplied an invalid evidence ID and case 7 cited unavailable evidence. All six accepted recommendations matched the rule. Both supervisor languages and the watch brief passed. The eight-case assertion failed. |
| `lint_ratchet.py` after the code edits | ✅ ruff 0, pyright 0 |
| Public-release file checks | `path_refs_check.py` passed on 648 text files. `secrets_scan.py` scanned 976 files with zero findings. |
| Local staging rehearsal (RUNBOOK §1, no `--copy-keys`) + `Deploy_smoke.py` | ✅ restore of today's stores (`local_20261122T142436Z`: 47,060 rows, 1,332,537 documents, 2,163 points; every count and digest equal), `secure`, migrations 0 pending, every service healthy, `Deploy_smoke.py` 15 / 15 ✅ (no sign-in: no tester login in the rehearsal); stopped with `down` (volumes kept) |

**Open points found (every source swept: ROADMAP, ARCHITECTURE labels and §10, THREAT_MODEL "Gap", decisions.md
notes, RUNBOOK §15, the archived plans from 2026-11-14 and their README)**

| Item | Source | Class |
|---|---|---|
| Commit and push the readiness changes | §4 A6, §6 | Updated owner decision (2026-11-22). Test the reviewed skill in the running web app before pushing the staging candidate. Tag the verified revision at A6. |
| Frontend error reporting to Sentry (F10) | Frontend plan F10 | Owner decision (2026-11-22). Defer browser error reporting until before production. During staging, testers report UI errors using the tester guide. API error reporting and A10 still apply. |
| Third live arrival-advice run | ADR-070, this audit | Closed under the owner's decision (2026-11-22). The retry scored 6 / 8. The earlier results are accepted for staging and the check retains its 8 / 8 threshold. |
| Deploy gate could count its own running job when the workflow and release tag shared a commit | A8, `.github/workflows/deploy.yml` | Fixed locally with owner approval. The workflow selects the latest push CI run for the exact commit and passes that SHA to the VM. `Deploy_check.py` passed all seven phases, including five gate scenarios. The same read-only query returned success for remote `4f3c600`. The live deployment is due at A8. |
| Sentry "Prevent Storing of IP Addresses" + the uptime monitor | THREAT_MODEL LLM02, ADR-071 amendment 1 (4) | blocks staging — planned (A10 / A11) |
| The tag's CI green, the smoke with a real sign-in, one login per tester, new model keys | RUNBOOK §15, D-AZ-3 | blocks staging — planned (A0, A6–A8, A11) |
| One real revise on a staging pack | Targeted-revise plan "uncertain", RUNBOOK §15 | blocks production (deferred with it, ADR-071 amendment 1) |
| A restore drill on staging since the last migration | RUNBOOK §15 / O11 | blocks production (deferred with it) |
| A global upload memory budget and the role-change test against saved answers ("before broader use") | Stabilization plan, security follow-ups | blocks production (staging: ≤ 10 named testers behind a login; per conversation 5 files / 300 chunks / 5 MB; the per-address sign-in limit of the BFF exists) |
| Injection screening knows known shapes only; the CLIs trust `--as` | THREAT_MODEL LLM01 / T3 | accepted residual risk (the injection set v3; the CLIs are owner-run) |
| Dependabot #19 onnxruntime 1.32.0 (from 2026-11-27, + the local upload check with bge-m3), #20 langsmith 0.15.0 (from 2026-12-01, + one real traced run) | ADR-063 note 2026-11-21 | deferred by an owner decision (cooldown) |
| @xyflow/react 13 (the padding is ready in `web/src/components/packs/RunGraph.tsx`) | ADR-063 note 2026-11-21 | deferred by an owner decision (majors = planned work) |
| The weekly pack's rewrite load (i3) | ROADMAP, owner 2026-11-15 | deferred by an owner decision |
| Long-term memory across conversations | ADR-065 (5), THREAT_MODEL T1 | deferred (its own ADR if ever) |
| DuckDB, Redis, a job queue, MinIO | ADR-018 + note 2026-11-04, ADR-071 | deferred until a measured trigger |
| `production` itself, paid models | ADR-071 amendment 1, ADR-045 note 2026-11-17 | deferred: real users or real data |
| Synthetic incidents / FBLs, causal-consistency checks, the shared event timeline | ROADMAP (PLANNED, optional), ARCHITECTURE §10 item 4 | optional future work, no plan — not a gate |
| The Stage 2 cache-only replay stopping at a03 | Model flexibility plan, open note | uncertain, evaluation tooling only (not runtime) — not a gate |
| The new reviewed-skill prompt changes the cache key of every arrival advice: the scheduled watch (10:30 / 22:30) makes fresh calls for its `jit` / `rta_late` vessels on its next runs | this audit | note (quota) |
| The Nov 22 live replies often used numeric placeholders for timestamps | this audit | The Nov 23 correction copies the UTC value of a cited summary field or option row. Phase 4 checks valid and invalid references. |
| ARCHITECTURE "End-to-end answer evaluation PLANNED / PROPOSED", "the LLM answer is PLANNED", "HTTP API IN PROGRESS, ADR-064 PROPOSED", "UNCERTAIN for ports / toll bands", ADR-018 row | ARCHITECTURE §2, §6, §7 | done but not marked / stale — **fixed 2026-11-22** |
| ROADMAP: Agents "IN PROGRESS", Evaluation "PARTIAL", Missing work "Agents phase", the ADR-018 list and the concurrency list, three stale Known issues | ROADMAP | done but not marked / stale — **fixed 2026-11-22** |
| THREAT_MODEL LLM10 / T8 Gap cells holding built controls | THREAT_MODEL | done but not marked — **fixed 2026-11-22** |
| RUNBOOK §15: the skill box ("`reviewed_by_owner: yes`") and the staging sentence | RUNBOOK §15 | **fixed 2026-11-22** (ticked with the date; the third box named) |
| ADR-064 stabilization note "pending full-data acceptance or pushed CI" | decisions.md | done later (CI `api-integration` green; Staging readiness j1 12 / 12) — historical note, left as written |
| Staging readiness O1–O3, O12 | 2026-11-18 plan | done (2026-11-18); O4–O10 = this plan; O11 = the production gates above |
