# Batch Builder

Turns a plate workbook into Ascent batch files (the instrument sequence),
cross-checked against Apollo.

Supports two assays side by side:

| | Input | Fill order | Output |
| --- | --- | --- | --- |
| **Tox4** | Hamilton run report, `Report` sheet | across rows (1, 2, 3 …) | 1 file per MBN plus a combined file |
| **Tox6** | Destination plate mapping, `ReportMapping` sheet | down columns (1, 13, 25 …) | 1 file per plate |

The format is detected from the workbook, not chosen by the analyst. Each run
lands in its own timestamped folder together with a human-readable run report.

This replaces the original single-file Tkinter script (kept for reference at
`reference/bb_v1.py`).

---

## Running it

### As a packaged application

Copy the whole `BatchBuilder` folder to the share and run `BatchBuilder.exe`.
It starts a small web server on `127.0.0.1` and opens your browser at it. The
console window that appears shows the local address; closing it stops the
application.

**It is completely self-contained.** Nothing needs installing on the
workstation: no Python, no packages, no ODBC configuration beyond a SQL Server
driver being present. Nothing is exposed on the network — each analyst runs
their own copy on their own machine, on their own port. The only thing it
reaches out to is Apollo, and it starts and runs without that too.

Copy the **entire folder**, not just the .exe — the `_internal` folder beside it
holds the interpreter, the templates and the stylesheet.

What ends up in the folder:

```
BatchBuilder  BatchBuilder.exe            the application
  _internal\                  runtime, templates, static assets
  batchbuilder.example.json   copy to batchbuilder.json to override defaults
  README.md                   this file
  hamilton files\             suggested place to drop plate workbooks
  ins_files\                  output lands here (falls back to your profile
                              if the share is read-only)
```

### From source

```bash
pip install -r requirements-dev.txt
PYTHONPATH=src python -m batchbuilder
```

Useful flags:

| Flag | Effect |
| --- | --- |
| `--port 8765` | Listen on a fixed port instead of a free one |
| `--no-browser` | Do not open a browser window |
| `--config PATH` | Use a specific `batchbuilder.json` |
| `--demo FIXTURE.json` | Replay recorded Apollo results instead of the live database |

`--demo` is how you exercise the whole application away from the lab network:

```bash
PYTHONPATH=src python -m batchbuilder --demo tests/fixtures/apollo_fixture.json
```

---

## Using it

1. Fill in instrument, method, rack/plate position, stream, plate code and MBNs.
   Leave **MBN 2** blank (or enter `X`) for a single-MBN run.
2. Drop the plate workbook on the drop zone. The plate map draws immediately,
   before Apollo is contacted, and the app reports what it found:
   which format, which fill order, and (for Tox6) which condition.
3. **Check batch** validates everything and writes nothing.
4. **Generate files** writes the batch folder and offers the files for download.

The plate map colours every well by what it holds — calibrator, control,
cutoff calibrator, qualitative QC, negative, MBN 1, MBN 2, repeat, or removed —
so a mis-loaded plate is visible before anything is generated.

### Where output goes

`ins_files\` beside the executable. If that folder is not writable (a read-only
share), output falls back to `%LOCALAPPDATA%\BatchBuilder\ins_files` and the
application says so at the top of the page.

---

## Tox6

### Fill order

Tox6 plates are filled **down columns** (A1, B1, C1 …) rather than across rows,
so consecutive injections are twelve vial positions apart: 1, 13, 25, 37 …

This needed **no change to the position formula**. `row_major_12` turns a
down-column fill order into the 1/13/25 sequence by itself; only the order rows
arrive in is different. The application detects the fill order from the workbook
and displays it, so an analyst can see at a glance which scheme a plate is on.

### Conditions

A Tox6 plate runs one of three conditions, detected automatically from which
control wells are present and overridable from the form:

| Condition | Controls | Samples |
| --- | --- | --- |
| **Quant** | Cal 1–6, QC L1–L4, Neg QC, Hydro QC | 84 |
| **Qual** | Cutoff Cal, Low QC, High QC, Neg QC, Hydro QC | 90 |
| **Combo** | both sets | 80 |

*Qual* here means **qualitative analytes**, not a qualification run. The
qualitative controls exist because the quantitative QCs do not contain those
analytes; they bracket the samples so the qualitative analysis is covered at
both ends of the run.

### Control matching

Tox6 controls are matched to Apollo by **exact name**. The Tox4 rule — test
whether the first two characters of the `qcid` appear in the well name — cannot
work here: `QC` appears in `Neg QC`, `QC L1`, `Hydro QC`, `Low QC` and
`High QC`, and `Ca` appears in both `Cal 1` and `Cutoff Cal`.

### Plate-only mockup mode

A Tox6 plate can be built with no Apollo lookup and no MBN, for sponsor testing
against mock plates whose specimens are not real. Every such run is stamped
"Not for production use" in the UI and in the run report.

### Still provisional

No Tox6 reference output exists yet, so these are **proposals** pending review:

- the block order (see `BlockLayout` in `generator_tox6.py`)
- the `_Lot` / `_Level` labels (see `TOX6_CONTROLS` in `controls.py`)
- the `.dam` names — `TO6_Str1` / `TO6_Str2` are placeholders, selectable from a
  configurable dropdown
- what the Tox6 controls will be called in Apollo

All of it is data in two tables, so correcting it after review is an edit, not a
rewrite. `mockups/tox6/` holds generated examples of all three conditions with a
covering note for the sponsor.

---

## Configuration

Everything runs on built-in defaults with no config file present. To change
something, copy `batchbuilder.example.json` to `batchbuilder.json` beside the
executable and keep only the keys you want to override.

Common changes:

- **Add an instrument or a method** — `form.instruments`, `form.methods`.
  `TO3`, `TO3b` and `PSY` were commented out of the original and remain
  disabled.
- **Add an acquisition method** — `form.acq_methods`, the `.dam` names offered
  in the form.
- **Point at a different Apollo server** — `apollo.server`, `apollo.database`.
  Credentials are compiled in and only need to appear here if they change.
- **Pin an ODBC driver** — `apollo.driver`. Left `null`, the newest installed
  SQL Server driver is used.
- **Accept a Hamilton status that currently fails** — `extra_ok_statuses`. This
  *adds* to each format's own vocabulary (`No Error` for Tox4, `Correct
  pipetting` for Tox6) rather than replacing it, so widening one cannot
  accidentally break the other.
- **Change what a complete Tox4 plate looks like** — `expectations`. Tox6 uses
  its per-condition requirements instead.

A malformed config file is reported in the page banner and ignored; the
application still starts on defaults.

---

## Tox4 output is a contract

Ascent already consumes these files. `tests/test_golden.py` regenerates all
three shipped sample files and compares them **byte for byte**, CRLF endings
included. Any change that alters a single byte fails the suite — including any
of the Tox6 work.

That is deliberate. Several things in the Tox4 output look wrong and are
reproduced anyway, because changing them changes a live interface:

- **The first QC block is numbered `QC2`–`QC5`; later blocks are `QC1`–`QC4`.**
  `QC_HYD` contains the substring `QC`, so it advances the level counter even
  though it is labelled `HYD`. Later blocks exclude HYD and so start at 1.
- **The per-MBN files carry the combined file's stem in their `OutputFile`
  column**, not their own.
- **The MBN 2 file restarts its injection counter at 1 for the opening block,
  then jumps to where the combined file left off** for its samples.
- **`2x DW96` is only ever selected by instrument `LC_7`.** The original also
  tested `"TOX3" in method`, a string none of its method options could contain,
  so that branch has never fired. Preserved as `settings.alt_methods: []`.

Do not update the expected files to make a test pass. If the lab decides one of
these should change, regenerate the golden files as a separate, reviewed change.

---

## Fixed since the original

- **Aspiration errors removed the wrong samples.** Errored rows were collected by
  index and then deleted one at a time, so every deletion after the first shifted
  the remaining indices. With two or more errors on a plate, good samples were
  silently dropped.
- **A plate with no NEG well crashed** with an unexplained `IndexError`.
- **Regenerating a batch twice in the same second crashed** on `os.mkdir`.
- **The date stamp was computed once at import**, so an application left open
  overnight stamped the previous day.
- **The database connection opened at import**, so an unreachable Apollo meant
  the application would not start at all and the analyst saw nothing.
- **Queries interpolated the MBN into SQL** as a string. All queries are now
  parameterised.
- **Any unexpected status was treated as success.** The two known failure strings
  were hardcoded; the check is now an allow-list, so an unfamiliar status fails
  safe and is named in the report.
- Duplicate barcodes, short calibrator sets, missing controls, specimens in an
  MBN but not on the plate, and unreadable workbooks are now reported clearly
  instead of crashing or passing silently.

---

## Troubleshooting

### The page just spins

The application prints the address it is listening on to its console window.
If the browser never loads that address:

1. **Read the console window.** Startup failures are printed there and the
   window is held open. If it closed instantly, the build predates v2.1.1.
2. **Check what is listening.**
   ```bash
   netstat -ano | findstr LISTENING | findstr 127.0.0.1
   ```
3. **Port conflicts.** On a machine running Docker or WSL2, Hyper-V reserves
   blocks of TCP ports. The application picks a free port automatically and
   announces it if a requested one is taken. To see the reserved ranges:
   ```bash
   netsh interface ipv4 show excludedportrange protocol=tcp
   ```
   Then pick something outside them with `--port`.

Apollo being unreachable does **not** cause this, by design. The server starts
without it, the page loads, and the connection state is shown in the top right.

### Apollo shows as unavailable

The page still works: plate files can be loaded, the plate map drawn, and layout
problems found. Only steps that need a batch number are blocked, and Tox6
mockup mode is unaffected.

Use **Re-check connection** in the banner after fixing the network rather than
restarting the application.

Common causes:

- **Not on the lab network.** `YOUR_SQL_SERVER` is an internal name; it will not
  resolve from home or over most VPN splits. Check with `nslookup YOUR_SQL_SERVER`.
- **No suitable ODBC driver.** Check what is installed:
  ```bash
  python -c "import pyodbc; print(pyodbc.drivers())"
  ```
  The application prefers the newest *ODBC Driver NN for SQL Server* and falls
  back through older ones to the legacy *SQL Server* driver. That legacy driver
  works but is very old; installing *ODBC Driver 17* or *18* is worth doing on
  any machine that only has it.
- **pyodbc missing from the build.** `pip install -r requirements.txt`. The
  application will start without it and say so, rather than failing to launch.

### Nothing is written

Output goes to `ins_files\` beside the executable, falling back to
`%LOCALAPPDATA%\BatchBuilder\ins_files` when that is read-only. Whichever is in
use is shown under the Generate button and in the run report.

---

## Layout

```
src/batchbuilder/
  models.py            data types shared by every layer
  controls.py          Tox6 control vocabulary, roles, condition detection
  positions.py         well ID -> vial position, as swappable named strategies
  readers.py           input format specs, format and fill-order detection
  hamilton.py          workbook parsing, driven by a reader spec
  apollo.py            read-only SQL Server access (+ a recorded stand-in)
  validation.py        pre-flight checks, dispatched per assay
  generator.py         Tox4 batch construction  <- byte-for-byte contract
  generator_tox6.py    Tox6 batch construction  <- proposed layout, in tables
  report.py            the run report
  service.py           orchestration; the only thing the web layer calls
  webapp.py            routes
  __main__.py          launcher
tests/                 196 tests, including the golden regression suite
build/                 PyInstaller spec and build script
mockups/tox6/          generated sponsor examples + covering note
reference/             the original bb_v1.py, for comparison
```

`positions.py` and `controls.py` are isolated on purpose: how a plate location
becomes a vial position, and what a control is called, are the two things most
likely to change again.

---

## Building

```powershell
powershell -ExecutionPolicy Bypass -File build\build.ps1
```

Runs the tests first and refuses to package if they fail. Output is
`build\dist\BatchBuilder\`; copy that whole folder to the share.

It is a one-folder build, not one-file: a one-file executable re-extracts itself
to a temp directory on every launch, which is slow from a share and more likely
to upset AV.

---

## Tests

```bash
python -m pytest
```

| File | Covers |
| --- | --- |
| `test_golden.py` | Byte-for-byte reproduction of the three shipped Tox4 files |
| `test_hamilton.py` | Parsing, well mapping, error rows, malformed workbooks |
| `test_tox6.py` | Format/orientation/condition detection, Tox6 layout, Tox4 untouched |
| `test_validation.py` | Form, control completeness, plate/Apollo reconciliation |
| `test_service.py` | End-to-end run, output folders, run report |
| `test_webapp.py` | Routes, uploads, downloads, path traversal guards |
| `test_config.py` | Defaults, overrides, and that the shipped example file loads |

### About the Apollo fixture

`tests/fixtures/apollo_fixture.json` is **inferred**, not captured: the database
is unreachable from a development machine, so the query results were
reverse-engineered from the three known-good output files. `build/reference_impl.py`
is a verbatim port of the original generation logic; running
`python build/validate_fixture.py` feeds the fixture through it and confirms it
reproduces the shipped files exactly. That is what makes the fixture trustworthy
as a stand-in — it is proven behaviourally equivalent for this batch, even though
the literal `qcid` values are a reconstruction.
