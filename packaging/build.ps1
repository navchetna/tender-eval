<#
    Builds the Tender Evaluation desktop app - the single entry point for packaging.

        powershell -ExecutionPolicy Bypass -File packaging\build.ps1              # app bundle
        powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Installer   # + installer

    Requirements (build machine only - the target machine needs none of these):
        - uv (https://docs.astral.sh/uv/) - provisions Python 3.12 + the build venv itself
        - Node.js 20+ / npm - builds the static UI
        - For -Installer: Inno Setup 6 (ISCC.exe on PATH or in its default install location)

    Output:
        dist\TenderEval\TenderEval.exe                          portable one-folder bundle
        packaging\installer\Output\TenderEval-Setup-<ver>.exe   with -Installer
#>
[CmdletBinding()]
param(
    [switch]$Installer
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Invoke-Step([string]$Name, [scriptblock]$Block) {
    Write-Host "[build] $Name"
    & $Block
    if ($LASTEXITCODE -ne 0) { throw "[build] '$Name' failed (exit $LASTEXITCODE)" }
}

# 1. Python build venv (.venv-desktop, separate from any dev venv).
Invoke-Step "Creating build venv" { uv venv --python 3.12 --allow-existing .venv-desktop }
Invoke-Step "Installing desktop requirements" { uv pip install --python .venv-desktop -r pydantic_backend\requirements-desktop.txt }

# 2. Static UI. NEXT_PUBLIC_API_BASE_URL=/api: the exe serves the API on the same origin.
Push-Location frontend
try {
    # `npm ci` wipes node_modules first, which on Windows intermittently fails with EBUSY when an
    # editor/indexer/AV briefly holds a folder open - so only reinstall when the lockfile changed.
    $installed = "node_modules\.package-lock.json"
    if (-not (Test-Path $installed) -or (Get-Item package-lock.json).LastWriteTime -gt (Get-Item $installed).LastWriteTime) {
        Invoke-Step "Installing UI dependencies" { npm ci --no-audit --no-fund }
    } else {
        Write-Host "[build] UI dependencies up to date"
    }
    $env:NEXT_OUTPUT = "export"
    $env:NEXT_PUBLIC_API_BASE_URL = "/api"
    Invoke-Step "Building static UI" { npx next build }
} finally {
    Remove-Item Env:NEXT_OUTPUT, Env:NEXT_PUBLIC_API_BASE_URL -ErrorAction SilentlyContinue
    Pop-Location
}
if (-not (Test-Path frontend\out\index.html)) { throw "[build] frontend\out\index.html missing" }

# 3. PyInstaller bundle.
foreach ($dir in @("build\TenderEval", "dist\TenderEval")) {
    if (Test-Path $dir) { Remove-Item -Recurse -Force $dir }
}
Invoke-Step "Running PyInstaller" {
    .venv-desktop\Scripts\pyinstaller.exe packaging\tender_eval.spec --noconfirm --distpath dist --workpath build
}
$exe = Join-Path $Root "dist\TenderEval\TenderEval.exe"
if (-not (Test-Path $exe)) { throw "[build] $exe not found" }
Write-Host "[build] Bundle ready: $exe"

# 4. Optional installer.
if ($Installer) {
    $iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
    if (-not $iscc) {
        $iscc = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
        ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    }
    if (-not $iscc) { throw "[build] Inno Setup 6 (ISCC.exe) not found - install it to build the installer." }
    Invoke-Step "Compiling installer" { & $iscc packaging\installer\tender_eval.iss }
    Write-Host "[build] Installer written to packaging\installer\Output\"
}

Write-Host "[build] Done."
