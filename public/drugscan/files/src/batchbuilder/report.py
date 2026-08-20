"""The run report written alongside each batch.

Gives the analyst a record of what was actually generated, from what, and what
the checks said -- including the notes and warnings that are easy to click past
in a dialog box.
"""
from __future__ import annotations

import getpass
import platform
import time
from pathlib import Path

from . import __version__
from .generator import BatchRequest
from .models import Finding, GeneratedFile, Plate, Severity

SEVERITY_ORDER = [Severity.ERROR, Severity.WARNING, Severity.NOTE, Severity.SUCCESS]

SEVERITY_HEADING = {
    Severity.ERROR: "ERRORS - these blocked or must be reviewed",
    Severity.WARNING: "WARNINGS - review before loading",
    Severity.NOTE: "NOTES",
    Severity.SUCCESS: "CHECKS PASSED",
}


def _rule(char: str = "-", width: int = 78) -> str:
    return char * width


def build_report(request: BatchRequest, plate: Plate, findings: list[Finding],
                 files: list[GeneratedFile], source_file: str,
                 output_dir: Path, apollo_description: str,
                 config_path: Path | None = None,
                 output_note: str | None = None) -> str:
    """Render the human-readable run report."""
    lines: list[str] = []
    add = lines.append

    add(_rule("="))
    add(f"BATCH BUILDER RUN REPORT  (v{__version__})")
    add(_rule("="))
    add("")
    add(f"Generated      : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    add(f"By             : {getpass.getuser()} on {platform.node()}")
    add(f"Apollo         : {apollo_description}")
    if config_path:
        add(f"Config         : {config_path}")
    add("")
    add(_rule())
    add("INPUTS")
    add(_rule())
    add(f"Hamilton report: {source_file}")
    add(f"Instrument     : {request.instrument}")
    add(f"Method         : {request.method}   Stream: {request.stream}")
    add(f"Rack position  : {request.rack_pos}   Plate position: {request.plate_pos}")
    add(f"Plate code     : {request.plate_code}")
    add(f"MBN1           : {request.mbn1}")
    add(f"MBN2           : {'(single MBN run)' if request.is_single_mbn else request.mbn2}")
    add("")
    add(_rule())
    add("PLATE CONTENTS")
    add(_rule())
    add(f"Calibrators    : {len(plate.cals)}")
    add(f"Controls       : {len(plate.controls)}")
    add(f"Negative wells : {len(plate.negatives)}")
    add(f"Patient samples: {len(plate.samples)}")
    if plate.dropped:
        add(f"Removed        : {len(plate.dropped)} (aspiration errors, listed below)")
        for well in plate.dropped:
            add(f"                 {well.barcode} in {well.well_id}: {well.status}")
    add("")
    add(_rule())
    add("OUTPUT")
    add(_rule())
    add(f"Folder         : {output_dir}")
    if output_note:
        add(f"                 {output_note}")
    for f in files:
        add(f"  {f.name}  ({len(f.rows)} injections)")
    add("")

    for severity in SEVERITY_ORDER:
        matching = [f for f in findings if f.severity is severity]
        if not matching:
            continue
        add(_rule())
        add(SEVERITY_HEADING[severity])
        add(_rule())
        for finding in matching:
            add(f"  - {finding.message}")
        add("")

    add(_rule("="))
    add("End of report")
    add(_rule("="))
    return "\r\n".join(lines) + "\r\n"


def write_report(text: str, output_dir: Path,
                 name: str = "run_report.txt") -> Path:
    path = output_dir / name
    path.write_bytes(text.encode("utf-8"))
    return path
