# Merchant Compliance Pipeline: Gmail → Drive → Postgres → Parsing → Evaluation

End-to-end pipeline, in the order it actually runs:

```text
Gmail unread PDF email (1 circular + any number of merchant PDFs as attachments)
  → Gmail OAuth (readonly + send + drive scopes)
  → validate `PROJECT-CODE: Project Name` subject
  → versioned Drive folder: "<code> - <name>" / "Version 00N - <datetime>"
  → upload every PDF to Drive, record each in Postgres (RECEIVED) — one row per file, so any
    number of merchant PDFs in the same email are ingested independently
  → async PDF parser (docling) submits/polls/fetches markdown, output_tree.json, TOC, images
  → parsed artifacts uploaded to Drive (parsed_results/...), TOC text + tree links stored in Postgres (PARSED)
  → LiteLLM gateway detects which TOC heading covers Payment Compliance vs Service Compliance
  → matching section content pulled from output_tree.json, stored in circular_evaluations / submission_evaluations (SUGGESTED)
  → an agent (pydantic-ai + LiteLLM) drafts and sends ONE reviewer notification email per
    project/version per processing run, covering every newly-suggested file in that run
  → human reviewer approves or corrects each topic, per file, via REST endpoints
  → the normalization view merges the circular's approved sections with every approved submission's
    sections into one side-by-side comparison, computed on demand
```

A project/version can have exactly one circular document and any number of submission documents —
submission PDFs are matched to the circular purely by living in the same email/project/version;
file names only need to contain `circular` or `submission` to be classified. If two attachments in
the same email share an identical file name (e.g. two merchants both send `submission.pdf`), the
pipeline automatically disambiguates them (`submission.pdf`, `submission (2).pdf`, ...) before upload/
persistence so neither is dropped.

## One-time setup

```bash
uv venv pydantic_backend/.venv
source pydantic_backend/.venv/bin/activate
uv pip install -r pydantic_backend/requirements.txt
cp pydantic_backend/.env.example pydantic_backend/.env
### IMPORTANT: edit pydantic_backend/.env now and fill in GMAIL_CLIENT_ID/SECRET ###
# also edit: DATABASE_URL (URL-encode special chars, e.g. @ -> %40), PARSER_BASE_URL,
# LITELLM_KEY_ENCRYPTION_KEY, LITELLM_WORKER_API_KEY, REVIEWER_EMAIL
```

Enable the Gmail API + Drive API in the Google Cloud project; the OAuth client must be a
**Desktop application**. Then authorize (opens a browser consent screen once):

```bash
python -m pydantic_backend.gmail_auth
```

This saves a refresh token to `.secrets/gmail-token.json` covering `gmail.readonly`,
`gmail.send`, and `drive` scopes. Re-run this command any time the required scopes change
(delete `.secrets/gmail-token.json` first).

Start the server:

```bash
python -m pydantic_backend.main   # serves on :8011
```

## Step-by-step curl walkthrough

### 1. Initialize the database schema

```bash
curl -X POST http://localhost:8011/setup/database | jq
```

Creates/recreates `projects`, `file_repository` (drops+recreates — safe only pre-launch),
plus `employees` and `circular_evaluations` (left intact unless cascaded).

### 2. Register at least one reviewer (employee)

```bash
curl -X POST http://localhost:8011/employees \
  -H "Content-Type: application/json" \
  -d '{"name": "Your Name", "email": "you@example.com", "password": "change-me", "litellm_key": "<their assigned LiteLLM key>"}' | jq
```

Save the returned `employee_id` — needed later to approve/correct sections. `litellm_key` is
required at creation (admins assign each employee their own enterprise agentic toolkit key,
used to authenticate every LLM call they trigger) and is never returned by any endpoint.

### 3. Poll Gmail for unread circular/submission PDFs and ingest them

```bash
curl -X POST "http://localhost:8011/ingestion/poll-gmail?max_results=20" | jq
```

For each new unread email matching `PROJECT-CODE: Project Name` with a PDF attachment:
creates/updates the project, uploads the PDF to a versioned Drive folder, and inserts a
`file_repository` row with `processing_status = RECEIVED`. Already-ingested emails are
skipped silently. File name must contain `circular` or `submission` to be classified accordingly
(only `circular` files go through section evaluation).

### 4. Parse the received PDFs

```bash
curl -X POST http://localhost:8011/parsing/process-pending | jq
```

Claims up to `PARSE_BATCH_SIZE` `RECEIVED` files, submits each to the async parser
(`PARSER_BASE_URL`), polls until done, then uploads `<stem>.md`, `<stem>_output_tree.json`,
`<stem>_toc.txt` (if the parser exposes it), and `<stem>_images/*.png` into
`.../parsed_results/` on Drive. Sets `processing_status = PARSED`, stores the raw TOC text
in `parse_toc`, and stores Drive file ids/links in `parse_artifacts`.

Can be called repeatedly/on a schedule — safe to re-run.

### 5. Detect Payment/Service sections + notify the reviewer

```bash
curl -X POST http://localhost:8011/evaluation/circular/process-pending | jq
```

For every `PARSED` file with `file_type = TENDER` and no evaluation yet: sends the TOC to
the LiteLLM gateway (authenticated with the calling admin's own assigned key) to pick the
Payment Compliance heading and the Service Compliance heading, looks up each heading's
full text in `output_tree.json`, and inserts a `circular_evaluations` row
(`technical_status`/`price_status = SUGGESTED`). Once the whole claimed batch is detected,
a pydantic-ai agent (LiteLLM-backed) drafts and sends ONE notification email per
project/version to `REVIEWER_EMAIL` via a `send_reviewer_email` tool, summarizing every
file that got a new suggestion in this run (there's normally just one circular per
project/version, but the same batching applies to `/evaluation/submission/process-pending` below,
where several merchant files processed together are covered by a single email).

Returns the list of newly created `evaluation_id`s.

### 6. Resend the notification (if `REVIEWER_EMAIL` was unset, or you want to nudge again)

```bash
curl -X POST http://localhost:8011/evaluation/circular/<evaluation_id>/notify | jq
```

### 7. Inspect a suggestion

```bash
curl http://localhost:8011/evaluation/circular/<evaluation_id> | jq
```

Or list everything still awaiting a decision:

```bash
curl http://localhost:8011/evaluation/circular/pending | jq
```

### 8. Approve or correct each topic (payment / service)

Approve the AI suggestion as-is:

```bash
curl -X POST http://localhost:8011/evaluation/circular/<evaluation_id>/review \
  -H "Content-Type: application/json" \
  -d '{"topic": "payment", "employee_id": "<employee_id>"}' | jq
```

Reject and replace with the correct TOC heading (copy it verbatim from `parse_toc` /
`GET /evaluation/circular/<evaluation_id>`):

```bash
curl -X POST http://localhost:8011/evaluation/circular/<evaluation_id>/review \
  -H "Content-Type: application/json" \
  -d '{"topic": "service", "employee_id": "<employee_id>", "corrected_heading": "1.4 Service Submission Evaluation"}' | jq
```

Repeat for both `payment` and `service`. Once both `technical_status` and `price_status`
read `APPROVED` in step 7, the circular document is fully validated.

### 9. Same flow for submission documents

Once merchants' PDFs (filename containing `submission`) have been ingested (step 3) and parsed
(step 4), run the identical detection/notify/review flow against `file_type = BID` files
under the `/evaluation/submission/...` routes — same request/response shapes as steps 5-8. A
project/version can have any number of submission PDFs; `POST /evaluation/submission/process-pending`
claims and detects all of them in one call and sends a single batched reviewer email
covering every submission processed in that run (rather than one email per merchant). Each merchant's
PDF gets its own `submission_evaluations` row (and its own `evaluation_id`), so approve/correct
each merchant independently via `/evaluation/submission/<evaluation_id>/review`:

```bash
curl -X POST http://localhost:8011/evaluation/submission/process-pending | jq
curl http://localhost:8011/evaluation/submission/pending | jq
curl http://localhost:8011/evaluation/submission/<evaluation_id> | jq
curl -X POST http://localhost:8011/evaluation/submission/<evaluation_id>/notify | jq
curl -X POST http://localhost:8011/evaluation/submission/<evaluation_id>/review \
  -H "Content-Type: application/json" \
  -d '{"topic": "payment", "employee_id": "<employee_id>"}' | jq
```

Each submission file gets its own row in `submission_evaluations`, linked to the same `project_id`/
`version` as the circular, so the normalization view (see `/normalization/...` below) can
compare every merchant's approved Payment/Service section content against the circular's
approved sections, side by side, no matter how many merchants submitted.

## Reference: all endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/setup/database` | Create/reset schema |
| POST | `/ingestion/poll-gmail?max_results=N` | Fetch + ingest unread PDF emails |
| POST | `/parsing/process-pending` | Parse received PDFs via the async parser |
| POST | `/evaluation/circular/process-pending` | Circular: detect payment/service sections + notify reviewer |
| GET | `/evaluation/circular/pending` | Circular: list evaluations awaiting review |
| GET | `/evaluation/circular/{evaluation_id}` | Circular: get one evaluation's full detail |
| POST | `/evaluation/circular/{evaluation_id}/notify` | Circular: resend the reviewer notification |
| POST | `/evaluation/circular/{evaluation_id}/review` | Circular: approve or correct a payment/service section |
| POST | `/evaluation/submission/process-pending` | Submission: detect payment/service sections + notify reviewer |
| GET | `/evaluation/submission/pending` | Submission: list evaluations awaiting review |
| GET | `/evaluation/submission/{evaluation_id}` | Submission: get one evaluation's full detail |
| POST | `/evaluation/submission/{evaluation_id}/notify` | Submission: resend the reviewer notification |
| POST | `/evaluation/submission/{evaluation_id}/review` | Submission: approve or correct a payment/service section |
| POST | `/employees` | Register a reviewer (admin assigns name/email/password/LiteLLM key) |
| GET | `/employees` | List reviewers (never includes the LiteLLM key) |
| GET | `/health` | Liveness check |

The bare `/evaluation/...` routes (without `/circular/`) still work and behave identically
to `/evaluation/circular/...` — kept only for backward compatibility with earlier curl
history. Prefer the `/evaluation/circular/...` form for anything new.

