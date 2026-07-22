# Tender-Bid Pipeline: Gmail → Drive → Postgres → Parsing → Evaluation

End-to-end pipeline, in the order it actually runs:

```text
Gmail unread PDF email (1 tender + any number of bidder PDFs as attachments)
  → Gmail OAuth (readonly + send + drive scopes)
  → validate `PROJECT-CODE: Project Name` subject
  → versioned Drive folder: "<code> - <name>" / "Version 00N - <datetime>"
  → upload every PDF to Drive, record each in Postgres (RECEIVED) — one row per file, so any
    number of bidder PDFs in the same email are ingested independently
  → async PDF parser (docling) submits/polls/fetches markdown, output_tree.json, TOC, images
  → parsed artifacts uploaded to Drive (parsed_results/...), TOC text + tree links stored in Postgres (PARSED)
  → Groq detects which TOC heading covers Technical Requirements vs Price/Commercial
  → matching section content pulled from output_tree.json, stored in tender_evaluations / bid_evaluations (SUGGESTED)
  → an agent (pydantic-ai + Groq) drafts and sends ONE reviewer notification email per
    project/version per processing run, covering every newly-suggested file in that run
  → human reviewer approves or corrects each topic, per file, via REST endpoints
  → the normalization view merges the tender's approved sections with every approved bid's
    sections into one side-by-side comparison, computed on demand
```

A project/version can have exactly one tender document and any number of bid documents —
bid PDFs are matched to the tender purely by living in the same email/project/version;
file names only need to contain `tender` or `bid` to be classified. If two attachments in
the same email share an identical file name (e.g. two bidders both send `bid.pdf`), the
pipeline automatically disambiguates them (`bid.pdf`, `bid (2).pdf`, ...) before upload/
persistence so neither is dropped.

## One-time setup

```bash
python3 -m venv pydantic_backend/.venv
source pydantic_backend/.venv/bin/activate
pip install -r pydantic_backend/requirements.txt
cp pydantic_backend/.env.example pydantic_backend/.env
# edit pydantic_backend/.env: GMAIL_CLIENT_ID/SECRET, DATABASE_URL (URL-encode special
# chars, e.g. @ -> %40), PARSER_BASE_URL, GROQ_API_KEY, REVIEWER_EMAIL
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
plus `employees` and `tender_evaluations` (left intact unless cascaded).

### 2. Register at least one reviewer (employee)

```bash
curl -X POST http://localhost:8011/employees \
  -H "Content-Type: application/json" \
  -d '{"name": "Your Name", "email": "you@example.com"}' | jq
```

Save the returned `employee_id` — needed later to approve/correct sections.

### 3. Poll Gmail for unread tender/bid PDFs and ingest them

```bash
curl -X POST "http://localhost:8011/ingestion/poll-gmail?max_results=20" | jq
```

For each new unread email matching `PROJECT-CODE: Project Name` with a PDF attachment:
creates/updates the project, uploads the PDF to a versioned Drive folder, and inserts a
`file_repository` row with `processing_status = RECEIVED`. Already-ingested emails are
skipped silently. File name must contain `tender` or `bid` to be classified accordingly
(only `tender` files go through section evaluation).

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

### 5. Detect Technical/Price sections + notify the reviewer

```bash
curl -X POST http://localhost:8011/evaluation/tender/process-pending | jq
```

For every `PARSED` file with `file_type = TENDER` and no evaluation yet: sends the TOC to
Groq to pick the Technical Requirements heading and the Price/Commercial heading, looks up
each heading's full text in `output_tree.json`, and inserts a `tender_evaluations` row
(`technical_status`/`price_status = SUGGESTED`). Once the whole claimed batch is detected,
a pydantic-ai agent (Groq-backed) drafts and sends ONE notification email per
project/version to `REVIEWER_EMAIL` via a `send_reviewer_email` tool, summarizing every
file that got a new suggestion in this run (there's normally just one tender per
project/version, but the same batching applies to `/evaluation/bid/process-pending` below,
where several bidder files processed together are covered by a single email).

Returns the list of newly created `evaluation_id`s.

### 6. Resend the notification (if `REVIEWER_EMAIL` was unset, or you want to nudge again)

```bash
curl -X POST http://localhost:8011/evaluation/tender/<evaluation_id>/notify | jq
```

### 7. Inspect a suggestion

```bash
curl http://localhost:8011/evaluation/tender/<evaluation_id> | jq
```

Or list everything still awaiting a decision:

```bash
curl http://localhost:8011/evaluation/tender/pending | jq
```

### 8. Approve or correct each topic (technical / price)

Approve the AI suggestion as-is:

```bash
curl -X POST http://localhost:8011/evaluation/tender/<evaluation_id>/review \
  -H "Content-Type: application/json" \
  -d '{"topic": "technical", "employee_id": "<employee_id>"}' | jq
```

Reject and replace with the correct TOC heading (copy it verbatim from `parse_toc` /
`GET /evaluation/tender/<evaluation_id>`):

```bash
curl -X POST http://localhost:8011/evaluation/tender/<evaluation_id>/review \
  -H "Content-Type: application/json" \
  -d '{"topic": "price", "employee_id": "<employee_id>", "corrected_heading": "1.4 Price Bid Evaluation"}' | jq
```

Repeat for both `technical` and `price`. Once both `technical_status` and `price_status`
read `APPROVED` in step 7, the tender document is fully validated.

### 9. Same flow for bid documents

Once bidders' PDFs (filename containing `bid`) have been ingested (step 3) and parsed
(step 4), run the identical detection/notify/review flow against `file_type = BID` files
under the `/evaluation/bid/...` routes — same request/response shapes as steps 5-8. A
project/version can have any number of bid PDFs; `POST /evaluation/bid/process-pending`
claims and detects all of them in one call and sends a single batched reviewer email
covering every bid processed in that run (rather than one email per bidder). Each bidder's
PDF gets its own `bid_evaluations` row (and its own `evaluation_id`), so approve/correct
each bidder independently via `/evaluation/bid/<evaluation_id>/review`:

```bash
curl -X POST http://localhost:8011/evaluation/bid/process-pending | jq
curl http://localhost:8011/evaluation/bid/pending | jq
curl http://localhost:8011/evaluation/bid/<evaluation_id> | jq
curl -X POST http://localhost:8011/evaluation/bid/<evaluation_id>/notify | jq
curl -X POST http://localhost:8011/evaluation/bid/<evaluation_id>/review \
  -H "Content-Type: application/json" \
  -d '{"topic": "technical", "employee_id": "<employee_id>"}' | jq
```

Each bid file gets its own row in `bid_evaluations`, linked to the same `project_id`/
`version` as the tender, so the normalization view (see `/normalization/...` below) can
compare every bidder's approved Technical/Price section content against the tender's
approved sections, side by side, no matter how many bidders submitted.

## Reference: all endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/setup/database` | Create/reset schema |
| POST | `/ingestion/poll-gmail?max_results=N` | Fetch + ingest unread PDF emails |
| POST | `/parsing/process-pending` | Parse received PDFs via the async parser |
| POST | `/evaluation/tender/process-pending` | Tender: detect technical/price sections + notify reviewer |
| GET | `/evaluation/tender/pending` | Tender: list evaluations awaiting review |
| GET | `/evaluation/tender/{evaluation_id}` | Tender: get one evaluation's full detail |
| POST | `/evaluation/tender/{evaluation_id}/notify` | Tender: resend the reviewer notification |
| POST | `/evaluation/tender/{evaluation_id}/review` | Tender: approve or correct a technical/price section |
| POST | `/evaluation/bid/process-pending` | Bid: detect technical/price sections + notify reviewer |
| GET | `/evaluation/bid/pending` | Bid: list evaluations awaiting review |
| GET | `/evaluation/bid/{evaluation_id}` | Bid: get one evaluation's full detail |
| POST | `/evaluation/bid/{evaluation_id}/notify` | Bid: resend the reviewer notification |
| POST | `/evaluation/bid/{evaluation_id}/review` | Bid: approve or correct a technical/price section |
| POST | `/employees` | Register a reviewer |
| GET | `/employees` | List reviewers |
| GET | `/health` | Liveness check |

The bare `/evaluation/...` routes (without `/tender/`) still work and behave identically
to `/evaluation/tender/...` — kept only for backward compatibility with earlier curl
history. Prefer the `/evaluation/tender/...` form for anything new.

