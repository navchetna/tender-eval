# PDF pipeline (AIComps async Docling)

Helm packaging of [`navchetna/AIComps`'s async Docling PDF pipeline](https://github.com/navchetna/AIComps/tree/main/input-handlers/pdf/parsers/docling/async) —
converts each submitted PDF into Markdown, a structured tree, a table of
contents, and extracted figures, using LightOnOCR (served by vLLM — see
[`../lighton-ocr/`](../lighton-ocr)) as its OCR/vision backend. This is what
tender-eval's `PARSER_BASE_URL` points at.

Source: the upstream project's own `manifests/` Kustomize set, converted to a
chart so it ships and versions with this solution. One deliberate fix from
upstream: `/app/outputs` is now backed by a PVC like `/data` already was —
upstream's manifests `hostPath`-mounted outputs to a literal dev-machine path,
which only works on that one node.

## Prerequisites

- [`../lighton-ocr/`](../lighton-ocr) already deployed (or any other
  OpenAI-compatible endpoint serving `lightonai/LightOnOCR-2-1B` — set
  `vlmUrl` accordingly).
- An image registry reachable from your cluster, if you're not using the
  published `ervin0307/pdf-pipeline:latest` image — see the upstream
  project's `Dockerfile` / `INSTALL.md` to build your own.

## Deploy

```bash
helm upgrade --install pdf-pipeline . --namespace pdf-pipeline --create-namespace \
  --values values.yaml \
  --set ingress.host=<cluster_url>    # same host as LITELLM_BASE_URL/PARSER_BASE_URL
```

`--namespace pdf-pipeline --create-namespace` matters here: this chart doesn't template its
own Namespace resource (that causes Helm ownership conflicts the moment anything else ever
touches the namespace — see the note in `values.yaml`), so Helm has to create and own it via
this flag instead. If you hit `"Namespace \"pdf-pipeline\" ... exists and cannot be imported"`,
something else already created it (e.g. running the upstream Kustomize manifests directly) —
check what's in it first (`kubectl get all,pvc -n pdf-pipeline`), then either delete it
(`kubectl delete namespace pdf-pipeline`) and re-run the command above, or adopt it by hand:

```bash
kubectl label namespace pdf-pipeline app.kubernetes.io/managed-by=Helm
kubectl annotate namespace pdf-pipeline meta.helm.sh/release-name=pdf-pipeline meta.helm.sh/release-namespace=pdf-pipeline
```

Or without the Ingress, using the NodePort (enabled by default at `30010`):

```bash
helm upgrade --install pdf-pipeline . --namespace pdf-pipeline --create-namespace \
  --values values.yaml --set ingress.enabled=false
```

## Verify

```bash
kubectl -n pdf-pipeline get pods,pvc,svc

# Via the internal ClusterIP service:
kubectl run curl-pdf-pipeline-check --rm -i --image=curlimages/curl --restart=Never -- \
  curl -s -o /dev/null -w '%{http_code}\n' \
  http://pdf-pipeline.pdf-pipeline.svc.cluster.local:8010/docs

# Via NodePort (if enabled):
curl http://<node-ip>:30010/docs

# Via Ingress (if enabled), matching tender-eval's own PARSER_BASE_URL shape:
curl https://<cluster_url>/pdf-pipeline/docs
```

`PARSER_BASE_URL` in tender-eval's `backend.env` should then be:

```
PARSER_BASE_URL=https://<cluster_url>/pdf-pipeline
```

(or the NodePort/ClusterIP form above, if you didn't enable the Ingress).

## Why the pipeline calls the model directly, not through the gateway

`server/worker.py` (upstream) calls `VLM_URL` — the LightOnOCR vLLM Service's
own `/v1/chat/completions` — directly, not the toolkit's LiteLLM gateway.
That's an internal, unauthenticated cluster-to-cluster call, so there's no
API key to manage for it and no extra hop through the gateway. The model is
still registered on the gateway separately (see `../lighton-ocr/`) so it's
visible in the toolkit's model catalog even though this pipeline doesn't use
that path itself.
