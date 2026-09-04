@echo off
:: ---------------------------------------------------------------------------
:: Fallback deployment: cloud (Groq) fast tier, no local model server required.
:: Use this when the NPU box is unavailable or OVMS will not start.
:: The primary, NPU-backed path is npu_run.bat.
:: ---------------------------------------------------------------------------
setlocal EnableExtensions EnableDelayedExpansion

set "COMPOSE_DIR=%~dp0"
set "INTEL_ROOT=%~dp0..\..\.."
pushd "%COMPOSE_DIR%" || (echo [ERROR] Cannot enter %COMPOSE_DIR% & exit /b 1)

call :ensure_parser

:: Consumed by docker-compose.yaml -> backend.environment.LITELLM_FAST_MODEL,
:: which overrides the value baked into backend.env.
set "LITELLM_FAST_MODEL=groq-gpt-oss-120b"

echo [INFO] Deployment mode : GROQ (cloud fallback)
echo [INFO] Fast model      : %LITELLM_FAST_MODEL%

docker compose up -d --build
if errorlevel 1 (
    echo [ERROR] docker compose failed.
    popd
    exit /b 1
)

echo.
echo [INFO] Waiting for backend to become ready...
set "READY="
for /l %%i in (1,1,30) do (
    if not defined READY (
        curl -s -o nul -w "%%{http_code}" http://localhost:8011/docs > "%TEMP%\tb_code.txt" 2>nul
        set /p CODE=<"%TEMP%\tb_code.txt"
        if "!CODE!"=="200" set "READY=1"
        if not defined READY timeout /t 2 /nobreak >nul
    )
)
del "%TEMP%\tb_code.txt" 2>nul

if not defined READY (
    echo [WARN] Backend did not report ready in time. Check: docker logs tender-bid-backend-1
) else (
    echo [OK] Backend ready.
)

echo.
echo [INFO] Verifying Groq route through LiteLLM...

:: LiteLLM is not listening the instant its container starts, so retry rather than
:: probing once. Reads the key from litellm.env rather than hardcoding it.
set "MASTER_KEY="
for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"LITELLM_MASTER_KEY=" litellm.env') do set "MASTER_KEY=%%b"
if not defined MASTER_KEY (
    echo [WARN] LITELLM_MASTER_KEY not found in litellm.env - skipping route check.
    goto :route_done
)

set "ROUTE_OK="
for /l %%i in (1,1,12) do (
    if not defined ROUTE_OK (
        curl -s -o nul -w "%%{http_code}" --max-time 60 ^
             -H "Authorization: Bearer !MASTER_KEY!" ^
             -H "Content-Type: application/json" ^
             -d "{\"model\":\"groq-gpt-oss-120b\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":4}" ^
             http://localhost:4000/chat/completions > "%TEMP%\tb_route.txt" 2>nul
        set /p RCODE=<"%TEMP%\tb_route.txt"
        if "!RCODE!"=="200" set "ROUTE_OK=1"
        if not defined ROUTE_OK timeout /t 5 /nobreak >nul
    )
)
del "%TEMP%\tb_route.txt" 2>nul

if defined ROUTE_OK (
    echo [OK] Groq route answered through LiteLLM.
) else (
    echo [WARN] Groq route did not answer - check GROQ_API_KEY in litellm.env.
)
:route_done

echo.
echo [DONE] Frontend: http://localhost:3002    Backend: http://localhost:8011
popd
endlocal
goto :eof

:: ---------------------------------------------------------------------------
:: The PDF parser is NOT part of this compose project - it lives in its own
:: ("async", under AIComps/.../docling/async), so `docker compose up` here never
:: starts it. Without it every document dies at the Parsed stage.
:: ---------------------------------------------------------------------------
:ensure_parser
curl -s -o nul -w "%%{http_code}" --max-time 5 http://localhost:8010/docs > "%TEMP%\tb_parser.txt" 2>nul
set /p PCODE=<"%TEMP%\tb_parser.txt"
del "%TEMP%\tb_parser.txt" 2>nul
if "%PCODE%"=="200" (
    echo [OK] PDF parser reachable on :8010.
    goto :eof
)
echo [WARN] PDF parser not responding on :8010 - starting its compose project...
pushd "%INTEL_ROOT%\AIComps\input-handlers\pdf\parsers\docling\async" 2>nul
if errorlevel 1 (
    echo [ERROR] Parser compose dir not found - start it manually, or parsing will fail.
    goto :eof
)
docker compose up -d
popd
for /l %%p in (1,1,20) do (
    curl -s -o nul -w "%%{http_code}" --max-time 5 http://localhost:8010/docs > "%TEMP%\tb_parser.txt" 2>nul
    set /p PCODE2=<"%TEMP%\tb_parser.txt"
    if "!PCODE2!"=="200" (
        echo [OK] PDF parser is up.
        del "%TEMP%\tb_parser.txt" 2>nul
        goto :eof
    )
    timeout /t 3 /nobreak >nul
)
del "%TEMP%\tb_parser.txt" 2>nul
echo [WARN] PDF parser still not responding - documents will stall at the Parsed stage.
goto :eof
