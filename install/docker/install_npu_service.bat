@echo off
:: ---------------------------------------------------------------------------
:: ONE-TIME setup: register OVMS (Qwen3-4B INT4 on Intel NPU) as an auto-start
:: Windows service, so the NPU model server is already up after every reboot and
:: npu_run.bat never has to launch (or wait on) a console process.
::
:: Requires administrator rights - `sc create` and `ovms.exe install` cannot be
:: done from a normal user token. This script self-elevates via UAC; accept the
:: prompt when it appears.
::
:: Run this once. Afterwards just use npu_run.bat.
:: ---------------------------------------------------------------------------
setlocal EnableExtensions EnableDelayedExpansion

:: ---- self-elevate --------------------------------------------------------
net session >nul 2>&1
if errorlevel 1 (
    echo [INFO] Administrator rights required - requesting elevation...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs" 2>nul
    if errorlevel 1 (
        echo [ERROR] Elevation was refused or failed.
        echo [HINT ] Right-click this file and choose 'Run as administrator'.
        pause
    )
    exit /b
)

set "INTEL_ROOT=%~dp0..\..\.."
set "OVMS_DIR=%INTEL_ROOT%\ovms\ovms"
set "OVMS_MODELS=%INTEL_ROOT%\ovms\models"

echo [INFO] OVMS binary : %OVMS_DIR%\ovms.exe
echo [INFO] Model repo  : %OVMS_MODELS%
echo.

if not exist "%OVMS_DIR%\install_ovms_service.bat" (
    echo [ERROR] install_ovms_service.bat not found under %OVMS_DIR%
    pause
    exit /b 1
)
if not exist "%OVMS_MODELS%\config.json" (
    echo [ERROR] %OVMS_MODELS%\config.json is missing.
    echo [HINT ] Without it OVMS starts but serves no models.
    pause
    exit /b 1
)

:: ---- register the service (vendor script: sc create + ovms.exe install) ---
:: It only writes a placeholder config.json when one is absent, so the existing
:: mediapipe_config_list registering the Qwen3 graph is preserved.
echo [INFO] Registering the ovms service...
call "%OVMS_DIR%\install_ovms_service.bat" "%OVMS_MODELS%"

:: Deliberately NOT checking errorlevel here. The vendor script ends on a
:: `findstr` PATH test whose "not found" result leaks out as errorlevel 1 even
:: on a fully successful install, so its exit code is meaningless. Ask the
:: service control manager what actually exists instead.
sc query ovms >nul 2>&1
if errorlevel 1 (
    echo [ERROR] The ovms service was not created - registration genuinely failed.
    pause
    exit /b 1
)
echo [OK] Service 'ovms' is registered.

:: ---- free port 8000 ------------------------------------------------------
:: A console-mode OVMS (e.g. one launched earlier by npu_run.bat) still owns
:: port 8000; the service would fail to bind and stop immediately.
tasklist /fi "IMAGENAME eq ovms.exe" 2>nul | find /i "ovms.exe" >nul
if not errorlevel 1 (
    echo [INFO] Stopping the existing non-service OVMS process to free port 8000...
    taskkill /F /IM ovms.exe >nul 2>&1
    timeout /t 5 /nobreak >nul
)

:: ---- auto-start ----------------------------------------------------------
:: sc create defaults to demand-start; auto is what makes it survive a reboot
:: without anyone needing an elevated prompt on demo day.
echo [INFO] Setting the service to start automatically at boot...
sc config ovms start= auto >nul 2>&1
sc qc ovms | find "AUTO_START" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Start type is still not AUTO_START - it will need a manual start after reboot.
) else (
    echo [OK] Start type is AUTO_START.
)

:: ---- start ---------------------------------------------------------------
sc query ovms | find "RUNNING" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] Service already running - restarting to pick up current config...
    sc stop ovms >nul 2>&1
    timeout /t 5 /nobreak >nul
)

echo [INFO] Starting the ovms service...
sc start ovms >nul 2>&1
timeout /t 3 /nobreak >nul
sc query ovms | find "RUNNING" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] The service did not reach RUNNING.
    echo [HINT ] Check %OVMS_DIR%\ovms_server.log and confirm nothing else holds port 8000.
    pause
    exit /b 1
)
echo [OK] Service is RUNNING.

:: ---- wait for the NPU compile -------------------------------------------
:: The REST port answers well before the model is servable, so probe a real
:: completion instead of /v3/models (which returns 200 while still compiling).
echo.
echo [INFO] Waiting for the model to compile on the NPU ^(~1 min cold^)...
set "READY="
for /l %%i in (1,1,60) do (
    if not defined READY (
        curl -s -o nul -w "%%{http_code}" --max-time 20 ^
             -H "Content-Type: application/json" ^
             -d "{\"model\":\"ervin0307/Qwen3-4B-Instruct-2507-int4-ov\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":4}" ^
             http://localhost:8000/v3/chat/completions > "%TEMP%\tb_svc.txt" 2>nul
        set /p CODE=<"%TEMP%\tb_svc.txt"
        if "!CODE!"=="200" set "READY=1"
        if not defined READY (
            set /a WAITED=%%i*5
            echo        ... compiling on NPU ^(!WAITED!s^)
            timeout /t 5 /nobreak >nul
        )
    )
)
del "%TEMP%\tb_svc.txt" 2>nul

echo.
if defined READY (
    echo [OK] OVMS service is running and the NPU model is serving.
    echo [OK] It will now start automatically on every boot.
    echo.
    echo      Logs    : %OVMS_DIR%\ovms_server.log
    echo      Status  : sc query ovms
    echo      Stop    : sc stop ovms      ^(needs admin^)
    echo      Remove  : sc delete ovms    ^(needs admin^)
) else (
    echo [WARN] The service started but the model did not answer in time.
    echo [WARN] Check %OVMS_DIR%\ovms_server.log
    echo [HINT] The stack still works - LiteLLM falls back to the cloud model.
)

echo.
pause
endlocal
