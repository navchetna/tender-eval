@echo off
:: ---------------------------------------------------------------------------
:: PRIMARY deployment: Intel NPU fast tier via OpenVINO Model Server (OVMS)
:: serving Qwen3-4B-Instruct-2507 (INT4, NPU-optimised).
::
:: OVMS is a Windows-native process (it needs direct NPU device access), so it
:: is started here on the host and reached from the containers through
:: host.docker.internal:8000.
::
:: If OVMS cannot start, the stack still runs: LiteLLM is configured with an
:: automatic fallback to the cloud model (see litellm-config.yaml
:: router_settings.fallbacks), and groq_run.bat is the fully cloud path.
:: ---------------------------------------------------------------------------
setlocal EnableExtensions EnableDelayedExpansion

set "COMPOSE_DIR=%~dp0"
set "INTEL_ROOT=%~dp0..\..\.."
set "OVMS_DIR=%INTEL_ROOT%\ovms\ovms"
set "OVMS_MODELS=%INTEL_ROOT%\ovms\models"
set "OVMS_CONFIG=%OVMS_MODELS%\config.json"

echo [INFO] Deployment mode : NPU (OpenVINO Model Server)
echo [INFO] OVMS binary     : %OVMS_DIR%\ovms.exe
echo [INFO] Model repo      : %OVMS_MODELS%

if not exist "%OVMS_DIR%\ovms.exe" (
    echo [ERROR] ovms.exe not found at %OVMS_DIR%
    echo [HINT ] Run groq_run.bat instead for the cloud fallback deployment.
    exit /b 1
)
if not exist "%OVMS_CONFIG%" (
    echo [ERROR] OVMS model repository config not found: %OVMS_CONFIG%
    echo [HINT ] It must register the Qwen3 mediapipe graph under mediapipe_config_list.
    exit /b 1
)

:: ---- 1. Bring up OVMS: reuse > service > console process -----------------
curl -s -o nul -w "%%{http_code}" --max-time 3 http://localhost:8000/v3/models > "%TEMP%\tb_probe.txt" 2>nul
set /p PROBE=<"%TEMP%\tb_probe.txt"
del "%TEMP%\tb_probe.txt" 2>nul
if "%PROBE%"=="200" (
    echo [INFO] OVMS already responding on port 8000 - reusing it.
    sc query ovms 2>nul | find "RUNNING" >nul 2>&1
    if not errorlevel 1 (
        echo [INFO] Source: the ovms Windows service ^(survives reboot^).
    ) else (
        echo [WARN] Source: a console-mode OVMS, NOT the service. It dies on
        echo [WARN] logoff/reboot. Run install_npu_service.bat to make it permanent.
    )
    goto :ovms_wait
)

:: Installed as a service by install_npu_service.bat? Prefer that - it survives
:: reboots and logoff. Starting it needs admin, so this is best-effort only.
sc query ovms >nul 2>&1
if not errorlevel 1 (
    echo [INFO] ovms service detected - attempting to start it...
    net start ovms >nul 2>&1
    if not errorlevel 1 (
        echo [INFO] ovms service started.
        goto :ovms_wait
    )
    echo [WARN] Could not start the ovms service ^(needs admin^) - falling back
    echo [WARN] to a console process for this session.
)

echo [INFO] Starting OVMS on port 8000 ^(NPU^)...
start "OVMS-NPU" /min cmd /c ""%OVMS_DIR%\setupvars.bat" && "%OVMS_DIR%\ovms.exe" --rest_port 8000 --config_path "%OVMS_CONFIG%" --log_level INFO"

:ovms_wait
:: The REST port answers immediately, but the model is only servable once it has been
:: compiled for the NPU (~1 min cold). So probe a real completion, not /v3/models, which
:: returns 200 long before the graph reaches AVAILABLE.
echo [INFO] Waiting for OVMS to finish compiling the model for the NPU...
set "OVMS_READY="
for /l %%i in (1,1,60) do (
    if not defined OVMS_READY (
        curl -s -o nul -w "%%{http_code}" --max-time 20 ^
             -H "Content-Type: application/json" ^
             -d "{\"model\":\"ervin0307/Qwen3-4B-Instruct-2507-int4-ov\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":4}" ^
             http://localhost:8000/v3/chat/completions > "%TEMP%\tb_ovms.txt" 2>nul
        set /p OCODE=<"%TEMP%\tb_ovms.txt"
        if "!OCODE!"=="200" set "OVMS_READY=1"
        if not defined OVMS_READY (
            set /a WAITED=%%i*5
            echo        ... compiling on NPU ^(!WAITED!s^)
            timeout /t 5 /nobreak >nul
        )
    )
)
del "%TEMP%\tb_ovms.txt" 2>nul

if not defined OVMS_READY (
    echo [WARN] OVMS did not become ready in time.
    echo [WARN] The stack will still start - LiteLLM will fall back to the cloud model.
    echo [HINT] For a guaranteed-clean cloud run, use groq_run.bat instead.
) else (
    echo [OK] OVMS ready - NPU model is serving on http://localhost:8000/v3
)

:: ---- 2. Bring up the container stack ------------------------------------
pushd "%COMPOSE_DIR%" || (echo [ERROR] Cannot enter %COMPOSE_DIR% & exit /b 1)

call :ensure_parser

:: Consumed by docker-compose.yaml -> backend.environment.LITELLM_FAST_MODEL.
set "LITELLM_FAST_MODEL=npu-qwen3-4b"
echo.
echo [INFO] Fast model      : %LITELLM_FAST_MODEL%

docker compose up -d --build
if errorlevel 1 (
    echo [ERROR] docker compose failed.
    popd
    exit /b 1
)

:: ---- 3. Verify the NPU route end-to-end through LiteLLM -----------------
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
echo [INFO] Verifying NPU route through LiteLLM...

:: LiteLLM is not listening the instant its container starts (config load + DB migrations),
:: so retry instead of probing once. Reads the key from litellm.env rather than hardcoding it.
set "MASTER_KEY="
for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"LITELLM_MASTER_KEY=" litellm.env') do set "MASTER_KEY=%%b"
if not defined MASTER_KEY (
    echo [WARN] LITELLM_MASTER_KEY not found in litellm.env - skipping route check.
    goto :route_done
)

set "ROUTE_OK="
for /l %%i in (1,1,24) do (
    if not defined ROUTE_OK (
        curl -s -o nul -w "%%{http_code}" --max-time 120 ^
             -H "Authorization: Bearer !MASTER_KEY!" ^
             -H "Content-Type: application/json" ^
             -d "{\"model\":\"npu-qwen3-4b\",\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}],\"max_tokens\":4}" ^
             http://localhost:4000/chat/completions > "%TEMP%\tb_route.txt" 2>nul
        set /p RCODE=<"%TEMP%\tb_route.txt"
        if "!RCODE!"=="200" set "ROUTE_OK=1"
        if not defined ROUTE_OK timeout /t 5 /nobreak >nul
    )
)
del "%TEMP%\tb_route.txt" 2>nul

if defined ROUTE_OK (
    echo [OK] NPU route answered through LiteLLM.
) else (
    echo [WARN] NPU route did not answer. LiteLLM will auto-fall back to the cloud model,
    echo [WARN] so the demo still works - but the NPU will not be exercised.
)
:route_done

echo.
echo [DONE] Frontend: http://localhost:3002    Backend: http://localhost:8011
echo [DONE] OVMS/NPU: http://localhost:8000/v3/models
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
