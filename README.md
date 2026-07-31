# Tender Evaluation — Datacenter Edition

This is the **datacenter/enterprise** deployment of the Tender Evaluation platform: it
doesn't run or manage any model itself — every LLM call and every PDF-OCR call is routed to
Intel's centrally-hosted enterprise agentic toolkit (`ei-api.mg2.eglb.intel.com`), and each
reviewer is billed/attributed on that shared gateway through their own personal key. This is
`main`; there is also an **`Ervin0307/aipc`** branch that instead runs every model on-device
(Intel NPU + Arc GPU, plus one cloud call) for a single-machine AI PC deployment — the two
branches are intentionally separate and not meant to be merged. If you're standing up a
laptop/workstation demo rather than a shared, centrally-managed deployment, use that branch
instead; this README only covers `main`.

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

## Models — where they run, and how this app reaches them

Unlike the AIPC branch, this deployment doesn't stand up any model server itself. Both
model-backed stages are centrally hosted and reached purely by URL + credentials:

| Stage | Backing service | Config |
|---|---|---|
| PDF OCR/parsing | Enterprise agentic toolkit's PDF pipeline (the same docling + vision-model pipeline as the AIPC branch, just centrally deployed) | `PARSER_BASE_URL=https://ei-api.mg2.eglb.intel.com/pdf-pipeline` |
| All LLM calls (section detection, row/header matching, judgment, scoring, comparison, notification drafting) | Enterprise agentic toolkit's LiteLLM gateway | `LITELLM_BASE_URL=https://ei-api.mg2.eglb.intel.com/v1`, model alias `LITELLM_MODEL=auto_router` |

There's no fast/quality model split in this app's own code the way there is on the AIPC
branch — every call asks the gateway for the single alias `auto_router`, and the gateway
itself decides which underlying model actually answers each request. What *does* vary per
call is **whose key** makes it:

- **Each employee has their own LiteLLM key**, assigned by an admin when the employee is
  created (`POST /employees`) and stored encrypted at rest (Fernet, via
  `LITELLM_KEY_ENCRYPTION_KEY`). Every LLM call an employee triggers (approving a section,
  running a comparison, etc.) is authenticated with *their* key, so usage/spend on the
  shared gateway is attributed to the person who caused it, not a shared app-wide key.
- **The unattended background worker** (the periodic parse/detect/notify loop — see
  `PARSE_WORKER_ENABLED` below) has no logged-in employee to attribute calls to, so it uses
  its own dedicated `LITELLM_WORKER_API_KEY` instead.
- **The bootstrap admin** gets `ADMIN_LITELLM_KEY` set on their employee row the first time
  `POST /setup/database` runs, so there's always at least one usable key from first boot.

All of these — `LITELLM_KEY_ENCRYPTION_KEY`, `LITELLM_WORKER_API_KEY`, `ADMIN_LITELLM_KEY`,
and every reviewer's own key — need to come from whoever administers the enterprise agentic
toolkit for your organization; this app only consumes them, it doesn't provision them.

---

## Installation

Because there's no model infrastructure to stand up, this is just the app itself:
Postgres + backend + frontend.

### Prerequisites

- Access to the enterprise agentic toolkit: an admin LiteLLM key, a worker LiteLLM key, and
  a Fernet encryption key for storing employee keys at rest (generate your own with
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
  — this one you *do* generate yourself, it's local-only and never leaves this deployment).
- A Google Cloud project with the Gmail API + Drive API enabled, and a **Desktop application**
  OAuth client (`GMAIL_CLIENT_ID`/`GMAIL_CLIENT_SECRET`).
- A [Logfire](https://logfire.pydantic.dev) project + write token (`LOGFIRE_TOKEN`) — required
  in a container, which has no local `logfire auth` session to fall back on.
- This assumes `tender-bid-api.mg2.eglb.intel.com` / `tender-bid.mg2.eglb.intel.com` are
  already fronted by a reverse proxy terminating TLS and forwarding to this stack's published
  ports (`8011` backend, `3002` frontend) — neither service here serves HTTPS itself. Adjust
  `CORS_ORIGINS` and the frontend's `NEXT_PUBLIC_API_BASE_URL` build arg in
  `docker-compose.yaml` if your real hostnames differ.

### Bring up the stack

```bash
cd install/docker
cp .env.example .env                  # Postgres credentials
cp backend.env.example backend.env    # fill in every value — see comments in the file

docker compose -f docker-compose.yaml up -d --build
```

This starts:

- **`postgres`** — the app's own store (projects, files, evaluations, employees).
- **`backend`** (`:8011`) — the FastAPI app: Gmail ingestion, parsing orchestration (talking
  to the enterprise PDF pipeline above), section detection, evaluation, and the
  review/normalization API.
- **`frontend`** (`:3002`) — the reviewer-facing UI.

One-time schema init + admin bootstrap:

```bash
curl -X POST http://localhost:8011/setup/database
```

This creates the schema and bootstraps the first employee as `ADMIN_EMAIL`/`ADMIN_PASSWORD`
with `ADMIN_LITELLM_KEY` attached, so there's an admin account (and a usable LiteLLM key)
from the very first boot.

Verify:

```bash
docker compose ps
curl -s http://localhost:8011/health
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:3002   # frontend — open in a browser to actually use it
```

### Add reviewers

Every other employee needs their own LiteLLM key assigned at creation time:

```bash
curl -X POST http://localhost:8011/employees \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane Reviewer", "email": "jane@example.com", "password": "change-me", "litellm_key": "<their assigned enterprise agentic toolkit key>"}'
```

From here, the day-to-day usage flow (ingest → parse → detect → review → compare) is
documented in [`pydantic_backend/README.md`](pydantic_backend/README.md).
