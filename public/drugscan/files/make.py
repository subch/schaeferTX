#!/usr/bin/env python3
"""
Batch Builder - project tasks.

One script for everything you need to do with this project. Written in Python
rather than as .bat/.ps1 files for three reasons:

  1. Managed Windows machines routinely refuse to run unsigned PowerShell
     scripts, which makes .ps1 an unreliable entry point.
  2. Gmail blocks .bat and .ps1 attachments outright, even inside a .zip, so a
     project built around them cannot be emailed.
  3. You already need Python installed to build this, so there is no extra
     dependency.

USAGE
    python make.py setup      first-time setup: venv, dependencies, tests
    python make.py test       run the test suite
    python make.py run        start the application (add --demo for no database)
    python make.py build      produce the .exe in build/dist/BatchBuilder
    python make.py clean      remove venv, build output and caches
    python make.py doctor     report what is installed and what is missing

Run `python make.py` with no arguments for a summary.

Anything after the task name is passed straight through, so:

    python make.py run --demo --port 8765
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
SRC = ROOT / "src"
WHEELS = ROOT / "vendor" / "wheels"

MIN_PYTHON = (3, 10)


# ---------------------------------------------------------------------------
# Small console helpers. No colour libraries - this has to work in any terminal.
# ---------------------------------------------------------------------------

def say(message: str = "") -> None:
    print(message, flush=True)


def heading(message: str) -> None:
    say()
    say("=" * 62)
    say(f" {message}")
    say("=" * 62)


def fail(message: str, hint: str = "") -> int:
    say()
    say(f"ERROR: {message}")
    if hint:
        say()
        say(hint)
    return 1


# ---------------------------------------------------------------------------
# Locating interpreters
# ---------------------------------------------------------------------------

def venv_python() -> Path:
    """Path to the interpreter inside the project virtual environment."""
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def require_venv() -> Path:
    python = venv_python()
    if not python.exists():
        raise SystemExit(fail(
            "No virtual environment found.",
            "Run this first:\n    python make.py setup"))
    return python


def run(command: list, **kwargs) -> int:
    """Run a subprocess, echoing what is being run so failures are traceable."""
    say(f"  > {' '.join(str(c) for c in command)}")
    return subprocess.call([str(c) for c in command], cwd=str(ROOT), **kwargs)


def child_env() -> dict:
    """Environment for child processes: the package lives under src/."""
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{SRC}{os.pathsep}{existing}" if existing else str(SRC)
    return env


# ---------------------------------------------------------------------------
# Email-safe asset restoration
# ---------------------------------------------------------------------------
# Gmail refuses .js attachments even inside a .zip, so the source zip carries
# the browser script as "app.js.txt". Restore it before anything tries to run.
# Harmless and idempotent when the file is already in place.

EMAIL_SAFE_SUFFIX = ".txt"
EMAIL_SAFE_FILES = [SRC / "batchbuilder" / "static" / "app.js"]


def restore_email_safe_assets(quiet: bool = False) -> None:
    for target in EMAIL_SAFE_FILES:
        stashed = target.with_name(target.name + EMAIL_SAFE_SUFFIX)
        if stashed.exists() and not target.exists():
            shutil.copyfile(stashed, target)
            if not quiet:
                say(f"  restored {target.relative_to(ROOT)} "
                    f"(from {stashed.name})")


def missing_assets() -> list:
    return [t for t in EMAIL_SAFE_FILES if not t.exists()]


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def task_doctor(_extra: list) -> int:
    """Report the environment, without changing anything."""
    heading("Environment check")

    say(f"Python running this script : {sys.version.split()[0]}")
    say(f"Project root               : {ROOT}")

    ok = True
    if sys.version_info < MIN_PYTHON:
        say(f"  -> Too old. Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required.")
        ok = False

    say()
    say(f"Virtual environment        : "
        f"{'present' if venv_python().exists() else 'not created yet'}")

    wheel_count = len(list(WHEELS.glob('*.whl'))) if WHEELS.exists() else 0
    say(f"Bundled wheels             : "
        f"{wheel_count if wheel_count else 'none (will use PyPI)'}")

    stashed = [t for t in EMAIL_SAFE_FILES
               if t.with_name(t.name + EMAIL_SAFE_SUFFIX).exists()]
    if stashed:
        say(f"Email-safe assets          : {len(stashed)} to restore on setup")

    missing = missing_assets()
    if missing and not stashed:
        say()
        for m in missing:
            say(f"  MISSING: {m.relative_to(ROOT)}")
        ok = False

    # Can we reach PyPI? Only matters when there are no bundled wheels.
    if not wheel_count:
        say()
        say("No bundled wheels, so setup needs PyPI access. Checking ...")
        try:
            import urllib.request
            urllib.request.urlopen("https://pypi.org/simple/", timeout=6)
            say("  PyPI is reachable.")
        except Exception as exc:
            say(f"  PyPI is NOT reachable ({type(exc).__name__}).")
            say()
            say("  You will need the dependency wheels transferred another way.")
            say("  See BUILD.md, 'If this machine has no PyPI access'.")
            ok = False

    say()
    say("Looks good." if ok else "Some problems found - see above.")
    return 0 if ok else 1


def task_setup(_extra: list) -> int:
    """Create the virtual environment and install dependencies."""
    heading("Setup")

    if sys.version_info < MIN_PYTHON:
        return fail(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer is required; "
            f"this is {sys.version.split()[0]}.",
            "Install a newer Python from https://www.python.org/downloads/\n"
            "and tick 'Add python.exe to PATH' during installation.")

    say("Restoring email-safe assets ...")
    restore_email_safe_assets()
    still_missing = missing_assets()
    if still_missing:
        return fail(
            "Required files are missing from this copy of the project:\n  "
            + "\n  ".join(str(m.relative_to(ROOT)) for m in still_missing),
            "The archive may have extracted incompletely. Re-extract it.")

    # --- virtual environment ------------------------------------------------
    if venv_python().exists():
        say("Virtual environment already exists - reusing it.")
    else:
        say("Creating virtual environment in .venv ...")
        if run([sys.executable, "-m", "venv", str(VENV)]) != 0:
            return fail("Could not create the virtual environment.")

    python = venv_python()

    # --- dependencies -------------------------------------------------------
    # Offline first: install from vendor/wheels when present so a machine with
    # no PyPI access still works. Fall back to PyPI otherwise.
    wheels = sorted(WHEELS.glob("*.whl")) if WHEELS.exists() else []
    say()
    if wheels:
        say(f"Installing from {len(wheels)} bundled wheels (no internet needed) ...")
        code = run([python, "-m", "pip", "install", "--quiet",
                    "--no-index", "--find-links", str(WHEELS),
                    "-r", "requirements-dev.txt"])
    else:
        say("No bundled wheels found; installing from PyPI ...")
        run([python, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
        code = run([python, "-m", "pip", "install", "--quiet",
                    "-r", "requirements-dev.txt"])

    if code != 0:
        return fail(
            "Installing dependencies failed.",
            "If this machine has no PyPI access, the dependency wheels need to\n"
            "reach it another way - they cannot be emailed, because PyInstaller\n"
            "ships .exe bootloader files that mail filters reject.\n"
            "See BUILD.md, 'If this machine has no PyPI access'.")

    say("Dependencies installed.")

    # --- tests --------------------------------------------------------------
    say()
    say("Running the test suite ...")
    if run([python, "-m", "pytest", "-q"], env=child_env()) != 0:
        return fail(
            "Tests failed.",
            "Setup itself completed, but do not build until this is understood:\n"
            "the suite includes a byte-for-byte check that the Tox4 files Ascent\n"
            "already reads have not changed.")

    heading("Setup complete")
    say()
    say("Next:")
    say("  python make.py run     start the application")
    say("  python make.py build   produce the .exe")
    say()
    return 0


def task_test(extra: list) -> int:
    """Run the test suite."""
    heading("Tests")
    restore_email_safe_assets(quiet=True)
    return run([require_venv(), "-m", "pytest", "-q", *extra], env=child_env())


def task_run(extra: list) -> int:
    """Start the application from source."""
    heading("Starting Batch Builder")
    restore_email_safe_assets(quiet=True)

    # `--demo` with no fixture given: fill in the one shipped with the tests.
    arguments = list(extra)
    if "--demo" in arguments:
        index = arguments.index("--demo")
        following = arguments[index + 1] if index + 1 < len(arguments) else None
        if following is None or following.startswith("-"):
            fixture = ROOT / "tests" / "fixtures" / "apollo_fixture.json"
            arguments.insert(index + 1, str(fixture))
            say(f"Demo mode: using {fixture.name}")

    say("The address it listens on is printed below.")
    say("Press Ctrl+C, or close this window, to stop.")
    say()
    return run([require_venv(), "-m", "batchbuilder", *arguments],
               env=child_env())


def task_build(_extra: list) -> int:
    """Run the tests, package the application, and smoke-test the result."""
    heading("Build")
    restore_email_safe_assets(quiet=True)
    python = require_venv()
    env = child_env()

    say("Running tests before packaging ...")
    if run([python, "-m", "pytest", "-q"], env=env) != 0:
        return fail(
            "Tests failed. Not packaging.",
            "Do not ship a build with a failing suite - the golden tests are\n"
            "what guarantee the Tox4 files Ascent reads have not changed.")

    say()
    say("Packaging (this takes a minute or two the first time) ...")
    code = run([python, "-m", "PyInstaller", "--noconfirm", "--clean",
                "--distpath", "build/dist", "--workpath", "build/work",
                "build/batchbuilder.spec"], env=env)
    if code != 0:
        return fail(
            "PyInstaller failed.",
            "If antivirus interfered, ask for the build folder to be\n"
            "allow-listed. PyInstaller output is a common false positive.")

    dist = ROOT / "build" / "dist" / "BatchBuilder"
    exe = dist / ("BatchBuilder.exe" if os.name == "nt" else "BatchBuilder")

    # PyInstaller runs its entry script with no package context, so a build can
    # fail on import alone while every test passes. "It compiled" is not the
    # same as "it starts".
    say()
    say("Smoke-testing the executable ...")
    try:
        reported = subprocess.check_output([str(exe), "--version"],
                                           stderr=subprocess.STDOUT, timeout=120)
        say(f"  {reported.decode(errors='replace').strip()}")
    except Exception as exc:
        return fail(f"The built executable does not start: {exc}")

    # Ship the example config and README beside the executable, and create the
    # folders the application expects to find next to itself.
    for name in ("batchbuilder.example.json", "README.md"):
        source = ROOT / name
        if source.exists():
            shutil.copyfile(source, dist / name)
    for folder in ("hamilton files", "ins_files"):
        (dist / folder).mkdir(exist_ok=True)

    total = sum(f.stat().st_size for f in dist.rglob("*") if f.is_file())

    heading("Build complete")
    say()
    say(f"  Folder : {dist}")
    say(f"  Size   : {total / 1024 / 1024:.0f} MB")
    say()
    say("Copy that ENTIRE folder to wherever analysts will run it from.")
    say("The .exe alone will not work - it needs _internal beside it.")
    say()
    return 0


def task_clean(_extra: list) -> int:
    """Remove the virtual environment, build output and caches."""
    heading("Clean")
    targets = [VENV, ROOT / "build" / "dist", ROOT / "build" / "work",
               ROOT / ".pytest_cache"]
    targets += list(ROOT.rglob("__pycache__"))
    removed = 0
    for target in targets:
        if target.exists():
            shutil.rmtree(target, ignore_errors=True)
            say(f"  removed {target.relative_to(ROOT)}")
            removed += 1
    say(f"\n{removed} item(s) removed." if removed else "\nNothing to remove.")
    return 0


TASKS = {
    "setup": task_setup,
    "test": task_test,
    "run": task_run,
    "build": task_build,
    "clean": task_clean,
    "doctor": task_doctor,
}


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="make.py",
        description="Batch Builder project tasks.",
        epilog="Anything after the task name is passed through, e.g. "
               "`python make.py run --demo --port 8765`.")
    parser.add_argument("task", nargs="?", choices=sorted(TASKS),
                        help="what to do")
    known, extra = parser.parse_known_args(argv)

    if not known.task:
        parser.print_help()
        say()
        say("Start with:  python make.py setup")
        return 0

    return TASKS[known.task](extra)


if __name__ == "__main__":
    sys.exit(main())
