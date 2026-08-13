# Helm: LightOnOCR + PDF pipeline, on top of the enterprise agent toolkit

These two charts are what [Prerequisite 0](../../README.md#0-stand-up-the-enterprise-agent-toolkit)'s
step 6 ("deploy the PDF pipeline") actually means in practice. They deploy
a standalone docling-based PDF parsing pipeline onto the same cluster as
the toolkit, backed by an OCR model registered on
the toolkit's own LiteLLM gateway — reusing the toolkit's existing vLLM chart
and gateway-registration pattern rather than duplicating them.

## Order of operations

1. **Toolkit already deployed** — Prerequisite 0, steps 1-5 in the root
   README: Qwen3-30B-A3B running, GenAI Gateway up, keys minted. Not covered
   here.
2. **[`lighton-ocr/`](lighton-ocr)** — deploys `lightonai/LightOnOCR-2-1B`
   with the toolkit's own `vllm` chart (step 1 in that chart's README), then
   registers it on the gateway with a small chart of our own (step 2).
   **Before running this, edit `vllm-model-values.yaml`'s CPU/memory sizing
   (`VLLM_CPU_KVCACHE_SPACE`, `VLLM_CPU_OMP_THREADS_BIND`, `cpu`, `memory`) —
   those values are tuned for one specific server and will crash or OOMKill
   on different hardware. See [`lighton-ocr/README.md`](lighton-ocr/README.md#before-you-deploy-tune-sizing-to-your-own-server)
   for exactly what to change and how to derive the right values (`lscpu` /
   `htop`).**
3. **[`pdf-pipeline/`](pdf-pipeline)** — deploys the async docling
   parsing service, pointed at the LightOnOCR service from step 2.
   **Before running this, create the `pdf-pipeline` namespace and its
   `pdf-pipeline-litellm` Secret (`VLM_API_KEY`) first** — the Deployment
   reads it via `vlmApiKeySecret`, and if it's missing the pod won't fail to
   schedule, it'll crash-loop with `Error: secret "pdf-pipeline-litellm" not
   found` in `kubectl describe pod`'s Events. See
   [`pdf-pipeline/README.md`](pdf-pipeline/README.md#prerequisites) for the
   commands to mint the key and create the secret.
4. **Point tender-eval at it** — set `PARSER_BASE_URL` in `backend.env` (see
   [`../docker/backend.env.example`](../docker/backend.env.example)) to
   wherever `pdf-pipeline`'s Ingress/NodePort ends up (step 3's chart exposes
   it under the same gateway host at `/pdf-pipeline` by default, matching
   what the root README already documents as the reference deployment's
   `PARSER_BASE_URL`).

```bash
cd install/helm

# 2. OCR model + gateway registration
cd lighton-ocr
helm upgrade --install vllm-lighton-ocr-cpu ../../../../enterprise-agent-toolkit/core/helm-charts/vllm \
  --values vllm-model-values.yaml \
  --set global.HUGGINGFACEHUB_API_TOKEN=<hf_token>
kubectl create secret generic lighton-ocr-registration-litellm \
  --from-literal=master-key="$(kubectl get deploy -n genai-gateway genai-gateway-deployment \
    -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="LITELLM_MASTER_KEY")].value}')"
helm upgrade --install lighton-ocr-registration . --values values.yaml
cd ..

# 3. PDF pipeline
cd pdf-pipeline
kubectl create namespace pdf-pipeline
# MASTER: the gateway's admin key, used only to mint KEY; KEY: a dedicated per-pipeline
# gateway key, stored in the pdf-pipeline-litellm secret so the Deployment can authenticate its OCR calls.
MASTER=$(kubectl get deploy -n genai-gateway genai-gateway-deployment \
  -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="LITELLM_MASTER_KEY")].value}')
KEY=$(kubectl run litellm-mint-pdfpipeline --rm -i --restart=Never --quiet --image=curlimages/curl -- \
  curl -s -X POST http://genai-gateway-service.genai-gateway.svc.cluster.local:4000/key/generate \
    -H "Authorization: Bearer $MASTER" -H "Content-Type: application/json" \
    -d "{\"key_alias\": \"pdf-pipeline-vlm-$(date +%s)\"}" | jq -r '.key')
# LiteLLM enforces unique key_alias values, so a fixed alias fails with a 400 on every retry
# after the first successful mint — hence the timestamp suffix above. jq -r '.key' on that
# error response silently becomes the literal string "null", so verify before using it:
echo "$KEY" | grep -qE '^sk-' || { echo "Mint failed — got: $KEY" >&2; exit 1; }
kubectl create secret generic pdf-pipeline-litellm --namespace pdf-pipeline \
  --from-literal=api-key="$KEY"
helm upgrade --install pdf-pipeline . --namespace pdf-pipeline --create-namespace \
  --values values.yaml \
  --set ingress.host=<cluster_url>   # same host as LITELLM_BASE_URL
```

See each chart's own README for prerequisites, verification steps, and why
the pieces are split the way they are.

Next: with the pipeline up, bring up tender-eval itself — see
[`../k8s/README.md`](../k8s/README.md#quick-start-installsh).
