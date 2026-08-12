#!/usr/bin/env bash
# One-command installer for the Kubernetes deployment path.
#
# Automates everything that CAN be automated: creating the tender_eval database on the
# toolkit's Postgres, generating LITELLM_KEY_ENCRYPTION_KEY, minting ADMIN_LITELLM_KEY /
# LITELLM_WORKER_API_KEY from the gateway, building both images, creating the namespace +
# secret, deploying, bootstrapping the schema, and verifying health.
#
# Usage: ./install.sh   (run from this directory, install/k8s/)
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
REPO_ROOT="$(cd ../.. && pwd)"

GATEWAY_NS="genai-gateway"
GATEWAY_HOST="genai-gateway-postgresql.genai-gateway.svc.cluster.local"
GATEWAY_SVC_URL="http://genai-gateway-service.genai-gateway.svc.cluster.local:4000"
DB_NAME="tender_eval"
APP_NS="tender-bid"
INGRESS_HOST="ei-api.mg2.eglb.intel.com"   # substitute your own toolkit cluster_url if different
FRONTEND_BASE_PATH="/tender-eval"          # must match ingress.yaml's frontend path exactly

ENV_FILE="backend.env"
ENV_EXAMPLE="backend.env.example"

log()  { echo "==> $*"; }
die()  { echo "ERROR: $*" >&2; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "'$1' is required but not found on PATH."; }

get_env() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- ; }
set_env() {
  if grep -qE "^$1=" "$ENV_FILE"; then
    sed -i "s|^$1=.*\$|$1=$2|" "$ENV_FILE"
  else
    echo "$1=$2" >> "$ENV_FILE"
  fi
}

# --- 0. Preflight -----------------------------------------------------------------------
log "Preflight checks"
require_cmd kubectl
require_cmd jq
require_cmd python3

kubectl get namespace "$GATEWAY_NS" >/dev/null 2>&1 \
  || die "Namespace '$GATEWAY_NS' not found — deploy the enterprise agent toolkit first (Prerequisite 0 in the root README)."

if command -v nerdctl >/dev/null 2>&1; then
  BUILD_CMD="sudo nerdctl --namespace k8s.io build"
elif command -v docker >/dev/null 2>&1; then
  BUILD_CMD="docker build"
else
  die "Neither nerdctl nor docker found — see README.md step 1 for install options."
fi

# --- 1. backend.env: create from example if missing -----------------------------------
if [ ! -f "$ENV_FILE" ]; then
  log "Creating $ENV_FILE from $ENV_EXAMPLE"
  cp "$ENV_EXAMPLE" "$ENV_FILE"
fi

# --- 2. Auto-fill DATABASE_URL (create tender_eval DB if needed) -----------------------
if [ -z "$(get_env DATABASE_URL)" ]; then
  log "DATABASE_URL is blank — creating the '$DB_NAME' database on the toolkit's Postgres"
  PGPASS="$(kubectl get secret genai-gateway-postgresql -n "$GATEWAY_NS" \
    -o jsonpath='{.data.postgres-password}' | base64 -d)"
  [ -n "$PGPASS" ] || die "Could not read genai-gateway-postgresql secret — is the toolkit's GenAI Gateway deployed?"

  EXISTS="$(kubectl run psql-tender-eval-check-$$ -n "$GATEWAY_NS" --rm -i --restart=Never \
    --image=bitnamilegacy/postgresql:16 --env="PGPASSWORD=$PGPASS" -- \
    psql -h genai-gateway-postgresql -U postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" 2>/dev/null | tr -d '[:space:]')"

  if [ "$EXISTS" != "1" ]; then
    kubectl run psql-tender-eval-setup-$$ -n "$GATEWAY_NS" --rm -i --restart=Never \
      --image=bitnamilegacy/postgresql:16 --env="PGPASSWORD=$PGPASS" -- \
      psql -h genai-gateway-postgresql -U postgres -c "CREATE DATABASE $DB_NAME;"
    log "Created database '$DB_NAME'"
  else
    log "Database '$DB_NAME' already exists — reusing it"
  fi

  set_env DATABASE_URL "postgresql://postgres:${PGPASS}@${GATEWAY_HOST}:5432/${DB_NAME}"
else
  log "DATABASE_URL already set — leaving it alone"
fi

# --- 3. Auto-fill LITELLM_KEY_ENCRYPTION_KEY --------------------------------------------
if [ -z "$(get_env LITELLM_KEY_ENCRYPTION_KEY)" ]; then
  log "Generating LITELLM_KEY_ENCRYPTION_KEY"
  # Same format python -c "from cryptography.fernet import Fernet; ..." produces
  # (32 random bytes, urlsafe-base64 encoded) — done in stdlib so this script doesn't
  # need the `cryptography` package installed to run.
  KEY="$(python3 -c 'import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
  set_env LITELLM_KEY_ENCRYPTION_KEY "$KEY"
else
  log "LITELLM_KEY_ENCRYPTION_KEY already set — leaving it alone"
fi

# --- 4. Mint ADMIN_LITELLM_KEY / LITELLM_WORKER_API_KEY from the gateway ----------------
mint_litellm_key() {
  local alias="$1"
  local master
  master="$(kubectl get deploy -n "$GATEWAY_NS" genai-gateway-deployment \
    -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="LITELLM_MASTER_KEY")].value}')"
  [ -n "$master" ] || die "Could not read LITELLM_MASTER_KEY from genai-gateway-deployment."

  kubectl run "litellm-mint-${alias}-$$" -n "$GATEWAY_NS" --rm -i --restart=Never \
    --image=curlimages/curl -- \
    curl -s -X POST "$GATEWAY_SVC_URL/key/generate" \
      -H "Authorization: Bearer $master" \
      -H "Content-Type: application/json" \
      -d "{\"key_alias\": \"tender-eval-${alias}\"}" \
    | jq -r '.key'
}

if [ -z "$(get_env ADMIN_LITELLM_KEY)" ]; then
  log "Minting ADMIN_LITELLM_KEY from the gateway"
  set_env ADMIN_LITELLM_KEY "$(mint_litellm_key admin)"
else
  log "ADMIN_LITELLM_KEY already set — leaving it alone"
fi

if [ -z "$(get_env LITELLM_WORKER_API_KEY)" ]; then
  log "Minting LITELLM_WORKER_API_KEY from the gateway"
  set_env LITELLM_WORKER_API_KEY "$(mint_litellm_key worker)"
else
  log "LITELLM_WORKER_API_KEY already set — leaving it alone"
fi

# --- 5. Check for fields ONLY a human can provide ---------------------------------------
MISSING=()
for k in GMAIL_CLIENT_ID GMAIL_CLIENT_SECRET LOGFIRE_TOKEN; do
  [ -z "$(get_env "$k")" ] && MISSING+=("$k")
done
if [ ${#MISSING[@]} -gt 0 ]; then
  log "Everything automatable is filled in. Still need from you, in $ENV_FILE:"
  printf '  - %s\n' "${MISSING[@]}"
  echo
  echo "GMAIL_CLIENT_ID/SECRET: Google Cloud Console -> APIs & Services -> Credentials"
  echo "  -> Create Credentials -> OAuth client ID -> Desktop app"
  echo "  (https://console.cloud.google.com/apis/credentials)"
  echo "LOGFIRE_TOKEN: your Logfire project's write token (https://logfire.pydantic.dev)"
  echo
  echo "Fill those in, then re-run this script — everything above is safe to skip on the next run."
  exit 1
fi

# --- 6. Build both images ---------------------------------------------------------------
log "Building backend image"
( cd "$REPO_ROOT" && $BUILD_CMD -f pydantic_backend/Dockerfile -t tender-bid-backend:local . )

log "Building frontend image"
( cd "$REPO_ROOT" && $BUILD_CMD -f frontend/Dockerfile \
    --build-arg NEXT_PUBLIC_API_BASE_URL="https://${INGRESS_HOST}/tender-eval-api" \
    --build-arg NEXT_PUBLIC_BASE_PATH="$FRONTEND_BASE_PATH" \
    -t tender-bid-frontend:local . )

# --- 7. Namespace + secret (idempotent) --------------------------------------------------
log "Creating namespace and backend-env secret"
kubectl create namespace "$APP_NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n "$APP_NS" create secret generic backend-env \
  --from-env-file="$ENV_FILE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null

# --- 8. Deploy ---------------------------------------------------------------------------
log "Applying manifests"
kubectl apply -k .
kubectl -n "$APP_NS" rollout status deploy/backend --timeout=180s
kubectl -n "$APP_NS" rollout status deploy/frontend --timeout=180s

# --- 8b. Gmail token sync ----------------------------------------------------------------
# What CANNOT be automated: Google's OAuth consent screen requires a human to click "Allow"
# in a real browser logged into the target Gmail account — that's a deliberate security
# boundary, not a gap here. `flow.run_local_server()` (pydantic_backend/ingestion/gmail.py)
# needs an actual browser + loopback network access, which this cluster/script doesn't have.
#
# What CAN be automated: getting the resulting token file into the running pod, so you don't
# have to hunt down the pod's (randomly-suffixed) name and hand-run kubectl cp every time.
GMAIL_TOKEN_LOCAL="$REPO_ROOT/.secrets/gmail-token.json"
if [ -f "$GMAIL_TOKEN_LOCAL" ]; then
  BACKEND_POD="$(kubectl -n "$APP_NS" get pod -l app=backend -o jsonpath='{.items[0].metadata.name}')"
  if [ -n "$BACKEND_POD" ]; then
    log "Copying local Gmail token into $BACKEND_POD"
    kubectl -n "$APP_NS" cp "$GMAIL_TOKEN_LOCAL" "$BACKEND_POD:/app/.secrets/gmail-token.json"
  fi
else
  log "No local Gmail token yet ($GMAIL_TOKEN_LOCAL not found) — Gmail polling won't work until you authorize it (see install/k8s/README.md step 4):"
  echo "    1. On any machine with a browser (needs Python, not Docker/kubectl):"
  echo "         python3 -m venv pydantic_backend/.venv && source pydantic_backend/.venv/bin/activate"
  echo "         pip install -r pydantic_backend/requirements.txt"
  echo "         cp pydantic_backend/.env.example pydantic_backend/.env"
  echo "         # fill in GMAIL_CLIENT_ID/SECRET, DATABASE_URL, LITELLM_KEY_ENCRYPTION_KEY,"
  echo "         # LITELLM_WORKER_API_KEY (same values as backend.env — Settings() validates"
  echo "         # the whole model even though gmail_auth.py only uses the Gmail ones)"
  echo "         python -m pydantic_backend.gmail_auth   # opens a one-time browser consent screen"
  echo "    2. Copy the resulting .secrets/gmail-token.json to $GMAIL_TOKEN_LOCAL on this machine"
  echo "    3. Re-run this script — it'll pick it up and push it into the running pod automatically"
  echo "    (Everything else in this script works fine without this — it only blocks Gmail ingestion.)"
fi

# --- 9. One-time schema bootstrap (NEVER re-run automatically — it drops+recreates tables) ---
BOOTSTRAP_MARKER=".bootstrapped"
if [ ! -f "$BOOTSTRAP_MARKER" ]; then
  log "Bootstrapping schema (first run only — this marker prevents accidental re-runs, which would drop existing project/file data)"
  kubectl -n "$APP_NS" port-forward svc/backend 18011:8011 >/dev/null 2>&1 &
  PF_PID=$!
  trap 'kill $PF_PID 2>/dev/null || true' EXIT
  sleep 3
  curl -sf -X POST http://localhost:18011/setup/database >/dev/null
  kill "$PF_PID" 2>/dev/null || true
  trap - EXIT
  touch "$BOOTSTRAP_MARKER"
  log "Schema bootstrapped, admin account created ($(get_env ADMIN_EMAIL))"
else
  log "Already bootstrapped (found $BOOTSTRAP_MARKER) — skipping, to avoid dropping existing data"
fi

# --- 10. Verify ---------------------------------------------------------------------------
# -k: the reference ingress.yaml ships with its TLS block commented out (no cert-manager /
# real certificate wired up by default — see ingress.yaml), so this hits a self-signed
# default cert. Drop -k once you've set up real TLS.
log "Verifying"
curl -sk "https://${INGRESS_HOST}/tender-eval-api/health" && echo
# -L: "/" 307-redirects to "/tender-eval/projects" (app login/landing logic) — follow it to
# check the actual page loads, not just that the redirect itself returned.
FRONTEND_CODE="$(curl -sk -L -o /dev/null -w '%{http_code}' "https://${INGRESS_HOST}/tender-eval")"
echo "Frontend: HTTP $FRONTEND_CODE"

echo
log "Done. Frontend: https://${INGRESS_HOST}/tender-eval"
log "Next: add reviewers (POST /employees) — see the root README's 'Add reviewers' section."
