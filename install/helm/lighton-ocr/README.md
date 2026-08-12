# LightOnOCR — deployed on the toolkit, registered on its gateway

Deploys `lightonai/LightOnOCR-2-1B` (the vision-language OCR model the PDF
pipeline needs — see [`../pdf-pipeline/README.md`](../pdf-pipeline/README.md))
onto the same cluster as the Intel® AI for Enterprise Agent Toolkit, and
registers it on the toolkit's own LiteLLM gateway (GenAI Gateway) exactly the
way the toolkit registers every other model it serves.

This is **not** done through the toolkit's own `agentic-config.cfg` /
`models=` catalog + `deploy-agentic-stack.sh` flow, because that flow expects
write access to the toolkit's central inventory and re-runs its full ansible
deployment. Instead:

- The model server itself is deployed with **the toolkit's own, already-proven
  `core/helm-charts/vllm` chart** — reused as-is, not reimplemented — using
  [`vllm-model-values.yaml`](vllm-model-values.yaml) in this directory (the
  LightOnOCR-2-1B slice of the toolkit's `xeon-values.yaml`).
- Registering that model on the gateway is packaged as **this chart**
  (`lighton-ocr`) — a Helm-managed post-install/post-upgrade hook Job that
  does the same `POST /model/new` call the toolkit's own
  `register-model-genai-gateway.yml` ansible task performs, so it's idempotent
  and safe to re-run on every `helm upgrade`.

## Prerequisites

- The Intel AI for Enterprise Agent Toolkit already deployed on this cluster
  (Prerequisite 0 in the [root README](../../../README.md)), with its GenAI
  Gateway (`genai-gateway` namespace) running.
- `kubectl` context pointed at that cluster.
- A HuggingFace token with read access to `lightonai/LightOnOCR-2-1B`.

## 1. Deploy the model (toolkit's chart, our values)

```bash
TOOLKIT_PATH=../../../../enterprise-agent-toolkit   # wherever you cloned it

helm upgrade --install vllm-lighton-ocr-cpu "$TOOLKIT_PATH/core/helm-charts/vllm" \
  --values vllm-model-values.yaml \
  --set global.HUGGINGFACEHUB_API_TOKEN=<your_hf_token>
```

This creates the `vllm-lighton-ocr-cpu-service.default` Service that both the
registration Job below and the PDF pipeline (see `../pdf-pipeline/`) call —
same release name and namespace the toolkit's own playbook would use for
`models=cpu-lighton-ocr`, so this is a drop-in equivalent.

Verify:

```bash
kubectl get pods -l app.kubernetes.io/instance=vllm-lighton-ocr-cpu
kubectl run curl-lighton-check --rm -i --image=curlimages/curl --restart=Never -- \
  curl -s -o /dev/null -w '%{http_code}\n' \
  http://vllm-lighton-ocr-cpu-service.default.svc.cluster.local/v1/models
# → 200
```

## 2. Register it on the gateway (this chart)

Fetch the LiteLLM master key (as the root README's "Issue keys from the
gateway" step already documents) and stash it in a Secret this chart reads:

```bash
kubectl create secret generic lighton-ocr-registration-litellm \
  --from-literal=master-key="$(kubectl get deploy -n genai-gateway genai-gateway-deployment \
    -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="LITELLM_MASTER_KEY")].value}')"
```

Then install this chart:

```bash
helm upgrade --install lighton-ocr-registration . --values values.yaml
```

Check the registration Job:

```bash
kubectl logs job/lighton-ocr-registration-register
# → "Model lightonai/LightOnOCR-2-1B registered successfully at http://genai-gateway-service..."
```

Confirm it on the gateway itself:

```bash
curl -s -H "Authorization: Bearer <master_key>" \
  https://<cluster_url>/v1/models | jq '.data[].id'
# → should now include "lightonai/LightOnOCR-2-1B"
```

## Why register at all, if the PDF pipeline calls the model directly?

The PDF pipeline (docling's `VlmPipeline`) talks straight to
`vllm-lighton-ocr-cpu-service`'s OpenAI-compatible endpoint — not through the
gateway — because that's an internal, unauthenticated cluster call and going
through LiteLLM would add a hop and an API key for no benefit (see
`../pdf-pipeline/README.md`). Registering on the gateway anyway means:

- The model shows up in `GET /v1/models` like every other toolkit-hosted
  model, so anyone auditing what's running on the toolkit sees it.
- Spend/usage tracking, quotas, and virtual-key scoping (the same mechanism
  tender-eval's own `LITELLM_KEY_ENCRYPTION_KEY` / per-employee keys rely on
  for the Qwen calls) become available for OCR calls too, if something other
  than the PDF pipeline ever needs to call it through the gateway.
