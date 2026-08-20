# ============================================================================
#  Batch Builder - build the distributable
# ============================================================================
#
#  WHAT THIS DOES
#    1. Runs the whole test suite. If anything fails, it stops without
#       packaging. The suite includes a byte-for-byte check that Tox4 output is
#       unchanged from the files Ascent already consumes, so a failure here is
#       a real problem, not a formality.
#    2. Runs PyInstaller to produce a self-contained folder.
#    3. Smoke-tests the executable it just built. PyInstaller can produce a
#       binary that fails on import while every test passes, so "it compiled"
#       is not the same as "it starts".
#    4. Copies the example config and README in beside it, and creates the
#       folders the application expects.
#
#  HOW TO RUN IT
#    Easiest:  double-click build.bat in the project root
#    Or, in the VS Code terminal:
#        powershell -ExecutionPolicy Bypass -File build\build.ps1
#
#  OUTPUT
#    build\dist\BatchBuilder\
#    Copy that ENTIRE folder to wherever analysts will run it from. The .exe
#    alone is not enough - the _internal folder next to it holds the Python
#    runtime, the page templates and the stylesheet.
#
#  WHY A FOLDER AND NOT A SINGLE FILE
#    A one-file build unpacks itself into a temp directory on every launch.
#    That is slow from a network share and is much more likely to be flagged by
#    antivirus. A folder build starts immediately and looks like ordinary files.
# ============================================================================

$ErrorActionPreference = "Stop"

# This script lives in build\, so the project root is one level up.
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# ---------------------------------------------------------------------------
# Pick the interpreter.
# ---------------------------------------------------------------------------
# Prefer the project's own virtual environment, so the build uses exactly the
# package versions setup.ps1 installed rather than whatever is on PATH.

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $python = $venvPython
    Write-Host "Using the project virtual environment (.venv)." -ForegroundColor Green
} else {
    Write-Host "No .venv found - falling back to Python on PATH." -ForegroundColor Yellow
    Write-Host "Run setup.bat first for a clean, reproducible build." -ForegroundColor Yellow
    $python = "python"
}

# The package lives under src\, which PyInstaller and pytest both need to find.
$env:PYTHONPATH = Join-Path $root "src"

# ---------------------------------------------------------------------------
# 1. Tests
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "== Running tests before packaging ==" -ForegroundColor Cyan
& $python -m pytest -q
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Tests failed. Not packaging." -ForegroundColor Red
    Write-Host "Do not ship a build with a failing suite - the golden tests are" -ForegroundColor Red
    Write-Host "what guarantee the Tox4 files Ascent reads have not changed." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# 2. Package
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "== Building ==" -ForegroundColor Cyan
Write-Host "(this takes a minute or two the first time)"

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath "build\dist" `
    --workpath "build\work" `
    "build\batchbuilder.spec"
if ($LASTEXITCODE -ne 0) {
    Write-Host "PyInstaller failed." -ForegroundColor Red
    exit 1
}

$dist = Join-Path $root "build\dist\BatchBuilder"
$exe  = Join-Path $dist "BatchBuilder.exe"

# ---------------------------------------------------------------------------
# 3. Smoke-test what was built
# ---------------------------------------------------------------------------
# PyInstaller runs its entry script as a top-level module with no package
# context. A build can therefore fail on import alone while every test passes,
# which is exactly how a broken build reaches an analyst.

Write-Host ""
Write-Host "== Smoke-testing the executable ==" -ForegroundColor Cyan
$reported = & $exe --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "The built executable does not start:" -ForegroundColor Red
    Write-Host $reported
    exit 1
}
Write-Host "  $reported" -ForegroundColor Green

# ---------------------------------------------------------------------------
# 4. Finish the folder
# ---------------------------------------------------------------------------
# The example config ships beside the exe so the lab can copy and edit it
# without needing this source tree.
Copy-Item "batchbuilder.example.json" -Destination $dist -Force
Copy-Item "README.md" -Destination $dist -Force

# Folders the application expects next to itself.
New-Item -ItemType Directory -Force -Path (Join-Path $dist "hamilton files") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dist "ins_files") | Out-Null

$size = "{0:N0} MB" -f ((Get-ChildItem $dist -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB)

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host " Build complete." -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Folder : $dist"
Write-Host "  Size   : $size"
Write-Host ""
Write-Host "Copy that ENTIRE folder to the share and run BatchBuilder.exe."
Write-Host "The .exe on its own will not work - it needs _internal beside it."
Write-Host ""
