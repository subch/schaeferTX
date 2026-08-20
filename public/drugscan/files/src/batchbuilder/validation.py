"""Pre-flight checks.

Everything here runs before a single file is written. An ERROR blocks
generation; WARNING and NOTE are advisory and are carried into the run report so
the analyst has a record of what the batch actually contained.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .apollo import ApolloClient, ApolloError
from .generator import SINGLE_MBN, BatchRequest
from .controls import CONDITION_SAMPLE_COUNTS, Condition
from .models import Finding, PbiSample, Plate, QcRecord, Severity, WellKind

MBN_RE = re.compile(r"^[A-Za-z0-9]{1,12}$")
PLATE_CODE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,32}$")

#: Windows will not accept these in a file name, and the plate code becomes one.
ILLEGAL_FILENAME_CHARS = set('<>:"/\\|?*')


@dataclass
class ControlExpectations:
    """What a complete plate looks like. Overridable per method from config."""

    cal_levels: int = 7
    qc_levels: int = 4
    require_neg: bool = True
    require_hyd: bool = True
    require_ext: bool = True


@dataclass
class ValidationResult:
    findings: list[Finding] = field(default_factory=list)
    pbi: list[PbiSample] = field(default_factory=list)
    qc_by_mbn: dict[str, list[QcRecord]] = field(default_factory=dict)
    orphans: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return any(f.blocking for f in self.findings)

    def by_severity(self, severity: Severity) -> list[Finding]:
        return [f for f in self.findings if f.severity is severity]

    def add(self, severity: Severity, message: str, subject: str = "") -> None:
        self.findings.append(Finding(severity, message, subject))


def check_form(request: BatchRequest) -> list[Finding]:
    """Validate the analyst's form entries without touching the database."""
    out: list[Finding] = []

    required = {
        "instrument": request.instrument,
        "rack position": request.rack_pos,
        "plate position": request.plate_pos,
        "method": request.method,
        "stream": request.stream,
    }
    for label, value in required.items():
        if not str(value).strip():
            out.append(Finding(Severity.ERROR, f"The {label} has not been selected."))

    plate_code = request.plate_code.strip()
    if not plate_code:
        out.append(Finding(Severity.ERROR, "The plate code is blank."))
    else:
        bad = sorted(set(plate_code) & ILLEGAL_FILENAME_CHARS)
        if bad:
            out.append(Finding(
                Severity.ERROR,
                f"The plate code contains {' '.join(bad)}, which cannot be used "
                f"in a file name.",
            ))
        elif not PLATE_CODE_RE.match(plate_code):
            out.append(Finding(
                Severity.WARNING,
                f"The plate code {plate_code!r} contains unusual characters. "
                f"It will be used as-is in the output file names.",
            ))

    if request.mockup:
        # A plate-only mockup has no batch in Apollo, so there is no MBN to check.
        return out

    if not request.mbn1.strip():
        out.append(Finding(Severity.ERROR, "MBN1 is blank."))
    elif not MBN_RE.match(request.mbn1.strip()):
        out.append(Finding(
            Severity.ERROR,
            f"MBN1 {request.mbn1!r} is not a valid batch number.",
        ))

    if not request.is_single_mbn:
        if not MBN_RE.match(request.mbn2.strip()):
            out.append(Finding(
                Severity.ERROR,
                f"MBN2 {request.mbn2!r} is not a valid batch number. Leave it "
                f"blank or enter {SINGLE_MBN} for a single-MBN run.",
            ))
        elif request.mbn1.strip() == request.mbn2.strip():
            out.append(Finding(
                Severity.ERROR,
                "MBN1 and MBN2 are the same batch number.",
            ))

    return out


def check_controls(plate: Plate,
                   expect: ControlExpectations) -> list[Finding]:
    """Confirm the plate carries a full set of calibrators and controls.

    The original assumed all of this and crashed with an unexplained IndexError
    when a plate was short a NEG well.
    """
    out: list[Finding] = []

    cals = plate.cals
    if len(cals) != expect.cal_levels:
        out.append(Finding(
            Severity.ERROR,
            f"The plate has {len(cals)} calibrator well(s); "
            f"{expect.cal_levels} were expected "
            f"({', '.join(c.barcode for c in cals) or 'none found'}).",
        ))

    negs = plate.negatives
    if expect.require_neg and not negs:
        out.append(Finding(
            Severity.ERROR,
            "The plate has no NEG well. The negative and wash rows have nowhere "
            "to draw from.",
        ))
    elif len(negs) > 1:
        out.append(Finding(
            Severity.WARNING,
            f"The plate has {len(negs)} NEG wells "
            f"({', '.join(n.well_id for n in negs)}). The first will be used.",
        ))

    controls = plate.controls
    numbered = [c for c in controls
                if c.kind is WellKind.QC and "HYD" not in c.barcode.upper()]
    if len(numbered) != expect.qc_levels:
        out.append(Finding(
            Severity.ERROR,
            f"The plate has {len(numbered)} numbered QC well(s); "
            f"{expect.qc_levels} were expected "
            f"({', '.join(c.barcode for c in numbered) or 'none found'}).",
        ))

    if expect.require_hyd and not any(
        "HYD" in c.barcode.upper() for c in controls
    ):
        out.append(Finding(Severity.ERROR, "The plate has no QC_HYD well."))

    if expect.require_ext and not any(
        c.kind is WellKind.EXT for c in controls
    ):
        out.append(Finding(Severity.ERROR, "The plate has no EXT-1 well."))

    if not plate.samples:
        out.append(Finding(
            Severity.ERROR,
            "The plate contains no patient samples, only controls.",
        ))

    return out


def check_apollo(request: BatchRequest, apollo: ApolloClient,
                 result: ValidationResult) -> None:
    """Confirm each MBN exists and collect its samples and controls."""
    for mbn in request.mbns:
        mbn = mbn.strip()
        try:
            exists = apollo.mbn_exists(mbn)
        except ApolloError as exc:
            result.add(Severity.ERROR, str(exc))
            return

        if not exists:
            result.add(
                Severity.ERROR,
                f"MBN {mbn} is not an active batch in Apollo.",
                subject=mbn,
            )
            continue

        samples = apollo.pbi_samples(mbn)
        records = apollo.qc_records(mbn)
        result.pbi.extend(samples)
        result.qc_by_mbn[mbn] = records

        if not samples:
            result.add(
                Severity.WARNING,
                f"MBN {mbn} contains no patient samples.",
                subject=mbn,
            )
        if not records:
            result.add(
                Severity.ERROR,
                f"Apollo returned no QC records for MBN {mbn}. The batch cannot "
                f"be built without control specimen numbers.",
                subject=mbn,
            )
        else:
            result.add(
                Severity.SUCCESS,
                f"MBN {mbn} validated: {len(samples)} sample(s), "
                f"{len(records)} control record(s).",
                subject=mbn,
            )


def reconcile(plate: Plate, result: ValidationResult) -> None:
    """Cross-check the physical plate against what Apollo says should be on it."""
    plate_barcodes = {w.barcode for w in plate.samples}
    seen: dict[str, str] = {}

    for spec in result.pbi:
        if spec.barcode not in plate_barcodes:
            result.add(
                Severity.ERROR,
                f"Specimen {spec.barcode} is in MBN {spec.mbatch} but is not on "
                f"the Hamilton plate.",
                subject=spec.barcode,
            )
        if spec.barcode in seen and seen[spec.barcode] != spec.mbatch:
            result.add(
                Severity.ERROR,
                f"Specimen {spec.barcode} appears in both MBN "
                f"{seen[spec.barcode]} and MBN {spec.mbatch}.",
                subject=spec.barcode,
            )
        seen[spec.barcode] = spec.mbatch

    known = {s.barcode for s in result.pbi}
    result.orphans = [w.barcode for w in plate.samples if w.barcode not in known]
    for barcode in result.orphans:
        well = plate.find_sample(barcode)
        result.add(
            Severity.NOTE,
            f"Sample {barcode} in well {well.well_id} is on the plate but in no "
            f"MBN. It will be added to the batch as a repeat.",
            subject=barcode,
        )

    matched = len(known & plate_barcodes)
    if matched:
        result.add(
            Severity.SUCCESS,
            f"{matched} MBN sample(s) matched between Apollo and the Hamilton "
            f"plate; {len(result.orphans)} repeat(s) found.",
        )


def validate(request: BatchRequest, plate: Plate, apollo: ApolloClient,
             parse_findings: list[Finding] | None = None,
             expect: ControlExpectations | None = None) -> ValidationResult:
    """Run every check. Nothing is written if the result is blocked.

    Which control checks apply depends on the assay: Tox4 expects a fixed set of
    calibrators and QCs, while Tox6 expects whatever its detected condition --
    Combo, Quant or Qual -- calls for.
    """
    from .generator_tox6 import check_condition_controls

    result = ValidationResult()
    result.findings.extend(parse_findings or [])
    result.findings.extend(check_form(request))

    if request.method and not request.method.upper().startswith(plate.assay):
        result.add(
            Severity.ERROR,
            f"The method selected is {request.method}, but this file is a "
            f"{plate.format_name}. Select the method that matches the plate "
            f"file, or upload the right file.")
        return result

    if plate.assay == "TO6":
        condition = request.condition
        if condition is Condition.NOT_APPLICABLE:
            condition = plate.condition
        result.findings.extend(check_condition_controls(plate, condition))
        expected_samples = CONDITION_SAMPLE_COUNTS.get(condition)
        if expected_samples and len(plate.samples) > expected_samples:
            result.add(
                Severity.WARNING,
                f"A {condition.value} plate normally carries "
                f"{expected_samples} samples; this one has "
                f"{len(plate.samples)}.")
    else:
        result.findings.extend(
            check_controls(plate, expect or ControlExpectations()))

    if result.blocked:
        # Do not query Apollo with input we already know is bad.
        return result

    if request.mockup:
        result.add(
            Severity.WARNING,
            "Plate-only mockup: Apollo was not consulted, so no specimen or "
            "control identity has been verified. Not for production use.")
        return result

    check_apollo(request, apollo, result)
    if not result.blocked:
        reconcile(plate, result)
    return result
