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
- The `pdf-pipeline-litellm` Secret must exist in the `pdf-pipeline` namespace
  **before** you install — the Deployment reads `VLM_API_KEY` from it via
  `vlmApiKeySecret`, and if it's missing the pod won't fail to schedule, it'll
  crash-loop with `Error: secret "pdf-pipeline-litellm" not found` in
  `kubectl describe pod`'s Events. Mint one and create the namespace + secret
  first:

  ```bash
  kubectl create namespace pdf-pipeline
  MASTER=$(kubectl get deploy -n genai-gateway genai-gateway-deployment \
    -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="LITELLM_MASTER_KEY")].value}')
  KEY=$(kubectl run litellm-mint-pdfpipeline --rm -i --restart=Never --quiet --image=curlimages/curl -- \
    curl -s -X POST http://genai-gateway-service.genai-gateway.svc.cluster.local:4000/key/generate \
      -H "Authorization: Bearer $MASTER" -H "Content-Type: application/json" \
      -d "{\"key_alias\": \"pdf-pipeline-vlm-$(date +%s)\"}" | jq -r '.key')
  echo "$KEY" | grep -qE '^sk-' || { echo "Mint failed — got: $KEY" >&2; exit 1; }
  kubectl create secret generic pdf-pipeline-litellm --namespace pdf-pipeline \
    --from-literal=api-key="$KEY"
  ```

  (`--quiet` matters here — without it, `kubectl run --rm` appends its own
  `pod "..." deleted` confirmation directly onto the container's stdout with
  no newline, which `jq` then fails to parse: `parse error: Invalid numeric
  literal...`. The `$(date +%s)` suffix matters too — LiteLLM enforces unique
  `key_alias` values across all keys, so a fixed alias fails with `400 "Key
  with alias ... already exists"` on every retry after the first successful
  mint, and `jq -r '.key'` on that error object silently becomes the literal
  string `null`. The `grep` check catches that instead of writing a broken
  key into the secret.)

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
