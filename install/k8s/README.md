# Deploying on Kubernetes

The Kubernetes equivalent of [`../docker/docker-compose.yaml`](../docker/docker-compose.yaml),
deployed with `kubectl apply -k` — with one deliberate difference: **no Postgres is deployed
here**. The compose file bundles one as a standalone-install fallback, but this deployment
follows the reference setup and points `DATABASE_URL` at the enterprise agent toolkit's
Postgres instead, so only the backend (`:8011`) and frontend (`:3000`) run here. The
prerequisites from the [root README](../../README.md#installation) apply unchanged — the
enterprise agent toolkit (Prerequisite 0), the Gmail OAuth client, the Logfire token, and all
the keys still have to exist first; this directory only changes *how* the app itself is
deployed.

What you need on the cluster side:

- `kubectl` access to a cluster, and `docker` (or another builder) plus a registry the
  cluster can pull from — unlike docker compose, Kubernetes doesn't build images from source.
- An ingress controller (the manifests assume `ingressClassName: nginx` — edit
  `ingress.yaml` if yours differs) and DNS for the two hostnames pointing at it.

## 1. Build and push the images

From the **repo root** (both Dockerfiles expect it as build context):

```bash
REGISTRY=registry.example.com   # wherever your cluster pulls from

docker build -f pydantic_backend/Dockerfile -t $REGISTRY/tender-bid-backend:latest .

# NEXT_PUBLIC_API_BASE_URL is baked into the JS bundle at build time (see frontend/Dockerfile)
# — set it to the public URL the *browser* will reach the backend on, i.e. the API host in
# ingress.yaml, and rebuild this image whenever that URL changes.
docker build -f frontend/Dockerfile \
  --build-arg NEXT_PUBLIC_API_BASE_URL=https://tender-bid-api.mg2.eglb.intel.com \
  -t $REGISTRY/tender-bid-frontend:latest .

docker push $REGISTRY/tender-bid-backend:latest
docker push $REGISTRY/tender-bid-frontend:latest
```

Then point `kustomization.yaml`'s `images:` block at the two pushed images.

## 2. Create the secret

The secret lives out of band — nothing in this directory ever contains a real credential.
Fill in `../docker/backend.env` exactly as for the compose setup (copy from
`backend.env.example`, see the comments in that file), with one addition: **add a
`DATABASE_URL` line pointing at the toolkit's Postgres** (that file's comments say to leave
it out only because compose wires up its own bundled Postgres — there is none here). Then:

```bash
kubectl create namespace tender-bid   # kustomize also creates it, but the secret needs it first

# The backend's full configuration, straight from the same env file compose uses —
# including the DATABASE_URL you just added.
kubectl -n tender-bid create secret generic backend-env \
  --from-env-file=../docker/backend.env
```

Two values in `backend.env` are deployment-URL-sensitive, same as with compose: make sure
`CORS_ORIGINS` contains the frontend's public origin (the first host in `ingress.yaml`), and
note that the *backend's* public URL lives in the frontend image, not in any secret (step 1).

## 3. Deploy

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
curl -s https://tender-bid-api.mg2.eglb.intel.com/health
curl -s -o /dev/null -w "%{http_code}\n" https://tender-bid.mg2.eglb.intel.com   # open in a browser to actually use it
```

From here everything is deployment-agnostic — adding reviewers and the day-to-day usage flow
are covered in the [root README](../../README.md#add-reviewers) and
[`pydantic_backend/README.md`](../../pydantic_backend/README.md).

## Notes and deviations from the compose setup

- **Backend stays at `replicas: 1`** — it runs the unattended background pipeline worker
  in-process, and its Gmail OAuth token lives on a `ReadWriteOnce` volume (`gmail-token`
  PVC). The deployment uses `strategy: Recreate` for the same reason. The frontend is
  stateless and can scale freely.
- **Gmail token seeding** — the app writes and refreshes `.secrets/gmail-token.json` itself
  at runtime on the `gmail-token` PVC. If you already have a token from a previous (e.g.
  compose) install, copy it in once the backend pod is up:
  `kubectl -n tender-bid cp .secrets/gmail-token.json <backend-pod>:/app/.secrets/gmail-token.json`
- **No Postgres here, by design** — the backend uses the enterprise agent toolkit's
  Postgres via the `DATABASE_URL` in the `backend-env` secret (step 2), matching the
  reference deployment. Only fall back to running your own (as the compose setup bundles)
  for a fully standalone install.
- **TLS terminates at the ingress** — neither service serves HTTPS itself, exactly as in the
  compose setup's external-reverse-proxy assumption. See the comments in `ingress.yaml`.
