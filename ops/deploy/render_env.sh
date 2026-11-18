#!/usr/bin/env bash
# Render an environment's env file from Azure Key Vault (Staging readiness plan P4, ADR-071).
#   render_env.sh staging /opt/portpilot/env/staging.env
# The VM signs in with its managed identity (no secret on disk to fetch secrets); the identity needs the Key Vault
# role "Key Vault Secrets User" on the vault only. Each variable KEY of deploy/env.example is the secret
# "<env>-<KEY with _ as ->" (e.g. staging-PG-API-PASSWORD); a missing secret is written empty (optional keys) and
# listed at the end. The vault name comes from /opt/portpilot/env/vault (one line).
set -euo pipefail
ENV_NAME="$1"; OUT="$2"
VAULT="$(cat /opt/portpilot/env/vault)"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
az login --identity --allow-no-subscriptions --output none
umask 077
TMP="$(mktemp)"
missing=()
while IFS= read -r line; do
  [[ "$line" =~ ^([A-Z_]+)= ]] || continue
  key="${BASH_REMATCH[1]}"
  name="$ENV_NAME-${key//_/-}"
  if value="$(az keyvault secret show --vault-name "$VAULT" --name "$name" --query value --output tsv 2>/dev/null)"; then
    printf '%s=%s\n' "$key" "$value" >> "$TMP"
  else
    printf '%s=\n' "$key" >> "$TMP"
    missing+=("$key")
  fi
done < "$REPO/deploy/env.example"
mv "$TMP" "$OUT"
chmod 600 "$OUT"
echo "rendered $OUT from $VAULT; not in the vault (empty): ${missing[*]:-none}"
