"""Orchestration: report in, validated batch folder out.

The web layer calls this and nothing else, so the whole pipeline stays testable
without a browser and reusable from a CLI.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from . import report as report_mod
from .apollo import ApolloClient, ApolloError
from .config import Config, resolve_output_dir
from . import generator_tox6
from .controls import Condition, ControlRole
from .generator import BatchRequest, GeneratorError, build
from .hamilton import HamiltonError, ParseOptions, parse
from .models import (
    FillOrientation, Finding, GeneratedFile, Plate, Severity, WellKind,
)
from .validation import ValidationResult, validate


@dataclass
class PlatePreview:
    """The 96-well map the UI draws before anything is written."""

    wells: list[dict] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)
    #: How the machine filled the plate, and the vial sequence that implies.
    orientation: str = FillOrientation.UNKNOWN.value
    orientation_label: str = ""
    orientation_short: str = ""
    #: Tox6 only: Combo / Quant / Qual.
    condition: str = ""
    condition_label: str = ""
    assay: str = ""
    format_name: str = ""


@dataclass
class RunResult:
    ok: bool
    findings: list[Finding] = field(default_factory=list)
    files: list[GeneratedFile] = field(default_factory=list)
    output_dir: Path | None = None
    report_path: Path | None = None
    report_text: str = ""
    preview: PlatePreview | None = None
    error: str | None = None

    def messages(self, severity: Severity) -> list[str]:
        return [f.message for f in self.findings if f.severity is severity]


def build_preview(plate: Plate, result: ValidationResult | None = None,
                  request: BatchRequest | None = None) -> PlatePreview:
    """Describe every well for the UI, tagged with what it holds."""
    by_position = {w.position: w for w in plate.wells}
    dropped = {w.position: w for w in plate.dropped}
    mbn_of = {}
    if result:
        mbn_of = {s.barcode: s.mbatch for s in result.pbi}
    orphans = set(result.orphans) if result else set()

    wells: list[dict] = []
    counts: dict[str, int] = {}
    for position in range(1, 97):
        well = by_position.get(position)
        gone = dropped.get(position)
        if gone is not None:
            role, label, title = "error", gone.barcode, gone.status
        elif well is None:
            role, label, title = "empty", "", "Empty"
        # Role is checked first: a Tox6 cutoff calibrator is also a CAL well,
        # and the qualitative controls must not be lumped in with the
        # quantitative ones on the map.
        elif well.role is ControlRole.QUAL_CAL:
            role, label, title = "qualcal", well.display_name, "Cutoff calibrator"
        elif well.role is ControlRole.QUAL_QC:
            role, label, title = "qualqc", well.display_name, "Qualitative QC"
        elif well.kind is WellKind.CAL:
            role, label, title = "cal", well.barcode, "Calibrator"
        elif well.kind is WellKind.NEG:
            role, label, title = "neg", well.barcode, "Negative / wash"
        elif well.kind in (WellKind.QC, WellKind.EXT):
            role, label, title = "qc", well.display_name, "Control"
        elif well.barcode in orphans:
            role, label, title = "repeat", well.barcode, "Repeat (in no MBN)"
        else:
            mbn = mbn_of.get(well.barcode)
            if request and mbn == request.mbn1:
                role, title = "mbn1", "MBN " + str(mbn)
            elif request and mbn == request.mbn2:
                role, title = "mbn2", "MBN " + str(mbn)
            else:
                role, title = "sample", "Sample"
            label = well.barcode

        counts[role] = counts.get(role, 0) + 1
        wells.append({
            "position": position,
            "well_id": well.well_id if well else (gone.well_id if gone else ""),
            "role": role,
            "label": label,
            "title": title,
        })

    return PlatePreview(
        wells=wells, counts=counts,
        orientation=plate.orientation.value,
        orientation_label=plate.orientation.label,
        orientation_short=plate.orientation.short,
        condition=plate.condition.value if plate.assay == "TO6" else "",
        condition_label=plate.condition.label if plate.assay == "TO6" else "",
        assay=plate.assay,
        format_name=plate.format_name,
    )


def _unique_folder(root: Path, stem: str) -> Path:
    """Create a fresh run folder.

    The timestamp only resolves to the second, so regenerating a batch twice in
    quick succession would otherwise collide. The original crashed outright when
    that happened.
    """
    stamp = time.strftime("%Y%m%d-%H%M%S")
    candidate = root / f"{stem}-{stamp}"
    suffix = 2
    while True:
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            candidate = root / f"{stem}-{stamp}-{suffix}"
            suffix += 1


def inspect(xls_path: str, config: Config):
    """Parse a report and describe it, without touching Apollo.

    Lets the UI draw the plate map the moment a file is chosen.
    """
    plate, findings = parse(xls_path, ParseOptions(
        extra_ok_statuses=tuple(config.extra_ok_statuses),
        position_strategy=config.position_strategy,
    ))
    return plate, findings, build_preview(plate, None, None)


def run(request: BatchRequest, xls_path: str, apollo: ApolloClient,
        config: Config, write: bool = True,
        source_label: str | None = None) -> RunResult:
    """Validate and, if clean, generate the batch folder.

    Passing write=False runs every check and builds the rows in memory without
    touching disk, which is what the UI uses for its preview. source_label is
    the name to record in the run report, since an upload arrives under a
    temporary name that means nothing to the analyst.
    """
    try:
        plate, parse_findings = parse(xls_path, ParseOptions(
            extra_ok_statuses=tuple(config.extra_ok_statuses),
            position_strategy=config.position_strategy,
        ))
    except HamiltonError as exc:
        return RunResult(ok=False, error=str(exc),
                         findings=[Finding(Severity.ERROR, str(exc))])

    request.settings = config.settings_for(request.method)

    try:
        result = validate(request, plate, apollo, parse_findings,
                          config.expectations_for(request.method))
    except ApolloError as exc:
        return RunResult(ok=False, error=str(exc),
                         findings=parse_findings + [Finding(Severity.ERROR, str(exc))])

    preview = build_preview(plate, result, request)

    if result.blocked:
        return RunResult(ok=False, findings=result.findings, preview=preview,
                         error="Validation failed; nothing was written.")

    try:
        if plate.assay == "TO6":
            if request.condition is Condition.NOT_APPLICABLE:
                request.condition = plate.condition
            files, notes = generator_tox6.build(
                request, plate, result.pbi, result.qc_by_mbn)
        else:
            files, notes = build(request, plate, result.pbi, result.qc_by_mbn)
    except GeneratorError as exc:
        result.add(Severity.ERROR, str(exc))
        return RunResult(ok=False, findings=result.findings, preview=preview,
                         error=str(exc))

    # Validation already reported every non-MBN sample by well, so the
    # generator's own note for the same specimen would list it twice.
    already_noted = {f.subject for f in result.findings if f.subject}
    findings = result.findings + [n for n in notes
                                  if n.subject not in already_noted]

    if not write:
        return RunResult(ok=True, findings=findings, files=files, preview=preview)

    output_root, note = resolve_output_dir(
        Path(config.output_dir) if config.output_dir else None
    )
    folder = _unique_folder(output_root, request.combined_stem)

    for f in files:
        (folder / f.name).write_bytes(f.render())

    text = report_mod.build_report(
        request=request, plate=plate, findings=findings, files=files,
        source_file=source_label or xls_path, output_dir=folder,
        apollo_description=getattr(apollo, "description", "Apollo"),
        config_path=config.source_path, output_note=note,
    )
    report_path = report_mod.write_report(text, folder)

    if note:
        findings.append(Finding(Severity.WARNING, note))

    return RunResult(ok=True, findings=findings, files=files, output_dir=folder,
                     report_path=report_path, report_text=text, preview=preview)
