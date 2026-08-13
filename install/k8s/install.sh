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
BOOTSTRAP_MARKER=".bootstrapped"

if [ -t 1 ]; then
  C_GREEN=$'\033[32m'; C_RED=$'\033[31m'; C_BLUE=$'\033[34m'; C_YELLOW=$'\033[33m'; C_RESET=$'\033[0m'
else
  C_GREEN=""; C_RED=""; C_BLUE=""; C_YELLOW=""; C_RESET=""
fi

log()   { echo "==> $*"; }
ok()    { echo "==> ${C_GREEN}$*${C_RESET}"; }        # value present / step succeeded
build() { echo "==> ${C_BLUE}$*${C_RESET}"; }         # building an image
note()  { echo "${C_YELLOW}$*${C_RESET}"; }           # informational aside, not a step result
die()   { echo "${C_RED}ERROR: $*${C_RESET}" >&2; exit 1; }

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

# --- 0b. Wipe any pre-existing tender-bid namespace ----------------------------------------
# This installer is meant to stand the app up from scratch every time it's run, so a
# leftover (or half-deleted/stuck-terminating) namespace from a previous attempt is deleted
# first rather than reused/adopted. This also drops the schema-bootstrap marker below, since
# a fresh namespace means a fresh (empty) database.
#
# pdf-pipeline is NOT touched here — it's a prerequisite deployed separately (its own Helm
# chart, see ../helm/pdf-pipeline/README.md), the same way genai-gateway is a prerequisite.
# This script only owns tender-bid.
if kubectl get namespace "$APP_NS" >/dev/null 2>&1; then
  log "Deleting pre-existing namespace '$APP_NS' (fresh install)"
  kubectl delete namespace "$APP_NS" --wait=true --timeout=180s
fi
rm -f "$BOOTSTRAP_MARKER"

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

  EXISTS="$(kubectl run psql-tender-eval-check-$$ -n "$GATEWAY_NS" --rm -i --restart=Never --quiet \
    --image=bitnamilegacy/postgresql:16 --env="PGPASSWORD=$PGPASS" -- \
    psql -h genai-gateway-postgresql -U postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" 2>/dev/null | tr -d '[:space:]')"

  if [ "$EXISTS" != "1" ]; then
    kubectl run psql-tender-eval-setup-$$ -n "$GATEWAY_NS" --rm -i --restart=Never --quiet \
      --image=bitnamilegacy/postgresql:16 --env="PGPASSWORD=$PGPASS" -- \
      psql -h genai-gateway-postgresql -U postgres -c "CREATE DATABASE $DB_NAME;"
    ok "Created database '$DB_NAME'"
  else
    ok "Database '$DB_NAME' already exists — reusing it"
  fi

  set_env DATABASE_URL "postgresql://postgres:${PGPASS}@${GATEWAY_HOST}:5432/${DB_NAME}"
else
  ok "✓ DATABASE_URL already set"
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
  ok "✓ LITELLM_KEY_ENCRYPTION_KEY already set"
fi

# --- 4. Mint ADMIN_LITELLM_KEY / LITELLM_WORKER_API_KEY from the gateway ----------------
mint_litellm_key() {
  local alias="$1"
  local master
  master="$(kubectl get deploy -n "$GATEWAY_NS" genai-gateway-deployment \
    -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="LITELLM_MASTER_KEY")].value}')"
  [ -n "$master" ] || die "Could not read LITELLM_MASTER_KEY from genai-gateway-deployment."

  kubectl run "litellm-mint-${alias}-$$" -n "$GATEWAY_NS" --rm -i --restart=Never --quiet \
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
  ok "✓ ADMIN_LITELLM_KEY already set"
fi

if [ -z "$(get_env LITELLM_WORKER_API_KEY)" ]; then
  log "Minting LITELLM_WORKER_API_KEY from the gateway"
  set_env LITELLM_WORKER_API_KEY "$(mint_litellm_key worker)"
else
  ok "✓ LITELLM_WORKER_API_KEY already set"
fi

# --- 5. Check for fields ONLY a human can provide ---------------------------------------
MISSING=()
for k in GMAIL_CLIENT_ID GMAIL_CLIENT_SECRET LOGFIRE_TOKEN; do
  [ -z "$(get_env "$k")" ] && MISSING+=("$k")
done
if [ ${#MISSING[@]} -gt 0 ]; then
  log "Everything automatable is filled in. Still need from you, in $ENV_FILE:"
  printf "  - ${C_RED}%s${C_RESET}\n" "${MISSING[@]}"
  echo
  note "GMAIL_CLIENT_ID/SECRET: Google Cloud Console -> APIs & Services -> Credentials"
  note "  -> Create Credentials -> OAuth client ID -> Desktop app"
  note "  (https://console.cloud.google.com/apis/credentials)"
  note "LOGFIRE_TOKEN: your Logfire project's write token (https://logfire.pydantic.dev)"
  echo
  note "Fill those in, then re-run this script — everything above is safe to skip on the next run."
  exit 1
fi

# --- 6. Build both images ---------------------------------------------------------------
build "Building backend image"
( cd "$REPO_ROOT" && $BUILD_CMD -f pydantic_backend/Dockerfile -t tender-bid-backend:local . )

build "Building frontend image"
( cd "$REPO_ROOT" && $BUILD_CMD -f frontend/Dockerfile \
    --build-arg NEXT_PUBLIC_API_BASE_URL="https://${INGRESS_HOST}/tender-eval-api" \
    --build-arg NEXT_PUBLIC_BASE_PATH="$FRONTEND_BASE_PATH" \
    -t tender-bid-frontend:local . )

# --- 7. Namespace + secret (idempotent) --------------------------------------------------
log "Creating namespace and backend-env secret"
kubectl create namespace "$APP_NS" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
kubectl -n "$APP_NS" create secret generic backend-env \
  --from-env-file="$ENV_FILE" --dry-run=client -o yaml | kubectl apply -f - >/dev/null
ok "Namespace and backend-env secret created"

# --- 8. Deploy ---------------------------------------------------------------------------
log "Applying manifests"
kubectl apply -k .
kubectl -n "$APP_NS" rollout status deploy/backend --timeout=180s
kubectl -n "$APP_NS" rollout status deploy/frontend --timeout=180s
ok "Backend and frontend deployed successfully"

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
    ok "Gmail token copied into $BACKEND_POD"
  fi
else
  note "No local Gmail token yet ($GMAIL_TOKEN_LOCAL not found) — Gmail polling won't work until you authorize it (see install/k8s/README.md step 4):"
  note "    1. On any machine with a browser (needs Python, not Docker/kubectl; uses uv):"
  note "         uv venv pydantic_backend/.venv && source pydantic_backend/.venv/bin/activate"
  note "         uv pip install -r pydantic_backend/requirements.txt"
  note "         cp pydantic_backend/.env.example pydantic_backend/.env"
  note "         ### IMPORTANT: edit pydantic_backend/.env now and fill in GMAIL_CLIENT_ID/SECRET ###"
  note "         # also fill in DATABASE_URL, LITELLM_KEY_ENCRYPTION_KEY, LITELLM_WORKER_API_KEY"
  note "         # (same values as backend.env — Settings() validates the whole model even"
  note "         # though gmail_auth.py only uses the Gmail ones)"
  note "         python -m pydantic_backend.gmail_auth   # opens a one-time browser consent screen"
  note "    2. Copy the resulting .secrets/gmail-token.json to $GMAIL_TOKEN_LOCAL on this machine"
  note "    3. Re-run this script — it'll pick it up and push it into the running pod automatically"
  note "    (Everything else in this script works fine without this — it only blocks Gmail ingestion.)"
fi

# --- 9. One-time schema bootstrap (NEVER re-run automatically — it drops+recreates tables) ---
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
  ok "Schema bootstrapped, admin account created ($(get_env ADMIN_EMAIL))"
else
  ok "Already bootstrapped (found $BOOTSTRAP_MARKER) — skipping, to avoid dropping existing data"
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
ok "Done. Frontend: https://${INGRESS_HOST}/tender-eval"
note "Next: add reviewers (POST /employees) — see the root README's 'Add reviewers' section."
