#!/usr/bin/env bash
# Deploy one git ref to one environment on its VM (Staging readiness plan P10, ADR-071). Run by the `Deploy` GitHub
# workflow through `az vm run-command` (as root, which switches to the `portpilot` user), or by the owner over SSH:
#   sudo -u portpilot /opt/portpilot/repo/ops/deploy/deploy.sh staging v2026.11.17 [--apply-migrations]
# Steps: check out the ref → render the env file from Key Vault (if missing) → build both images tagged with the
# commit → back up the running stack → start the stores → migrations (status; apply only with --apply-migrations,
# which the workflow passes after the owner's approval) → start everything → smoke test → on a failed smoke, put the
# previous images back (the database is never rolled back automatically: restore with Backup.py, runbook §Restore).
# Exit: 0 deployed; 2 bad arguments; 3 migrations pending without approval; 4 an applied migration was edited;
#       5 smoke failed (previous images restored); other = the failing command's code.
set -euo pipefail

ENV_NAME="${1:-}"; REF="${2:-}"; APPLY="${3:-}"
case "$ENV_NAME" in staging|production) ;; *) echo "usage: deploy.sh staging|production <git-ref> [--apply-migrations]"; exit 2 ;; esac
[[ "$REF" =~ ^[A-Za-z0-9._/-]{1,100}$ ]] || { echo "bad ref"; exit 2; }
[[ -z "$APPLY" || "$APPLY" == "--apply-migrations" ]] || { echo "bad third argument"; exit 2; }

APP=/opt/portpilot
REPO="$APP/repo"
ENV_FILE="$APP/env/$ENV_NAME.env"
STATE="$APP/state"
mkdir -p "$STATE" "$APP/backups" "$APP/env"
cd "$REPO"

echo "== 1. source $REF"
git fetch --quiet --tags origin
git checkout --quiet --detach "$REF"
TAG="$(git rev-parse --short=12 HEAD)"

echo "== 2. env file"
if [[ ! -s "$ENV_FILE" ]]; then
  bash "$REPO/ops/deploy/render_env.sh" "$ENV_NAME" "$ENV_FILE"
fi
chmod 600 "$ENV_FILE"
STACK="$(grep -E '^PORTPILOT_STACK=' "$ENV_FILE" | cut -d= -f2-)"
ORIGIN="$(grep -E '^PORTPILOT_WEB_ORIGIN=' "$ENV_FILE" | cut -d= -f2-)"
export PORTPILOT_TAG="$TAG"
compose() { docker compose -f deploy/compose.yaml --env-file "$ENV_FILE" "$@"; }

echo "== 3. images portpilot-api:$TAG, portpilot-web:$TAG"
compose build --pull=false api web
PREV_TAG="$(cat "$STATE/$ENV_NAME.tag" 2>/dev/null || true)"

echo "== 4. backup of the running stack"
if docker inspect "$STACK-postgres" >/dev/null 2>&1; then
  python3 pipelines/scripts/ops/Backup.py backup --stack "$STACK" --env-file "$ENV_FILE" --out "$APP/backups"
  python3 pipelines/scripts/ops/Backup.py prune --out "$APP/backups"
else
  echo "no stack yet: first deploy (seed it with Backup.py restore, runbook §Seed)"
fi

echo "== 5. stores + migrations"
compose up -d postgres mongo qdrant
set +e
compose --profile ops run --rm ops python pipelines/scripts/ops/Migrate.py status
RC=$?
set -e
if [[ $RC -eq 4 ]]; then echo "an applied migration was edited: stop"; exit 4; fi
if [[ $RC -eq 3 ]]; then
  if [[ "$APPLY" != "--apply-migrations" ]]; then
    echo "migrations are pending: re-run the workflow with apply_migrations (the owner approves that step)"; exit 3
  fi
  compose --profile ops run --rm ops python pipelines/scripts/ops/Migrate.py apply --yes
elif [[ $RC -ne 0 ]]; then
  echo "Migrate.py status failed ($RC)"; exit "$RC"
fi

echo "== 6. start"
compose up -d --remove-orphans

echo "== 7. smoke"
if python3 pipelines/scripts/ops/Deploy_smoke.py --origin "$ORIGIN" --stack "$STACK"; then
  echo "$TAG" > "$STATE/$ENV_NAME.tag"
  echo "deployed $REF ($TAG) to $ENV_NAME"
else
  if [[ -n "$PREV_TAG" ]]; then
    echo "smoke failed: back to $PREV_TAG"
    PORTPILOT_TAG="$PREV_TAG" compose up -d api scheduler web
  fi
  exit 5
fi
