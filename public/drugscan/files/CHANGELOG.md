# Changelog

## 2.1.3-dev - unreleased

Makes the project transferable. Gmail rejects a fixed list of file extensions
and inspects inside archives to enforce it, which the previous source zip fell
foul of.

### Added

- **`make.py`** - one entry point for setup, test, run, build, clean and
  doctor. Replaces six .bat and .ps1 files. Better regardless of the mail
  problem: no PowerShell execution-policy friction on managed machines, and one
  script instead of six. The .bat/.ps1 wrappers remain in the repository as a
  convenience but are no longer the documented path.
- **`build/make_email_zip.py`** - produces a source archive containing no
  blocked file types, and verifies its own output by re-scanning the finished
  archive, including inside nested archives.
- `make.py doctor` - reports Python version, virtual environment, bundled
  wheels and PyPI reachability without changing anything.

### Changed

- `app.js` ships as `app.js.txt` in the source archive; `make.py setup` restores
  it. `.js` is a blocked attachment type.
- `vendor/wheels` is excluded from the emailed archive. This cannot be worked
  around: PyInstaller ships `.exe` bootloaders inside its own wheel and
  setuptools ships CLI stubs, and renaming files inside a wheel corrupts it.
  Machines without PyPI access need the wheels via Drive, USB or an internal
  mirror - documented in BUILD.md.
- Front-end tests read static assets tolerantly, so they pass whether or not
  `make.py setup` has restored the stashed asset names yet.
- The packaging tests now assert against `make.py`, the authoritative build
  path, and skip the `build.ps1` equivalent when that file is not present.

### Verified

The emailed archive was extracted to a clean folder and taken all the way
through: `make.py setup` restored the stashed asset, installed from PyPI and
passed 235 tests; `make.py build` produced a 17 MB folder whose executable
starts and serves the restored `app.js` correctly.

## 2.1.2-dev - unreleased

Two bugs that both presented as "the page just spins", plus the first verified
standalone build.

### Fixed

- **The busy spinner was on screen permanently.** The `hidden` attribute takes
  its `display: none` from the user-agent stylesheet, so any author-level
  `display` rule beats it -- and `.busy`, `.detected`, `.legend`, `.counts`,
  `.check` and `label` all declare `display: flex`. Every `hidden` toggle in the
  page was therefore inert: the spinner, the legend, the plate chips, the
  Condition field and the mockup checkbox were all visible from the moment the
  page loaded. A `[hidden] { display: none !important }` reset fixes all of them
  at once.
- **The packaged executable would not start at all.** PyInstaller runs its entry
  script as a top-level module with no package context, so pointing it at
  `batchbuilder/__main__.py` failed on that file's relative imports -- before
  any of the application's own error handling existed. Builds now go through
  `build/entry.py`, which imports the package properly.

### Added

- `tests/test_frontend.py` - static checks on the front end, covering the class
  of bug that DOM-state assertions cannot see: the `[hidden]` reset must exist
  and be `!important`, every element the script toggles must exist, no asset may
  reference a remote host, and every request must carry a deadline.
- Packaging guards: the spec must not use `__main__.py` as its entry point, and
  `build.ps1` now smoke-tests the built executable with `--version` before
  packaging is declared successful. A build that cannot start is now a build
  failure.

### Verified

The standalone build was run end to end for the first time: it serves in ~400ms
with Apollo unreachable, serves its bundled assets, parses a plate, generates a
batch, and writes to `ins_files` beside the executable.

## 2.1.1-dev - unreleased

Startup and connection-failure fixes. Reported symptom: the page just spins.

### Fixed

- **The application could die before the web server started.**
  `SqlServerApolloClient.connect()` did a bare `import pyodbc`; if pyodbc was
  missing or broken that raised `ModuleNotFoundError`, which the launcher did
  not catch because it only guarded against `ApolloError`. The process exited
  while the browser had already been told to open, leaving a tab spinning at a
  port nothing was listening on. Missing pyodbc is now an `ApolloError` and the
  application starts regardless.
- **Startup no longer waits on Apollo.** The connection was probed synchronously
  before `serve()`, so any slow or hanging connect delayed the server while the
  browser sat waiting. The probe now runs on a background thread and the page
  reports the connection state itself. Measured: the page answers in under half
  a second with Apollo completely unreachable.
- **The browser is only opened once the server accepts connections**, instead of
  on a fixed 0.7s timer.
- **A batch needing Apollo no longer hangs the UI.** Validation would block a
  worker thread for as long as the ODBC driver took to give up. When the probe
  already knows the server is unreachable the request fails immediately (503)
  with the reason, and the page offers a "Re-check connection" button. Measured:
  the busy overlay clears in ~260ms rather than spinning indefinitely.
- **`/api/health` can no longer block.** It returns the last known state from
  the background probe. A browser polling a hung health check could previously
  tie up every worker thread.
- **The legacy "SQL Server" ODBC driver rejected the connection string.** It
  does not understand `TrustServerCertificate` and fails rather than ignoring
  it. That attribute is now only sent to drivers that support it.
- **Unhandled startup errors no longer vanish.** A packaged build launched by
  double-click printed a traceback into a console window that closed with the
  process. Failures are now reported and the window is held open.
- **Port selection is more robust** on a machine running Docker: the reservation
  is retried, a fallback is announced rather than silent, and total failure
  explains Hyper-V reserved port ranges.

### Added

- Every request from the page has a deadline, so a stalled call surfaces an
  explanation instead of an overlay that spins forever.
- A banner when Apollo is unreachable, stating that plate files can still be
  loaded, inspected and checked for layout problems.
- `POST /api/health/recheck` to retry the connection without restarting.

## 2.1.0-dev - unreleased

Adds Tox6 alongside Tox4. **Tox4 output remains byte-for-byte identical**, still
enforced by `tests/test_golden.py` and verified through the running application.

### Added

- **Second input format.** Tox6 destination plate mappings (`ReportMapping`
  sheet) are read alongside Tox4 Hamilton run reports (`Report` sheet). The
  format is detected from the workbook, never chosen by the analyst.
- **Fill-order detection.** The application works out whether a plate was filled
  across rows (1, 2, 3) or down columns (1, 13, 25) and shows it prominently.
  Note that this required no change to the vial position formula: the existing
  `row_major_12` rule turns a down-column fill into the 1/13/25 sequence on its
  own.
- **Condition detection.** Combo, Quant and Qual are identified from the control
  wells present, displayed on the plate map, and overridable from the form.
- **Tox6 control vocabulary** matched by exact name, with quantitative and
  qualitative controls kept distinct throughout - including on the plate map,
  which now colours the cutoff calibrator and qualitative QCs separately.
- **Tox6 batch generation** with qualitative QCs bracketing the samples.
- **Plate-only mockup mode**: build a Tox6 batch with no Apollo lookup and no
  MBN, for sponsor testing. Every such run is stamped "Not for production use".
- **Acquisition method dropdown** so the `.dam` name is selected rather than
  derived. `TO6_Str1` / `TO6_Str2` ship as placeholders.
- Cross-check that the selected method matches the uploaded file's format.
- `mockups/tox6/` - generated examples of all three conditions with a covering
  note listing exactly what still needs sponsor sign-off.

### Changed

- `ok_statuses` is now `extra_ok_statuses` and is **additive**: it widens each
  format's own accepted statuses rather than replacing them, so a local override
  for one assay cannot silently break the other.
- The drop-zone summary and the plate map now derive from the same counts, so
  they cannot disagree. They previously did, for Tox6 plates.
- Static assets are version-stamped, so an updated build never serves stale
  CSS/JS from a browser cache.

### Fixed

- `batchbuilder.example.json` contained an invalid escape and would not parse.
  It is now covered by a test that loads it and compares it against the built-in
  defaults.

### Still provisional (Tox6)

No Tox6 reference output exists, so these are proposals, all held in data tables:

1. Block order - `BlockLayout` in `generator_tox6.py`.
2. `_Lot` / `_Level` labels - `TOX6_CONTROLS` in `controls.py`.
3. `.dam` names - placeholders `TO6_Str1` / `TO6_Str2`.
4. What Tox6 controls will be called in Apollo. Until that is known, controls in
   a mockup name themselves.

## 2.0.0-dev — unreleased

Rewrite of the original `bb_v1.py`. **Generated batch files are byte-for-byte
identical to the previous version**, enforced by `tests/test_golden.py`.

### Added

- Local web interface, packaged as a self-contained executable. Starts a server
  on `127.0.0.1`, opens the browser, and needs no hosting.
- 96-well plate map, colour-coded by calibrator / control / negative / MBN 1 /
  MBN 2 / repeat / removed, drawn as soon as a report is chosen.
- **Check batch** — full validation with nothing written.
- Run report (`run_report.txt`) written into every output folder: inputs, plate
  contents, files produced, and every error, warning and note.
- Pre-flight checks: calibrator and control completeness, duplicate barcodes,
  specimens in an MBN but not on the plate, the same specimen in both MBNs,
  plate-code characters illegal in file names, MBN format.
- Recent runs list, with per-file and zip download.
- External `batchbuilder.json` for instruments, methods, constants, expectations
  and the Apollo server. All optional; built-in defaults match the original.
- ODBC driver auto-detection with a fallback chain.
- `--demo` mode, replaying recorded Apollo results so the application can be run
  and demonstrated off the lab network.
- Test suite (89 tests), including byte-for-byte golden files.

### Fixed

- Removing aspiration-error samples deleted the wrong rows when a plate had more
  than one error, because indices were collected before deletion and not
  adjusted as the list shrank.
- A plate with no NEG well raised an unexplained `IndexError`.
- Generating the same batch twice within one second crashed on `os.mkdir`.
- The file date stamp was computed at import, so an application left open past
  midnight stamped the previous day.
- The database connection was opened at import; an unreachable Apollo prevented
  the application from starting at all, with no message to the analyst.
- MBNs were interpolated into SQL strings. All queries are parameterised.
- Unrecognised Hamilton statuses were treated as success. Status handling is now
  an allow-list, so an unfamiliar status fails safe and is named in the report.
- Output falls back to a per-user folder when the install folder is read-only,
  instead of failing.

### Preserved deliberately

Reproduced exactly because Ascent consumes these files today. See README for the
full list and reasoning.

- First QC block numbered `QC2`–`QC5` while later blocks use `QC1`–`QC4`.
- Per-MBN files carry the combined file's stem in their `OutputFile` column.
- The MBN 2 file restarts its injection counter, then jumps to the combined
  file's position for samples.
- `2x DW96` selected only by instrument `LC_7`; the original's `"TOX3" in method`
  test could never match and is preserved as an empty config list.

### Open questions

Carried from the handover and not yet answered; current behaviour noted.

1. Exact set of Hamilton failure statuses — currently any status other than
   `No Error` fails.
2. Whether `TO3` should select `2x DW96` — currently it does not.
3. Per-method differences when `TO3`/`TO3b`/`PSY` are re-enabled.
4. Whether this is validated software under change control.
5. Whether an Apollo TEST instance exists to validate against before PROD.
