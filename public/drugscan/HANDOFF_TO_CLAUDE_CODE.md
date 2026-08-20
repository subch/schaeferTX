# Batch Builder — handoff to Claude Code

**You are Claude Code running on Travis's work machine at a clinical toxicology
laboratory.** This document is the complete brief for getting the Batch Builder
application built, verified and deployed there. Read all of it before acting.

Travis wrote this tool. It converts a Hamilton liquid-handler plate workbook
into Ascent batch files — the sequence file the LC-MS/MS instrument loads to
know what to inject and in what order. It replaces an older single-file Tkinter
script (`reference/bb_v1.py`, kept for comparison).

---

## Ground rules

**1. Tox4 output is a live contract. Do not change it.**

Ascent already consumes these files in production. `tests/test_golden.py`
regenerates three real batch files and compares them **byte for byte**, CRLF
line endings included. If that test fails, something is genuinely broken.

> **Never** update the files in `tests/fixtures/expected/` to make a test pass.
> If the laboratory decides the format should change, that is a separate,
> deliberately reviewed change with regenerated golden files.

**2. Several things in the output look like bugs and are reproduced on purpose.**

Do not "fix" any of these:

- The first QC block is numbered `QC2`–`QC5` while later blocks are `QC1`–`QC4`.
  `QC_HYD` contains the substring `QC`, so it advances the level counter even
  though it is labelled `HYD`.
- The per-MBN files carry the *combined* file's stem in their `OutputFile`
  column, not their own.
- The MBN 2 file restarts its injection counter at 1 for the opening block, then
  jumps to where the combined file left off for its samples.
- `2x DW96` is only ever selected by instrument `LC_7`. The original also tested
  `"TOX3" in method`, a string none of its method options could contain, so that
  branch has never fired. Preserved as `settings.alt_methods: []`.

**3. The application must start and run without the database.**

Apollo lives on the lab network. The app is required to come up on a machine
that cannot reach it, so a plate file can still be loaded, inspected and checked.
Never make startup wait on, or fail because of, a database connection.

**4. Ask Travis before changing generator logic.** Almost everything else —
UI, packaging, docs, tests — is fair game.

---

## Step 0 — Check the environment

```bash
python make.py doctor
```

Reports Python version, virtual environment, bundled wheels and whether PyPI is
reachable. Changes nothing. If `python` is not found, try `py`; Python **3.10 or
newer** is required.

---

## Step 1 — Get the source

Ask Travis which applies:

- **He has attached the files or a zip to this conversation** — write them to a
  working folder, e.g. `C:\dev\batch-builder`, preserving the directory layout
  exactly. The tests and the build both depend on it.
- **The machine can reach `https://schaefertx.com/APOLLO_PASSWORD/`** — the full source
  is published there as individual files and as
  `batch-builder-source.zip`. That copy is *sanitised*: credentials, server
  names, batch numbers and specimen identifiers are synthetic placeholders. It
  runs and all tests pass; see Step 3 for supplying the real values.

Either way you should end up with roughly this:

```
make.py                one entry point for every task
src/batchbuilder/      the application
tests/                 236 tests, including the golden files
build/                 PyInstaller spec, entry point, packaging
vendor/wheels/         dependencies for offline install (may be absent)
BUILD.md               human-facing build guide
README.md              how the application works
```

---

## Step 2 — Set up

```bash
python make.py setup
```

Creates `.venv` (nothing is installed machine-wide), installs dependencies, then
runs the test suite.

**Expected: `236 passed, 3 skipped`.** If tests fail, stop and diagnose — do not
proceed to a build.

If dependency installation fails, the machine has no PyPI access and
`vendor/wheels/` is missing. That folder cannot be emailed, because PyInstaller
ships `.exe` bootloader files inside its own wheel. Tell Travis; he needs to move
it across by another route (Drive, USB, internal mirror). Once it is in place at
`vendor/wheels/`, re-run setup — it installs offline automatically.

---

## Step 3 — Supply the real connection details

The published source carries placeholders, not credentials. **Ask Travis for the
Apollo server, instance, database, username and password.** Do not guess them,
and do not commit them anywhere.

Create `batchbuilder.json` beside `make.py`:

```json
{
  "apollo": {
    "server": "<server>\\<instance>",
    "database": "<database>",
    "uid": "<username>",
    "pwd": "<password>"
  }
}
```

Anything set here overrides the built-in values. The file is git-ignored.

---

## Step 4 — Verify against the live database

Do this **before** building. Running from source and running the packaged `.exe`
execute identical code, so problems are far easier to diagnose here.

```bash
python make.py run
```

A browser opens on `127.0.0.1`. Confirm with Travis that:

- the page loads and the top right reads **Apollo connected**
- dropping a Hamilton plate workbook draws the 96-well plate map
- **Check batch** validates against a real MBN and reports sensible counts

`python make.py run --demo` exercises the whole interface with recorded data and
no database, which is useful if Apollo is unreachable.

---

## Step 5 — Build

```bash
python make.py build
```

Runs the tests, packages with PyInstaller, then starts the executable it just
produced to confirm it actually launches. Output: `build/dist/BatchBuilder/`,
about 17 MB.

---

## Step 6 — Deploy

Copy the **entire `BatchBuilder` folder** to wherever analysts run it from.

> The `.exe` alone will not work. It needs the `_internal` folder beside it,
> which holds the Python runtime, the page templates and the stylesheet.

Analysts double-click `BatchBuilder.exe`. It starts a local web server on
`127.0.0.1` and opens their browser. Nothing is exposed on the network, no ports
are opened, and no hosting is involved — each person runs their own copy.

---

## Traps that have already bitten this project

Every one of these was a real failure, found and fixed. If you touch the
relevant area, do not reintroduce them.

**PyInstaller entry point.** It runs its entry script as a top-level module with
no package context. Pointing it at `src/batchbuilder/__main__.py` fails on that
file's relative imports, *before* any error handling exists — the process dies
and the user gets a browser tab spinning at nothing. The spec must point at
`build/entry.py`. `make.py build` smoke-tests the binary with `--version`
afterwards, so a build that compiles but cannot start is a build failure.

**CRLF line endings.** The Ascent batch files are CRLF and the golden tests
compare bytes. Reading a golden file with `read_text()` applies universal-newline
translation and silently converts it to LF. Read bytes and decode. Git will do
the same thing via autocrlf unless a `.gitattributes` marks the tree `-text`.

**The `hidden` attribute versus CSS.** `[hidden]` gets `display: none` from the
user-agent stylesheet, so any author rule with `display: flex` beats it. Several
elements in the page are toggled with `hidden` *and* styled `display: flex`,
which made the busy spinner permanently visible. `app.css` carries a
`[hidden] { display: none !important; }` reset — leave it there. Note that
`element.hidden` reads `true` even while CSS forces the element on screen, so
verify with `getComputedStyle`, not DOM state.

**Blocking on Apollo.** Connecting to an unreachable SQL Server can take minutes,
far longer than any login timeout, because name resolution happens first. The
health check runs on a background thread and the request path fails fast when the
probe already knows the server is down. Do not make any user-facing path wait on
a connection.

**ODBC drivers.** The app prefers *ODBC Driver 18/17 for SQL Server* and falls
back through older ones to the legacy *SQL Server* driver. That legacy driver
rejects `TrustServerCertificate` outright rather than ignoring it, so the
attribute is only sent to drivers that understand it. If only the legacy driver
is present, suggest installing ODBC Driver 17 or 18.

**Antivirus.** PyInstaller output is frequently quarantined. This is a
well-known false positive. Ask for the build folder or the resulting
`BatchBuilder.exe` to be allow-listed — building on the machine rather than
emailing an `.exe` already avoids the worst of it.

---

## Two assays, and what is still provisional

| | Input sheet | Fill order | Output |
| --- | --- | --- | --- |
| **Tox4** | `Report` | across rows (1, 2, 3 …) | one file per MBN plus a combined file |
| **Tox6** | `ReportMapping` | down columns (1, 13, 25 …) | one file per plate |

The format is detected from the workbook, never chosen by the analyst.

Tox6 plates are filled down columns, so consecutive injections are twelve vial
positions apart. This needed **no change to the position formula** —
`row_major_12` turns a down-column fill into that sequence on its own. Only the
row order differs.

A Tox6 plate runs one of three conditions, detected from which controls are
present and overridable in the form:

| Condition | Controls | Samples |
| --- | --- | --- |
| **Quant** | Cal 1–6, QC L1–L4, Neg QC, Hydro QC | 84 |
| **Qual** | Cutoff Cal, Low QC, High QC, Neg QC, Hydro QC | 90 |
| **Combo** | both sets | 80 |

*Qual* means **qualitative analytes**, not a qualification run. Those controls
exist because the quantitative QCs do not contain those analytes; they bracket
the samples so the qualitative analysis is covered at both ends.

**Tox6 has no reference output yet.** These are proposals awaiting the sponsor's
sign-off, and all of them are data in two tables rather than logic:

1. Block order — `BlockLayout` in `src/batchbuilder/generator_tox6.py`
2. `_Lot` / `_Level` labels — `TOX6_CONTROLS` in `src/batchbuilder/controls.py`
3. The `.dam` names — `TO6_Str1` / `TO6_Str2` are placeholders, selectable from
   a configurable dropdown
4. What the Tox6 controls will be called in Apollo. Until that is known, controls
   in a plate-only mockup name themselves.

`mockups/tox6/` holds generated examples of all three conditions with a covering
note listing exactly what needs confirming. Travis can send those to the sponsor.

Tox6 controls are matched to Apollo by **exact name**, not by substring. The
Tox4 rule — test whether the first two characters of the `qcid` appear in the
well name — cannot work for Tox6: `QC` appears in `Neg QC`, `QC L1`, `Hydro QC`,
`Low QC` and `High QC`, and `Ca` appears in both `Cal 1` and `Cutoff Cal`.

---

## Where things live

```
src/batchbuilder/
  models.py            shared data types
  controls.py          Tox6 control vocabulary, roles, condition detection
  positions.py         well ID -> vial position, as swappable named strategies
  readers.py           input format specs, format and fill-order detection
  hamilton.py          workbook parsing, driven by a reader spec
  apollo.py            read-only SQL Server access, background health probe
  validation.py        pre-flight checks, dispatched per assay
  generator.py         Tox4 construction   <- byte-for-byte contract
  generator_tox6.py    Tox6 construction   <- proposed layout, held in tables
  report.py            the run report written beside each batch
  service.py           orchestration; the only thing the web layer calls
  webapp.py            routes
  __main__.py          launcher
```

`positions.py` and `controls.py` are isolated deliberately: how a plate location
becomes a vial position, and what a control is called, are the two things most
likely to change again.

### Tests

| File | Covers |
| --- | --- |
| `test_golden.py` | Byte-for-byte reproduction of three real Tox4 files |
| `test_hamilton.py` | Parsing, well mapping, error rows, malformed workbooks |
| `test_tox6.py` | Format/orientation/condition detection, Tox6 layout |
| `test_validation.py` | Form, control completeness, plate/Apollo reconciliation |
| `test_service.py` | End-to-end run, output folders, run report |
| `test_webapp.py` | Routes, uploads, downloads, path traversal guards |
| `test_launcher.py` | Startup, ports, health probe never blocking |
| `test_config.py` | Defaults, overrides, the shipped example file |
| `test_frontend.py` | Static front-end checks DOM assertions cannot see |

### About the Apollo test fixture

`tests/fixtures/apollo_fixture.json` is **inferred, not captured** — the database
is unreachable from a development machine, so the query results were
reverse-engineered from three known-good output files.
`build/reference_impl.py` is a verbatim port of the original script's logic;
running `python build/validate_fixture.py` feeds the fixture through it and
confirms it reproduces the shipped files exactly. That is what makes it
trustworthy as a stand-in, even though the literal `qcid` values are a
reconstruction.

If you obtain real Apollo query output, replacing the fixture with captured data
would strengthen this. Keep the golden comparison intact either way.

---

## If Travis asks you to change the output format

Take it slowly and confirm the intent. The safe sequence is:

1. Make the change behind a config value where possible, so it can be reverted
   without a code change.
2. Run the suite. The golden test **will** fail — that is the point of it.
3. Show Travis the exact diff of what changed in the generated files, line by
   line, and get explicit confirmation.
4. Only then regenerate the expected files, in a commit that does nothing else,
   with a message explaining what changed and who approved it.

Never combine a golden-file regeneration with any other change.
