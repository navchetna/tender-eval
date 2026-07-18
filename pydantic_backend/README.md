# Gmail → PostgreSQL tender ingestion

This is the current first workflow stage. Kafka, Google Drive uploads, PDF parsing, and bid evaluation are deliberately out of scope for now.

```text
Gmail unread PDF email
  → Gmail OAuth token
  → read subject, sender, received time, and PDF bytes in memory
  → validate `PROJECT-CODE: Project Name`
  → PostgreSQL transaction creates/finds project and increments version
  → PostgreSQL records each PDF as RECEIVED
```

## Safe configuration

Create a local `.env` from `.env.example`. Put the Gmail client ID/secret and **actual Supabase password** there; never commit it. Run `python -m pydantic_backend.gmail_auth` once to open Google consent and write a refresh token to `.secrets/gmail-token.json`.

Before authorizing, enable the Gmail API in the Google Cloud project and ensure this OAuth client is a Desktop application. The service uses the minimal `gmail.readonly` scope.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r pydantic_backend/requirements.txt
cp pydantic_backend/.env.example .env
# edit .env locally
python -m pydantic_backend.gmail_auth
python -m pydantic_backend.main
```

Initialize the two database tables once:

```bash
curl -X POST http://localhost:8011/setup/database
```

Then poll Gmail and persist matching unread PDF emails:

```bash
curl -X POST 'http://localhost:8011/ingestion/poll-gmail?max_results=20'
```

`projects` is the source of truth and a transaction-level advisory lock prevents two polling runs from allocating the same project version. The `file_repository` records email provenance, checksum, size, classification, and a `RECEIVED` status. Gmail messages are not marked read yet, so duplicate handling is based on `(email_message_id, file_name)`.
