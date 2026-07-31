# Tender Evaluation — AIPC Edition

This branch (`Ervin0307/aipc`) is the **AI PC** deployment of the Tender Evaluation
platform: every model in the pipeline runs on-device (Intel NPU + Arc GPU), except for one
deliberately-kept cloud call for final judgment quality. `main` runs a different,
enterprise/per-employee-key deployment of the same app — the two are intentionally separate,
not meant to be merged, so this README (and the rest of this branch) describes only this
AIPC setup. Checking out `main` gets you that branch's own README instead.

## Problem statement

Large companies run tenders to procure infrastructure. To reduce bias and pick the best bid,
every bidder's proposal has to be checked against the tender's own technical requirements,
and the pricing has to be compared on a level footing. Done by hand, this means a reviewer
reads a tender PDF (often 50+ pages) and every competing bid PDF, hunts down the
"Technical Requirements" and "Price/Commercial" sections in each one (every vendor's PDF
formats and headings differently), and manually cross-references line items — slow,
inconsistent between reviewers, and hard to justify after the fact ("why was Bidder B
marked non-compliant on row 12?").

## What this solution does

1. **Ingest** — a tender email (and any number of bidder-response emails) arrives in Gmail;
   the pipeline picks up unread PDF attachments and files them into a versioned project.
2. **Parse** — each PDF is OCR'd by a vision-language model into Markdown plus a structured
   tree + table-of-contents, so the document's actual layout (sections, tables, headings) is
   preserved as data, not just flattened text.
3. **Detect** — an LLM reads the table of contents and picks out which heading covers
   Technical Requirements and which covers Price/Commercial, for the tender and for every bid.
4. **Review** — a human reviewer is notified by email and approves or corrects each AI
   suggestion (per document, per topic) — the AI never has the final say.
5. **Normalize & compare** — once a tender and its bids are approved, their technical rows
   and price rows are aligned to each other and judged for compliance, and a plain-language
   comparison across bidders is produced — all traceable back to the exact section/row it
   came from, so a reviewer can see *why*, not just *what*.

## Models — what runs where, and why

This branch uses **three** models across two device targets plus one cloud call, fronted by
a single local LiteLLM proxy so the backend never talks to any model server directly — it
always asks LiteLLM for `npu-qwen3-4b`, `lightonocr-1b`, or `claude-sonnet-4-5` and LiteLLM
resolves where that actually lives.

| Model | Where it runs | Serves | Used for |
|---|---|---|---|
| **LightOnOCR-2-1B** (GGUF) | Intel **Arc GPU**, via `llama.cpp`'s `llama-server` (SYCL backend) | Vision — PDF page images → Markdown | The entire OCR/parsing stage (`pdf-pipeline`, a separate service — see below) |
| **Qwen3-4B-Instruct-2507** (OpenVINO IR, int4) | Intel **NPU**, via OpenVINO Model Server (OVMS) | Text — the "fast" tier | Technical/Price section detection, row/header alignment between tender and bid tables, drafting the reviewer notification email |
| **Claude** (`claude-sonnet-4-5`) | Cloud (Anthropic, via LiteLLM) | Text — the "quality" tier | Per-row compliance judgment, section scoring, and the final cross-bidder comparison/explanation — the calls where reasoning quality matters more than latency |

Why one cloud call survives on an otherwise fully local stack: judging compliance and
writing the final comparison is the highest-stakes reasoning step in the pipeline (it's what
a reviewer ultimately reads and acts on), and a 4B on-device model isn't yet a substitute for
Claude-tier judgment there. Everything upstream of it — OCR and section detection, which is
extraction/matching, not judgment — runs entirely on-device.

`pydantic_backend/llm_credentials.py` is the code-level version of this split:
`fast_llm_credentials()` (routed to `npu-qwen3-4b`) backs `detect_sections`, `match_rows`,
`match_headers`, and `notify_reviewer`; `quality_llm_credentials()` (routed to
`claude-sonnet-4-5`) backs `judge_row`, `score_section`, and `compare_bids`.

---

## Installation

Bring the model servers up first (they're host-native processes — NPU/GPU access doesn't
work well from inside a container), then the application stack, which fronts them through
LiteLLM.

### Prerequisites: download the models

| Model | Link |
|---|---|
| LightOnOCR-2-1B (GGUF, for llama.cpp) | https://huggingface.co/ervin0307/LightOnOCR-2-1B-GGUF |
| Qwen3-4B-Instruct-2507 (OpenVINO IR, for OVMS) | https://huggingface.co/ervin0307/Qwen3-4B-Instruct-2507-int4-ov |

For LightOnOCR you need **two files** from that repo: the quantized model itself (e.g.
`LightOnOCR-2-1B-bbox-Q4_K_M.gguf`) and an `mmproj-*.gguf` file — the vision projector that
turns page-image patches into the embeddings the language model consumes. The repo offers
the projector in more than one precision:

- **`mmproj-F32.gguf`** — full precision, largest file, reference quality.
- **`mmproj-BF16.gguf`** — half the size of F32, quality indistinguishable from it in
  practice. **This is what this deployment actually uses.**

Lower-precision quantized projectors (Q4/Q5/Q6/Q8) also exist in the repo but are not
recommended here — the projector is a small fraction of total model size, so quantizing it
saves little disk/VRAM while risking visibly worse OCR (garbled or dropped text), which
defeats the point of an OCR pipeline. Stick to BF16 (default) or F32 (if you need maximum
fidelity and have the extra disk/VRAM to spare).

### 1. Qwen3-4B on the NPU (OpenVINO Model Server on **Windows**)

Runs on the Windows side of the machine (OVMS + NPU driver are native Windows). Official
reference: [OVMS bare-metal deployment guide](https://docs.openvino.ai/2026/model-server/ovms_docs_deploying_server_baremetal.html).

```bat
mkdir models
ovms --rest_port 8000 ^
     --model_repository_path .\models ^
     --source_model ervin0307/Qwen3-4B-Instruct-2507-int4-ov ^
     --target_device NPU ^
     --model_name ervin0307/Qwen3-4B-Instruct-2507-int4-ov ^
     --task text_generation
```

`--source_model` pulls the model from Hugging Face straight into `--model_repository_path`
and registers it in one step — nothing to pre-download by hand. OVMS then serves an
OpenAI-compatible endpoint on `http://localhost:8000/v3`.

If you'd rather pull the model once and register/serve it separately (useful for an offline
model repo, or a model you've already downloaded), OVMS also supports a two-step form —
this was the approach used for the earlier 8B variant of this model:

```bat
mkdir models
ovms --pull --source_model OpenVINO/Qwen3-8B-int4-cw-ov ^
     --model_repository_path models --target_device NPU --task text_generation ^
     --tool_parser hermes3 --cache_dir .ov_cache --enable_prefix_caching true ^
     --max_prompt_len 2000
ovms --add_to_config --config_path models\config.json ^
     --model_name OpenVINO/Qwen3-8B-int4-cw-ov --model_path OpenVINO\Qwen3-8B-int4-cw-ov
```

For this deployment, use the single-command form above with
`ervin0307/Qwen3-4B-Instruct-2507-int4-ov`.

Verify it's up:

```bash
curl http://localhost:8000/v3/models
```

### 2. LightOnOCR on the GPU (llama.cpp server on **WSL**)

Two ways to get the `llama-server` binary/image — either works, the container image is what
this deployment actually runs.

**Build from source** (Intel oneAPI + SYCL backend), if you want a native binary instead of
a container:

```bash
source /opt/intel/oneapi/setvars.sh

git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
cmake -B build -DGGML_SYCL=ON -DCMAKE_C_COMPILER=icx -DCMAKE_CXX_COMPILER=icpx -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j$(nproc)
```

**Or use the prebuilt Intel-SYCL image** (`ghcr.io/ggml-org/llama.cpp:server-intel`) — this
is what's actually deployed here, pointed at the two model files you downloaded above
(placed at, e.g., `~/models/lightonocr-bbox/`):

```bash
docker run -d \
    --name llama-server-test \
    --device /dev/dxg \
    -e ZES_ENABLE_SYSMAN=1 \
    -v /home/devcloud/images:/media \
    -v /home/devcloud/ecasteli/models:/models \
    -v /usr/lib/wsl:/usr/lib/wsl \
    -p 8080:8080 \
    ghcr.io/ggml-org/llama.cpp:server-intel \
    -m /models/lightonocr-bbox/LightOnOCR-2-1B-bbox-Q4_K_M.gguf \
    --mmproj /models/lightonocr-bbox/mmproj-BF16.gguf \
    --media-path /media \
    -ngl 99 \
    -np 4 \
    -c 65536 \
    -b 8192 \
    -ub 2048 \
    -fa on \
    --mtmd-batch-max-tokens 2048 \
    --host 0.0.0.0 --port 8080
```

`--device /dev/dxg` + the `/usr/lib/wsl` mount are WSL2's GPU-passthrough plumbing for
Windows AI PCs; on bare-metal Linux with an Intel GPU you can drop both and mount
`/dev/dri` instead. Verify it's up:

```bash
curl http://localhost:8080/v1/models
```

### 3. The PDF parsing service (docling + LightOnOCR)

This is a separate repo/service — [`navchetna/AIComps`](https://github.com/navchetna/AIComps/tree/main/input-handlers/pdf/parsers/docling/async).
Follow its own README/INSTALL.md to build and run it (`docker compose up -d --build` from
that directory).

**Important:** point its `VLM_URL` at **LiteLLM**, not directly at `llama-server` — that's
what makes LightOnOCR's usage show up in the LiteLLM dashboard alongside the other two
models, and is required either way once LiteLLM is the thing enforcing auth on that
endpoint. In that service's `docker-compose.yml`:

```yaml
environment:
  VLM_URL: "http://host.docker.internal:4000/v1/chat/completions"
  VLM_API_KEY: "${VLM_API_KEY}"   # must match LITELLM_MASTER_KEY below; set via a local .env
```

and its model name (in `server/worker.py`'s `ApiVlmOptions.params`) must be `lightonocr-1b`
— the `model_name` this stack's `litellm-config.yaml` gives that entry, not the raw
Hugging Face model id.

Since `VLM_URL` now points at LiteLLM (started in step 5 below, not yet running at this
point), `pdf-pipeline` will start fine but OCR requests will fail until LiteLLM is up —
that's expected; just make sure step 5 runs before you actually submit a PDF.

### 4. Verify both model servers are reachable from WSL

**Requires WSL set to mirrored networking.** OVMS runs on Windows, but everything else
(llama-server, LiteLLM, this backend) runs inside WSL — by default WSL2 uses NAT networking,
which puts WSL on its own isolated subnet and doesn't reliably forward `localhost` traffic
from WSL back to a service bound to `localhost` on Windows. **Mirrored** mode instead gives
WSL the same network stack as Windows, so `localhost:8000` from WSL reaches OVMS on Windows
directly. Needs Windows 11 22H2+ and WSL ≥ 2.0.0.

To enable it, on the **Windows** side create/edit `%UserProfile%\.wslconfig` (i.e.
`C:\Users\<you>\.wslconfig`) and add:

```ini
[wsl2]
networkingMode=mirrored
```

Then restart WSL from PowerShell (this closes every WSL session/terminal you have open):

```powershell
wsl --shutdown
```

Reopen your WSL terminal and confirm it took effect — under mirrored mode, `ip addr` inside
WSL shows the same IP as Windows' own network adapter (not an isolated `172.x`/NAT address).
The real test is that this succeeds:

```bash
curl http://localhost:8000/v3/models    # Qwen3 via OVMS (Windows), only reachable in mirrored mode
curl http://localhost:8080/v1/models    # LightOnOCR via llama-server (WSL-native, works either way)
```

### 5. Bring up the application (LiteLLM + backend + frontend)

```bash
cd install/docker
cp .env.example .env                  # Postgres credentials
cp backend.env.example backend.env    # fill in every value — see comments in the file
cp litellm.env.example litellm.env    # LITELLM_MASTER_KEY (must match backend.env) + ANTHROPIC_API_KEY

docker compose -f docker-compose.yaml up -d --build
```

One-time schema init once the backend is up:

```bash
curl -X POST http://localhost:8011/setup/database
```

This starts, in order:

- **`postgres`** — app + LiteLLM's own store (spend logs, virtual keys, `/ui` login).
- **`litellm`** (`network_mode: host`, so it shares WSL's own network namespace — needed to
  reach the Windows-hosted OVMS over `localhost`, which in turn requires the mirrored
  networking mode set up in step 4) — proxies `npu-qwen3-4b` →
  OVMS (`:8000`) and `lightonocr-1b` → `llama-server` (`:8080`); `claude-sonnet-4-5` is added
  separately via the Admin UI (`http://localhost:4000/ui`), not `litellm-config.yaml`.
- **`backend`** (`:8011`) — the FastAPI app: Gmail ingestion, parsing orchestration
  (talking to the `pdf-pipeline` service from step 3), section detection, evaluation, and
  the review/normalization API.
- **`frontend`** (`:3002`) — the reviewer-facing UI.

Verify:

```bash
docker compose ps
curl -s http://localhost:8011/health
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3002   # frontend — open in a browser to actually use it
```

From here, the day-to-day usage flow (ingest → parse → detect → review → compare) is
documented in [`pydantic_backend/README.md`](pydantic_backend/README.md).
