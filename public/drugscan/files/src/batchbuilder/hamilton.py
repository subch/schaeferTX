"""Read a plate workbook into a Plate.

Handles both supported inputs -- the Tox4 Hamilton run report and the Tox6
destination plate mapping -- by detecting which one a workbook is and reading it
through the matching :class:`~batchbuilder.readers.SheetSpec`.
"""
from __future__ import annotations

from dataclasses import dataclass

import xlrd

from .controls import Condition, detect_condition
from .models import Finding, FillOrientation, Plate, PlateWell, Severity, WellKind
from .positions import PositionError, get_strategy
from .readers import (
    FORMATS, SheetSpec, classify_tox6, detect_format, detect_orientation,
)


class HamiltonError(Exception):
    """The workbook could not be read."""


@dataclass
class ParseOptions:
    #: Statuses accepted in addition to the ones the format already allows.
    #: The format defines its own vocabulary -- "No Error" for Tox4, "Correct
    #: pipetting" for Tox6 -- so this only ever widens what passes.
    extra_ok_statuses: tuple[str, ...] = ()
    position_strategy: str | None = None
    #: Force a reader by key instead of detecting one. Diagnostics only.
    force_format: str | None = None


def _cell_text(value) -> str:
    """xlrd hands back floats for numeric cells; barcodes must not gain a '.0'."""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _open(path: str):
    try:
        return xlrd.open_workbook(path)
    except Exception as exc:  # xlrd raises a grab-bag of exception types
        raise HamiltonError(
            f"Could not open {path} as an .xls workbook. If this file was saved "
            f"as .xlsx or .csv it must be re-saved as Excel 97-2003. ({exc})"
        ) from exc


def _pick_spec(workbook, options: ParseOptions) -> SheetSpec:
    if options.force_format:
        for spec in FORMATS:
            if spec.key == options.force_format:
                return spec
        raise HamiltonError(f"Unknown input format {options.force_format!r}.")

    spec = detect_format(workbook.sheet_names())
    if spec is None:
        expected = ", ".join(f"{s.sheet!r} ({s.label})" for s in FORMATS)
        raise HamiltonError(
            f"This workbook has none of the sheets a plate file should have. "
            f"Expected one of: {expected}. Found: "
            f"{', '.join(workbook.sheet_names())}"
        )
    return spec


def parse(path: str, options: ParseOptions | None = None) -> tuple[Plate, list[Finding]]:
    """Parse the plate workbook at ``path``.

    Returns the plate and any findings raised while reading it. Wells whose
    transfer failed are moved to ``plate.dropped`` rather than deleted in place,
    which is what the original got wrong: it collected indices and then deleted
    them one by one, so every deletion after the first removed the wrong row.
    """
    opts = options or ParseOptions()
    findings: list[Finding] = []

    workbook = _open(path)
    spec = _pick_spec(workbook, opts)

    try:
        sheet = workbook.sheet_by_name(spec.sheet)
    except Exception:
        raise HamiltonError(
            f"The workbook has no {spec.sheet!r} sheet. Found: "
            f"{', '.join(workbook.sheet_names())}"
        ) from None

    if sheet.nrows < 2:
        raise HamiltonError(f"The {spec.sheet!r} sheet has no data rows.")

    header = [_cell_text(sheet.cell(0, c).value) for c in range(sheet.ncols)]
    wanted = (spec.barcode_col, spec.well_col, spec.status_col)
    missing = [c for c in wanted if c not in header]
    if missing:
        raise HamiltonError(
            f"The {spec.sheet!r} sheet is missing required column(s): "
            f"{', '.join(missing)}. Found: {', '.join(header)}"
        )
    i_barcode = header.index(spec.barcode_col)
    i_well = header.index(spec.well_col)
    i_status = header.index(spec.status_col)

    ok_statuses = tuple(spec.ok_statuses) + tuple(opts.extra_ok_statuses)
    to_position = get_strategy(opts.position_strategy)

    plate = Plate(source_name=path, format_name=spec.label, assay=spec.assay)
    seen: dict[str, PlateWell] = {}
    well_order: list[str] = []
    record = 0

    for r in range(1, sheet.nrows):
        barcode = _cell_text(sheet.cell(r, i_barcode).value)
        if barcode == "" or barcode in spec.empty_markers:
            # A deliberately unused well. Still counts for orientation, because
            # the machine visited it.
            well_id = _cell_text(sheet.cell(r, i_well).value)
            if well_id:
                well_order.append(well_id)
            continue

        well_id = _cell_text(sheet.cell(r, i_well).value)
        status = _cell_text(sheet.cell(r, i_status).value)
        well_order.append(well_id)
        record += 1

        try:
            position = to_position(well_id)
        except PositionError as exc:
            findings.append(Finding(
                Severity.ERROR,
                f"Row {r + 1} of the plate file: {exc}",
                subject=barcode,
            ))
            continue

        if spec.controls is not None:
            kind, role = classify_tox6(barcode, spec.controls)
        else:
            kind, role = classify(barcode), None

        well = PlateWell(
            barcode=barcode,
            well_id=well_id,
            position=position,
            status=status,
            kind=kind,
            role=role,
            record_index=record,
        )

        if status not in ok_statuses:
            plate.dropped.append(well)
            findings.append(Finding(
                Severity.WARNING,
                f"Specimen {barcode} in well {well_id} reported "
                f"{status!r} and has been removed from the batch. "
                f"If it is a patient sample it must also be removed from the MBN.",
                subject=barcode,
            ))
            continue

        if barcode in seen:
            findings.append(Finding(
                Severity.ERROR,
                f"Specimen {barcode} appears twice on the plate, in wells "
                f"{seen[barcode].well_id} and {well_id}.",
                subject=barcode,
            ))
        seen[barcode] = well
        plate.wells.append(well)

    if not plate.wells:
        raise HamiltonError(
            f"No usable rows found in the {spec.sheet!r} sheet. Every row was "
            f"blank, an unused-well placeholder, or an error."
        )

    plate.orientation = detect_orientation(well_order)
    if spec.controls is not None:
        plate.condition = detect_condition(
            [w.barcode for w in plate.wells if w.role is not None], spec.controls)

    if plate.orientation is FillOrientation.UNKNOWN:
        findings.append(Finding(
            Severity.WARNING,
            "Could not tell whether this plate was filled across rows or down "
            "columns. Check the vial positions before loading.",
        ))

    return plate, findings


def classify(barcode: str) -> WellKind:
    """Bucket a Tox4 barcode by substring.

    Precedence matters and is inherited from the original: a barcode containing
    both 'CAL' and 'QC' is a calibrator. Kept identical so plates that have been
    running for years keep classifying the same way.
    """
    name = str(barcode).upper()
    if "CAL" in name:
        return WellKind.CAL
    if "QC" in name:
        return WellKind.QC
    if "EXT-1" in name:
        return WellKind.EXT
    if "NEG" in name:
        return WellKind.NEG
    return WellKind.SAMPLE
