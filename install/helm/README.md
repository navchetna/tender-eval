# Helm: LightOnOCR + PDF pipeline, on top of the enterprise agent toolkit

These two charts are what [Prerequisite 0](../../README.md#prerequisite-0--stand-up-the-enterprise-agent-toolkit)'s
step 6 ("deploy the PDF pipeline") actually means in practice. They deploy
the standalone [`AIComps` async Docling pipeline](https://github.com/navchetna/AIComps/tree/main/input-handlers/pdf/parsers/docling/async)
onto the same cluster as the toolkit, backed by an OCR model registered on
the toolkit's own LiteLLM gateway — reusing the toolkit's existing vLLM chart
and gateway-registration pattern rather than duplicating them.

## Order of operations

1. **Toolkit already deployed** — Prerequisite 0, steps 1-5 in the root
   README: Qwen3-30B-A3B running, GenAI Gateway up, keys minted. Not covered
   here.
2. **[`lighton-ocr/`](lighton-ocr)** — deploys `lightonai/LightOnOCR-2-1B`
   with the toolkit's own `vllm` chart (step 1 in that chart's README), then
   registers it on the gateway with a small chart of our own (step 2).
3. **[`pdf-pipeline/`](pdf-pipeline)** — deploys the AIComps async Docling
   service, pointed at the LightOnOCR service from step 2.
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
helm upgrade --install pdf-pipeline . --namespace pdf-pipeline --create-namespace \
  --values values.yaml \
  --set ingress.host=<cluster_url>   # same host as LITELLM_BASE_URL
cd ..
```

See each chart's own README for prerequisites, verification steps, and why
the pieces are split the way they are.

## Why two charts instead of one

- **`lighton-ocr`** only adds gateway *registration* — the model server
  itself is deployed with the toolkit's own, already-hardened `vllm` chart
  (CPU tuning, security context, HF token secret, PVC), reused as-is rather
  than reimplemented. Registering that model is the one piece the toolkit
  doesn't automate outside its own ansible playbook, so that's the one piece
  packaged here.
- **`pdf-pipeline`** has no equivalent upstream chart to reuse — AIComps
  ships Kustomize manifests, not Helm — so it's a from-scratch chart built
  from those manifests (with one fix: persistent volumes for both
  `/app/outputs` and `/data`, where the upstream manifests only persisted
  `/data` and used a dev-machine-specific `hostPath` for outputs).
