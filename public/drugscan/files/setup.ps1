# ============================================================================
#  Batch Builder - one-time setup
# ============================================================================
#
#  WHAT THIS DOES
#    1. Checks you have a usable Python.
#    2. Creates a private virtual environment in .venv, so nothing is installed
#       into the machine's system Python. Nothing outside this folder changes.
#    3. Installs the dependencies. It prefers the wheels bundled in
#       vendor\wheels, so this works with no internet access at all. If that
#       folder is missing it falls back to downloading from PyPI.
#    4. Runs the test suite, so you know the code is sound before you build.
#
#  HOW TO RUN IT
#    Easiest:  double-click setup.bat
#    Or, in the VS Code terminal:
#        powershell -ExecutionPolicy Bypass -File setup.ps1
#
#    The -ExecutionPolicy Bypass part matters: many managed Windows machines
#    refuse to run unsigned .ps1 files without it. It applies to this one
#    command only and changes nothing permanently.
#
#  AFTER THIS
#    Run build.bat (or build\build.ps1) to produce the .exe.
# ============================================================================

$ErrorActionPreference = "Stop"

# Always work relative to this script, not wherever the terminal happens to be.
$root = $PSScriptRoot
Set-Location $root

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host " Batch Builder - setup" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# ---------------------------------------------------------------------------
# 1. Find a Python interpreter.
# ---------------------------------------------------------------------------
# Prefer the "py" launcher, which is what the standard python.org installer
# puts on PATH; fall back to plain "python".

$python = $null
foreach ($candidate in @("py", "python")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { $python = $candidate; break }
}

if (-not $python) {
    Write-Host "No Python found on PATH." -ForegroundColor Red
    Write-Host ""
    Write-Host "Install Python 3.10 or newer from https://www.python.org/downloads/"
    Write-Host "and tick 'Add python.exe to PATH' during installation."
    Write-Host "If your organisation provides Python through the Software Center,"
    Write-Host "use that instead."
    exit 1
}

$versionText = & $python -c "import sys; print('.'.join(map(str, sys.version_info[:3])))"
Write-Host "Using Python $versionText  (via '$python')" -ForegroundColor Green

# The code uses `X | None` type syntax, which needs 3.10 or newer.
$major, $minor = & $python -c "import sys; print(sys.version_info[0]); print(sys.version_info[1])"
if ([int]$major -lt 3 -or ([int]$major -eq 3 -and [int]$minor -lt 10)) {
    Write-Host "Python 3.10 or newer is required (found $versionText)." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# 2. Create the virtual environment.
# ---------------------------------------------------------------------------
# A venv keeps this project's packages separate from anything else on the
# machine. Deleting the .venv folder undoes everything this script installs.

$venvPython = Join-Path $root ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    Write-Host "Virtual environment already exists - reusing it." -ForegroundColor Green
} else {
    Write-Host "Creating virtual environment in .venv ..." -ForegroundColor Cyan
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Could not create the virtual environment." -ForegroundColor Red
        exit 1
    }
}

# ---------------------------------------------------------------------------
# 3. Install dependencies.
# ---------------------------------------------------------------------------
# Offline first. vendor\wheels holds every package this project needs, already
# downloaded, so a machine with no PyPI access still works.
#   --no-index      : do not contact PyPI at all
#   --find-links    : look in this folder instead

$wheels = Join-Path $root "vendor\wheels"
$haveWheels = (Test-Path $wheels) -and
              ((Get-ChildItem $wheels -Filter *.whl -ErrorAction SilentlyContinue).Count -gt 0)

Write-Host ""
if ($haveWheels) {
    $count = (Get-ChildItem $wheels -Filter *.whl).Count
    Write-Host "Installing from bundled wheels ($count found) - no internet needed." -ForegroundColor Cyan
    & $venvPython -m pip install --quiet --no-index --find-links $wheels -r requirements-dev.txt
} else {
    Write-Host "No bundled wheels found; downloading from PyPI." -ForegroundColor Yellow
    Write-Host "If this machine has no internet access, this step will fail." -ForegroundColor Yellow
    & $venvPython -m pip install --quiet --upgrade pip
    & $venvPython -m pip install --quiet -r requirements-dev.txt
}

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Installing dependencies failed." -ForegroundColor Red
    Write-Host "If this machine is behind a proxy with no PyPI access, make sure"
    Write-Host "the vendor\wheels folder came across with this project."
    exit 1
}
Write-Host "Dependencies installed." -ForegroundColor Green

# ---------------------------------------------------------------------------
# 4. Run the tests.
# ---------------------------------------------------------------------------
# The suite includes a byte-for-byte check that Tox4 output is unchanged from
# the files Ascent already consumes. If that fails, do not ship the build.

Write-Host ""
Write-Host "Running the test suite ..." -ForegroundColor Cyan
& $venvPython -m pytest -q
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Tests failed. Setup finished, but do not build until this is" -ForegroundColor Red
    Write-Host "understood - the suite guards the Tox4 output format." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Done.
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host " Setup complete." -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  Run the app now :  run.bat"
Write-Host "  Build the .exe  :  build.bat"
Write-Host ""
Write-Host "In VS Code, use Terminal > Run Task to do the same things."
Write-Host ""
