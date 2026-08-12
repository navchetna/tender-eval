# Deploying on Kubernetes

The reference deployment path — the same kind of cluster the enterprise agent toolkit itself
runs on (Prerequisite 0), deployed with `kubectl apply -k`. The
[`../docker/docker-compose.yaml`](../docker/docker-compose.yaml) setup is the standalone/local
-dev alternative to this, with one deliberate difference between them: **no Postgres is
deployed here**. The compose file bundles one as a standalone-install fallback, but this
deployment points `DATABASE_URL` at the enterprise agent toolkit's Postgres instead, so only
the backend (`:8011`) and frontend (`:3000`) run here. The prerequisites from the
[root README](../../README.md#installation) apply unchanged — the enterprise agent toolkit
(Prerequisite 0), the Gmail OAuth client, the Logfire token, and all the keys still have to
exist first; this directory only covers *how* the app itself is deployed.

What you need on the cluster side:

- `kubectl` access to a cluster, and `nerdctl` + a running `buildkitd` — the enterprise agent
  toolkit's own nodes are provisioned as plain containerd Kubernetes nodes with **no Docker
  installed at all**, so this is the expected default here, not a fallback. It's the same
  tooling already used to build the `pdf-pipeline` image (see
  `../helm/pdf-pipeline/README.md`). If you do have Docker on whatever machine builds these
  images, that works too — see the alternative below — but don't expect it to be present on
  the toolkit's own nodes.
- An ingress controller (the manifests assume `ingressClassName: nginx` — edit
  `ingress.yaml` if yours differs) and DNS for the shared host (`ei-api.mg2.eglb.intel.com`
  by default) pointing at it.

## Quick start: `./install.sh`

Steps 1-5 below, done for you: creates the `tender_eval` database, generates
`LITELLM_KEY_ENCRYPTION_KEY`, mints `ADMIN_LITELLM_KEY`/`LITELLM_WORKER_API_KEY` from the
gateway, builds both images, creates the namespace/secret, deploys, bootstraps the schema
(once — never again, since that step drops+recreates tables), and verifies. Idempotent — safe
to re-run; it only fills in values that are still blank and never repeats the schema bootstrap.

```bash
cd install/k8s
cp backend.env.example backend.env   # first run only, if backend.env doesn't exist yet
./install.sh
```

Verified end-to-end against a live cluster: builds both images, deploys, bootstraps, and
confirms `.../tender-eval-api/health` returns `{"status":"ok",...}` and `.../tender-eval`
serves the app (`200`, after following its login/landing redirect). One thing this run
surfaced and fixed: `frontend.yaml`'s readiness/liveness probes originally checked bare `/`,
which 404s once `frontend/next.config.ts`'s `basePath: "/tender-eval"` is set — nothing is
served at the bare root anymore. They now check `/tender-eval` instead.

The only things it genuinely can't do for you — because they require creating an external
account/credential, not just calling an API with something the cluster already has — are
`GMAIL_CLIENT_ID`/`GMAIL_CLIENT_SECRET` and `LOGFIRE_TOKEN`. Fill those into `backend.env`
(the script tells you exactly which ones are still blank and where to get them) and re-run.

The rest of this file explains what `install.sh` is doing step by step, and how to do each
piece by hand if you need to debug or customize something it assumes.

## 1. Build the images

From the **repo root** (both Dockerfiles expect it as build context). Builds straight into
containerd's `k8s.io` namespace, so the kubelet can use the image immediately — no registry,
no push step. This is what `kustomization.yaml` already assumes by default (`imagePullPolicy:
IfNotPresent`, bare image names, tag `local`):

```bash
# buildkitd must be running — check first, start it if not:
systemctl is-active buildkit || sudo buildkitd --addr unix:///run/buildkit/buildkitd.sock &

sudo nerdctl --namespace k8s.io build -f pydantic_backend/Dockerfile \
  -t tender-bid-backend:local .

# NEXT_PUBLIC_API_BASE_URL is baked into the JS bundle at build time (see frontend/Dockerfile)
# — set it to the public URL the *browser* will reach the backend on, i.e. the API host in
# ingress.yaml, and rebuild this image whenever that URL changes.
sudo nerdctl --namespace k8s.io build -f frontend/Dockerfile \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://ei-api.mg2.eglb.intel.com/tender-eval-api \
  --build-arg NEXT_PUBLIC_BASE_PATH=/tender-eval \
  -t tender-bid-frontend:local .

# Confirm both are visible to containerd/kubelet:
sudo nerdctl --namespace k8s.io images | grep tender-bid
```

If your cluster has more than one node, this only works on whichever node builds/schedules
the pods — for a multi-node cluster, push to a registry from wherever you build instead (see
below) and point every node's kubelet at it.

**Alternative — with Docker, and/or a registry (multi-node clusters):**

```bash
REGISTRY=registry.example.com   # wherever your cluster pulls from

docker build -f pydantic_backend/Dockerfile -t $REGISTRY/tender-bid-backend:latest .
docker build -f frontend/Dockerfile \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://ei-api.mg2.eglb.intel.com/tender-eval-api \
  --build-arg NEXT_PUBLIC_BASE_PATH=/tender-eval \
  -t $REGISTRY/tender-bid-frontend:latest .

docker push $REGISTRY/tender-bid-backend:latest
docker push $REGISTRY/tender-bid-frontend:latest
```

Then point `kustomization.yaml`'s `images:` block (`newName`/`newTag`) at the two pushed
images, and set `imagePullPolicy: Always` in `backend.yaml`/`frontend.yaml`.

## 2. Create the secret

The secret lives out of band — nothing in this directory ever contains a real credential.
`backend.env` doesn't exist yet — create it from this directory's own example (a separate
file from `../docker/backend.env.example`, since this path needs `DATABASE_URL` set and the
compose path doesn't):

```bash
cp backend.env.example backend.env
```

Fill in every value in `backend.env` (see the comments in that file), including
`DATABASE_URL` — it's already present as a line to fill in here, unlike the compose example,
because there's no bundled Postgres in this deployment path.

**Use a database of tender-eval's own, not the toolkit's `litellm` database.** The toolkit's
Postgres (`genai-gateway-postgresql`, in the `genai-gateway` namespace) is a plain Bitnami
PostgreSQL instance — LiteLLM's own schema lives in one database on it (`litellm`), but the
same instance's `postgres` superuser account (the chart sets `auth.postgresPassword`, which
provisions it) can create additional databases. First, find that superuser password — the
Bitnami chart stores it in a Secret, not just in Helm values:

```bash
kubectl get secret genai-gateway-postgresql -n genai-gateway \
  -o jsonpath='{.data.postgres-password}' | base64 -d
```

Then create a separate `tender_eval` database there instead of pointing this app at `litellm`
directly, so the two schemas never collide:

```bash
kubectl run psql-tender-eval-setup -n genai-gateway --rm -i --restart=Never \
  --image=bitnamilegacy/postgresql:16 -- \
  env PGPASSWORD=<postgres_superuser_password> psql \
    -h genai-gateway-postgresql -U postgres \
    -c "CREATE DATABASE tender_eval;"
```

(`<postgres_superuser_password>` is the value the lookup above just printed.) Then point this
app's `DATABASE_URL` at that database, not `litellm`:

```
DATABASE_URL=postgresql://postgres:<postgres_superuser_password>@genai-gateway-postgresql.genai-gateway.svc.cluster.local:5432/tender_eval
```

Then:

```bash
kubectl create namespace tender-bid   # kustomize also creates it, but the secret needs it first

kubectl -n tender-bid create secret generic backend-env \
  --from-env-file=backend.env
```

Two values in `backend.env` are deployment-URL-sensitive, same as with compose: make sure
`CORS_ORIGINS` contains the frontend's public origin, and note that the *backend's* public
URL lives in the frontend image, not in any secret (step 1). With the default shared-host
setup in `ingress.yaml` (frontend and backend both on `ei-api.mg2.eglb.intel.com`, split only
by path), that origin is `https://ei-api.mg2.eglb.intel.com` — frontend and backend end up
same-origin, so this mostly guards against someone embedding this API elsewhere rather than
a real cross-origin browser call. If you used separate hostnames instead, this needs the
frontend's actual one.

**Use internal cluster service addresses for `PARSER_BASE_URL` and `LITELLM_BASE_URL`, not
the external `ei-api.mg2.eglb.intel.com` hostname** — already the default in
`backend.env.example`, but worth understanding why: this backend runs in the *same* cluster
as the PDF pipeline and the GenAI Gateway, and this cluster has no real LoadBalancer
(`ingress-nginx-controller`'s `EXTERNAL-IP` is `<pending>`). Routing a pod's own request out
through the external hostname and back in through the ingress is a **hairpin NAT** — the
resolved public IP often can't loop back into the same cluster it fronts. Symptom: every
parse and every section-detection call fails with `httpcore.ConnectTimeout` /
`pydantic_ai.exceptions.ModelAPIError: Request timed out.`, even though the external hostname
works fine from *outside* the cluster (e.g. your own browser, or `curl` from wherever you run
`install.sh`). Verify connectivity directly from the pod if you hit this on a different
cluster's topology:

```bash
BACKEND_POD=$(kubectl -n tender-bid get pod -l app=backend -o jsonpath='{.items[0].metadata.name}')
kubectl -n tender-bid exec "$BACKEND_POD" -- python3 -c "
import httpx
for url in ['https://ei-api.mg2.eglb.intel.com/v1/models', 'http://genai-gateway-service.genai-gateway.svc.cluster.local:4000/v1/models']:
    try:
        print(url, httpx.get(url, verify=False, timeout=8).status_code)
    except Exception as e:
        print(url, 'ERROR:', e)
"
```

The external one should time out; the internal one should return `401` (needs auth, but the
*connection* itself works — that's what confirms this is the fix).

## 3. Deploy

**Step 2's `backend-env` secret must exist before this step** — the Deployment references it
via `envFrom`, and if it's missing the pod won't crash, it'll sit in a restart loop with
`Error: secret "backend-env" not found` in `kubectl describe pod`'s Events. If you see that,
go back and create the secret, then re-apply.

From the repo root:

```bash
kubectl apply -k install/k8s
kubectl -n tender-bid get pods -w   # wait for backend and frontend to go Ready
```

One-time schema init + admin bootstrap (creates tables and the first ADMIN employee from
`ADMIN_EMAIL` / `ADMIN_PASSWORD` / `ADMIN_LITELLM_KEY` in `backend-env`):

```bash
kubectl -n tender-bid port-forward svc/backend 8011:8011 &
curl -X POST http://localhost:8011/setup/database
kill %1
```

Verify:

```bash
curl -s https://ei-api.mg2.eglb.intel.com/tender-eval-api/health
curl -s -o /dev/null -w "%{http_code}\n" https://ei-api.mg2.eglb.intel.com/tender-eval   # open in a browser to actually use it
```

From here everything is deployment-agnostic — adding reviewers and the day-to-day usage flow
are covered in the [root README](../../README.md#add-reviewers) and
[`pydantic_backend/README.md`](../../pydantic_backend/README.md).

## 4. Authorize Gmail access

The app can't read the inbox yet — nothing has granted it access to the actual Gmail
account. This step is **why** it's required: Google's OAuth consent screen requires a real
human to click "Allow" in a browser while logged into the target Gmail account
(`flow.run_local_server()` in `pydantic_backend/ingestion/gmail.py`) — that's a deliberate
security boundary on Google's side, not something the app (or `install.sh`) can script
around. It only needs to happen once; the resulting refresh token is reused (and
self-refreshed) from then on.

Do this on any machine with a browser — it doesn't have to be the cluster or wherever you ran
`install.sh`, and doesn't need Docker/kubectl, just Python and the `gmail_client_id`/
`gmail_client_secret` values from `backend.env`:

```bash
python3 -m venv pydantic_backend/.venv
source pydantic_backend/.venv/bin/activate
pip install -r pydantic_backend/requirements.txt

cp pydantic_backend/.env.example pydantic_backend/.env
# fill in GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET (same values as backend.env), plus
# DATABASE_URL / LITELLM_KEY_ENCRYPTION_KEY / LITELLM_WORKER_API_KEY (also same values as
# backend.env — gmail_auth.py doesn't use these, but pydantic-settings validates the
# *entire* Settings model on construction, so they still have to be present)

python -m pydantic_backend.gmail_auth
# opens a browser consent screen once — approve access, then this exits and prints
# "Gmail authorization complete." A refresh token is now at .secrets/gmail-token.json.
```

Then get that token into the running pod — copy `.secrets/gmail-token.json` to the repo
root on whatever machine has `kubectl` access and re-run `./install.sh` (it detects the file
and pushes it into the pod automatically), or do it by hand:

```bash
kubectl -n tender-bid cp .secrets/gmail-token.json <backend-pod>:/app/.secrets/gmail-token.json
```

## Notes and deviations from the compose setup

- **Backend stays at `replicas: 1`** — it runs the unattended background pipeline worker
  in-process, and its Gmail OAuth token lives on a `ReadWriteOnce` volume (`gmail-token`
  PVC). The deployment uses `strategy: Recreate` for the same reason. The frontend is
  stateless and can scale freely.
- **Gmail token seeding** — the app writes and refreshes `.secrets/gmail-token.json` itself
  at runtime on the `gmail-token` PVC, but something has to put a token there in the first
  place — see step 4 above.
- **No Postgres here, by design** — the backend uses the enterprise agent toolkit's
  Postgres via the `DATABASE_URL` in the `backend-env` secret (step 2), matching the
  reference deployment. Only fall back to running your own (as the compose setup bundles)
  for a fully standalone install.
- **TLS terminates at the ingress** — neither service serves HTTPS itself, exactly as in the
  compose setup's external-reverse-proxy assumption. See the comments in `ingress.yaml`.
