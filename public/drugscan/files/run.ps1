# ============================================================================
#  Batch Builder - run from source
# ============================================================================
#
#  Starts the application without building an .exe. This is the quickest way to
#  test on the lab network: if it works here, the packaged build will too,
#  because they run identical code.
#
#  USAGE
#    run.bat                      normal start, opens your browser
#    run.bat --demo               run against recorded data, no database needed
#    run.bat --port 8765          use a fixed port
#    run.bat --no-browser         do not open a browser
#
#  Close the window to stop the application.
# ============================================================================

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
Set-Location $root

$venvPython = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "No .venv found. Run setup.bat first." -ForegroundColor Red
    exit 1
}

# The package lives under src\, which is not on the default import path.
$env:PYTHONPATH = Join-Path $root "src"

# --demo with no fixture path given: fill in the one that ships with the tests,
# so `run.bat --demo` just works.
$arguments = @($args)
$demoIndex = [Array]::IndexOf($arguments, "--demo")
if ($demoIndex -ge 0) {
    $next = if ($demoIndex + 1 -lt $arguments.Count) { $arguments[$demoIndex + 1] } else { $null }
    if (-not $next -or $next.StartsWith("--")) {
        $fixture = Join-Path $root "tests\fixtures\apollo_fixture.json"
        $arguments = $arguments[0..$demoIndex] + @($fixture) +
                     $(if ($demoIndex + 1 -lt $arguments.Count) { $arguments[($demoIndex + 1)..($arguments.Count - 1)] } else { @() })
        Write-Host "Demo mode: using $fixture" -ForegroundColor Yellow
    }
}

Write-Host "Starting Batch Builder ..." -ForegroundColor Cyan
Write-Host "(the address it listens on is printed below; close this window to stop)"
Write-Host ""

& $venvPython -m batchbuilder @arguments
