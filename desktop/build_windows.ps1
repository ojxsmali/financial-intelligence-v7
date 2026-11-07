# Reproducible Windows build of FinancialIntelligenceV7.exe
# Usage (from the project root):  powershell -ExecutionPolicy Bypass -File desktop\build_windows.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
}
$py = Join-Path $root ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r requirements-dev.txt --quiet

Write-Host "Running tests..."
& $py -m pytest -q -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw "Tests failed; not building." }

& $py desktop\make_icon.py | Out-Null
Write-Host "Building executable (takes a few minutes)..."
& $py -m PyInstaller desktop\fip_desktop.spec --noconfirm --clean --distpath dist --workpath build
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

$exe = Join-Path $root "dist\FinancialIntelligenceV7.exe"
if (Select-String -Path $exe -Pattern "AIza[0-9A-Za-z_\-]{35}" -Quiet) { throw "Secret-like string found in exe!" }
Write-Host ("Built {0} ({1:N0} MB)" -f $exe, ((Get-Item $exe).Length / 1MB))
