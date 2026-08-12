# PDF pipeline (async docling)

Helm packaging of a standalone async docling-based PDF parsing pipeline —
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
- Your cluster needs pull access to `navchetna/pdf-pipeline` on Docker Hub —
  this is our own patched build (see `values.yaml`'s `image:` comment for
  why it isn't the upstream `ervin0307/pdf-pipeline:latest` image, and how
  to rebuild/republish it if the source changes).

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

## Why the pipeline calls the model through the gateway

`server/worker.py` calls `VLM_URL` — the toolkit's LiteLLM gateway
(`.../v1/chat/completions`), not the LightOnOCR vLLM Service directly — using
a dedicated key (`vlmApiKeySecret` in `values.yaml`; see its comment for how
to mint one). Routing through the gateway means every OCR call is
authenticated and shows up in the gateway's own request logs and spend
tracking, same as every other model call in this deployment — see
`../lighton-ocr/` for where `lightonai/LightOnOCR-2-1B` gets registered on
the gateway in the first place.
