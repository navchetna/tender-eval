# Run Commands

All commands run from:

```powershell
cd "C:\Users\Dell pro Precision 7\intel\tender-eval\install\docker"
```

---

## A. First-time setup (once per machine)

```powershell
cd "C:\Users\Dell pro Precision 7\intel\tender-eval\install\docker"
```

```powershell
Start-Process -FilePath ".\install_npu_service.bat" -Verb RunAs
```

```powershell
.\npu_run.bat
```

```powershell
curl.exe -X POST http://localhost:8011/setup/database
```

---

## B. Deployment 1 — NPU (primary)

```powershell
cd "C:\Users\Dell pro Precision 7\intel\tender-eval\install\docker"
```

```powershell
.\npu_run.bat
```

---

## C. Deployment 2 — Groq (cloud fallback)

```powershell
cd "C:\Users\Dell pro Precision 7\intel\tender-eval\install\docker"
```

```powershell
.\groq_run.bat
```

---

## D. Verify

```powershell
docker ps --format "{{.Names}}  {{.Status}}"
```

```powershell
sc.exe query ovms
```

```powershell
curl.exe -s -X POST http://localhost:8000/v3/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"ervin0307/Qwen3-4B-Instruct-2507-int4-ov\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":8}"
```

```powershell
$KEY = (Select-String -Path .\litellm.env -Pattern '^LITELLM_MASTER_KEY=(.+)$').Matches.Groups[1].Value
```

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:4000/chat/completions -Headers @{Authorization="Bearer $KEY";"Content-Type"="application/json"} -Body '{"model":"npu-qwen3-4b","messages":[{"role":"user","content":"ping"}],"max_tokens":8}' | Select-Object model
```

```powershell
docker exec tender-bid-backend-1 printenv LITELLM_FAST_MODEL
```

```powershell
$B = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes('admin@example.com:admin123')); Invoke-RestMethod -Uri http://localhost:8011/evaluation/pending/count -Headers @{Authorization="Basic $B"}
```

Frontend: http://localhost:3002
Backend: http://localhost:8011

---

## E. Logs

```powershell
docker logs --tail 100 tender-bid-backend-1
```

```powershell
docker logs --tail 100 tender-bid-litellm-1
```

```powershell
Get-Content "C:\Users\Dell pro Precision 7\intel\ovms\ovms\ovms_server.log" -Tail 50
```

---

## F. Rebuild after code changes

```powershell
docker compose build backend frontend
```

```powershell
$env:LITELLM_FAST_MODEL="npu-qwen3-4b"; docker compose up -d
```

---

## G. Stop

```powershell
docker compose down
```

```powershell
sc.exe stop ovms
```

---

## H. Switch NPU -> Groq without restarting OVMS

```powershell
$env:LITELLM_FAST_MODEL="groq-gpt-oss-120b"; docker compose up -d backend
```

## I. Switch back to NPU

```powershell
$env:LITELLM_FAST_MODEL="npu-qwen3-4b"; docker compose up -d backend
```
