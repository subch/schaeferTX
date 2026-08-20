# Building Batch Builder on your work machine

This is the source for Batch Builder. You build the `.exe` here rather than
receiving one, which avoids the mail and antivirus problems that come with
emailing executables.

**Time needed:** about ten minutes, most of it waiting.

---

## Before you start

**Python 3.10 or newer** must be installed. Get it from
[python.org/downloads](https://www.python.org/downloads/) and tick
**"Add python.exe to PATH"** during installation, or use whatever your
organisation ships through the Software Center.

Check it:

```bash
py --version
```

VS Code is optional — everything works from a terminal — but the project ships
tasks and debug configurations for it.

---

## The short version

```bash
python make.py setup     first-time setup: environment, dependencies, tests
python make.py run       start the app and check it against real Apollo
python make.py build     produce build/dist/BatchBuilder/
```

Then copy the whole `build/dist/BatchBuilder` folder to wherever analysts run
it from.

`python make.py` on its own lists every task. `python make.py doctor` reports
what is installed and what is missing without changing anything — run that first
if something looks wrong.

---

## Step 1 — Unzip

Extract to a normal local folder such as `C:\dev\batch-builder`.

Avoid OneDrive, network shares, and paths with unusual characters — Python
virtual environments and file-syncing interact badly.

> Extract it properly. Running from inside the .zip preview window will not work.

---

## Step 2 — Setup

```bash
cd C:\dev\batch-builder
python make.py setup
```

This will:

1. Check your Python version.
2. Restore `app.js` from `app.js.txt` (see *Why some files are renamed* below).
3. Create a `.venv` folder — a private environment for this project only.
   Nothing is installed machine-wide; deleting `.venv` undoes it entirely.
4. Install the dependencies.
5. Run the test suite.

You should finish with `233 passed`.

> **If the tests fail, stop and find out why before building.** The suite
> includes a byte-for-byte comparison against the Tox4 files Ascent already
> consumes. A failure there means the output format changed.

### If this machine has no PyPI access

Setup will fail at the install step. The dependencies cannot be emailed —
PyInstaller ships `.exe` bootloader files inside its wheel, and mail filters
reject those even inside a `.zip`. Nothing can be done about that from this end.

Options, best first:

1. **Google Drive.** Upload `vendor/wheels` (or the full source zip, which
   includes it) to Drive and share it with yourself. This is Google's own
   documented answer for blocked attachments and needs no workarounds.
2. **A USB stick or your organisation's file transfer tool.**
3. **An internal package mirror**, if your organisation runs one — point pip at
   it with `--index-url`.

However the folder arrives, put it at `vendor/wheels` inside the project and
re-run `python make.py setup`. It installs from there with no internet:

```
vendor/wheels/*.whl        35 files, about 6 MB
```

---

## Step 3 — Test it before you package it

Do this while on the lab network, **before** building. Running from source and
running the built `.exe` execute identical code, so if it works here it will
work packaged — and problems are far easier to diagnose at this stage.

```bash
python make.py run
```

Your browser opens automatically. The console shows the address it is listening
on; press `Ctrl+C` to stop.

Check that:

- the page loads
- the top right says **Apollo connected**
- dropping a plate workbook draws the plate map
- **Check batch** validates against a real MBN

To try the interface with no database at all:

```bash
python make.py run --demo
```

---

## Step 4 — Build

```bash
python make.py build
```

Runs the tests, then PyInstaller, then starts the executable it just built to
confirm it actually launches. Expect a couple of minutes the first time.

Output lands in `build/dist/BatchBuilder/`.

---

## Step 5 — Deploy

Copy the **entire `BatchBuilder` folder**, roughly 17 MB:

```
BatchBuilder\
  BatchBuilder.exe            the application
  _internal\                  Python runtime, page templates, stylesheet
  batchbuilder.example.json   copy to batchbuilder.json to change settings
  README.md
  hamilton files\             suggested drop point for plate workbooks
  ins_files\                  output lands here
```

> **The `.exe` alone will not work.** It needs `_internal` beside it.

Analysts double-click `BatchBuilder.exe`. It starts a small web server on
`127.0.0.1` and opens their browser. Nothing is exposed on the network, no ports
are opened, and no hosting is involved — each person runs their own copy on
their own machine.

---

## Using VS Code

`File > Open Folder...` and pick the extracted folder. Accept the prompt to
install the **Python** extension.

`Terminal > Run Task...` gives you the same tasks as `make.py`, and
`Ctrl+Shift+B` builds. There are debug configurations with working breakpoints
for both the application and the tests, and Test Explorer is wired up. All of it
is workspace-scoped — nothing touches your global VS Code settings.

---

## Why some files are renamed

Gmail refuses a fixed list of file extensions and inspects inside `.zip`
archives to enforce it. Two of this project's own files are on that list:

| File | Why | How it is handled |
| --- | --- | --- |
| `app.js` | `.js` is blocked | Shipped as `app.js.txt`; `make.py setup` restores it |
| `setup.bat`, `run.bat`, `build.bat`, `*.ps1` | `.bat` and `.ps1` are blocked | Left out entirely — `make.py` replaces them |

`make.py` exists precisely so the project does not depend on file types that
cannot be transferred. It is also better than the scripts it replaced: no
PowerShell execution-policy problems, and one entry point instead of six.

If you obtain the project some other way (Drive, a USB stick, version control),
`app.js` will already be in place and `make.py setup` will simply skip that step.

---

## Troubleshooting

### "No Python found" / `python` is not recognised

Either Python is not installed, or "Add to PATH" was not ticked during install.
Reinstall with that box ticked, or call it by full path. Restart your terminal
and VS Code afterwards so they pick up the changed PATH.

Try `py` instead of `python` — the Windows launcher is often present when
`python` is not.

### Installing dependencies fails

See *If this machine has no PyPI access* above. Run `python make.py doctor` — it
will tell you explicitly whether PyPI is reachable.

### PyInstaller is blocked or quarantined by antivirus

PyInstaller output is frequently flagged. Ask IT to allow-list the build folder
or the resulting `BatchBuilder.exe`. It is a false positive and a well-known
one — the packing technique resembles things that are genuinely malicious, which
is the whole reason you are building on the machine rather than emailing a
finished `.exe`.

### Apollo will not connect

The application starts and runs regardless; only steps needing an MBN are
blocked. The page shows the reason and offers **Re-check connection**.

- **Not on the lab network.** `YOUR_SQL_SERVER` is an internal name. Test with
  `nslookup YOUR_SQL_SERVER`.
- **No suitable ODBC driver.** Check with:
  ```bash
  .venv\Scripts\python.exe -c "import pyodbc; print(pyodbc.drivers())"
  ```
  The app prefers *ODBC Driver 18/17 for SQL Server* and falls back through
  older ones to the legacy *SQL Server* driver. That legacy driver works but is
  very old — installing ODBC Driver 17 or 18 is worth doing.

### The page opens but nothing appears

Force-refresh with `Ctrl+F5`. If it persists, read the console window the
application opened — startup problems are printed there and it is held open
deliberately.

### A port is already in use

The app picks a free port automatically and says so when a requested one is
taken. On a machine running Docker or WSL2, Hyper-V reserves blocks of ports:

```bash
netsh interface ipv4 show excludedportrange protocol=tcp
```

Then pick something outside those ranges: `python make.py run --port 8765`.

### Starting over

```bash
python make.py clean
```

Removes the virtual environment, build output and caches. Nothing else is
touched.

---

## What is in this archive

```
make.py                the only entry point you need
src\batchbuilder\      the application
tests\                 233 tests, including the Tox4 golden files
build\                 PyInstaller spec, entry point, packaging helpers
mockups\tox6\          generated Tox6 examples for the sponsor
reference\bb_v1.py     the original script, for comparison
.vscode\               tasks, debug configs, workspace settings
README.md              what the application does and how it works
CHANGELOG.md           what changed and why
BUILD.md               this file
```

Start with `README.md` for how the application itself works — the Tox4 output
contract, the Tox6 layout still awaiting sign-off, and the configuration file.

---

## One thing worth knowing

`src\batchbuilder\config.py` contains the read-only Apollo credentials, as the
original script did. That is deliberate so the tool works with no configuration,
and you have confirmed those credentials are fine to use on the lab network.

Be aware they travel inside this archive. If your mail or DLP policy would
object to credentials moving through email, move them into a
`batchbuilder.json` beside the executable instead — `config.py` already reads
`apollo.uid` and `apollo.pwd` from there, and anything set in that file
overrides the compiled-in values.
