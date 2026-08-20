"""Input formats.

Two different machines produce two different workbooks:

* **Tox4** -- a Hamilton run report on a ``Report`` sheet, filled across rows.
* **Tox6** -- a destination-plate mapping on a ``ReportMapping`` sheet, filled
  down columns.

The format is detected from the workbook rather than chosen by the analyst,
because getting it wrong would silently mis-read every well. Both remain fully
supported; Tox4 output is locked byte-for-byte by the golden tests.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .controls import ControlRole, ControlSet, TOX6_CONTROLS
from .models import FillOrientation, WellKind

WELL_RE = re.compile(r"^([A-Za-z])\s*(\d{1,2})$")


@dataclass(frozen=True)
class SheetSpec:
    """How to read one workbook layout."""

    key: str
    label: str
    sheet: str
    assay: str
    barcode_col: str
    well_col: str
    status_col: str
    ok_statuses: tuple[str, ...]
    #: Barcode values meaning "nothing was placed here".
    empty_markers: tuple[str, ...]
    #: Control vocabulary, when the assay names its controls explicitly.
    controls: ControlSet | None = None
    #: Extra columns worth carrying into the run report, if present.
    extra_cols: tuple[str, ...] = ()


TOX4_REPORT = SheetSpec(
    key="tox4_report",
    label="Hamilton run report (Tox4)",
    sheet="Report",
    assay="TO4",
    barcode_col="Asp Container BC",
    well_col="Disp PosID",
    status_col="Asp Status",
    ok_statuses=("No Error", ""),
    empty_markers=("-----",),
    controls=None,  # Tox4 classifies by substring, see hamilton.classify
)

TOX6_MAPPING = SheetSpec(
    key="tox6_mapping",
    label="Destination plate mapping (Tox6)",
    sheet="ReportMapping",
    assay="TO6",
    barcode_col="SPositionBC",
    well_col="TPositionId",
    status_col="TSumStateDescription",
    ok_statuses=("Correct pipetting",),
    empty_markers=("----------",),
    controls=TOX6_CONTROLS,
    extra_cols=("SRackBC", "SPositionId", "TRackBC", "UserName"),
)

FORMATS: tuple[SheetSpec, ...] = (TOX4_REPORT, TOX6_MAPPING)


def detect_format(sheet_names: list[str]) -> SheetSpec | None:
    """Pick the reader whose sheet the workbook actually contains."""
    available = {n.strip().casefold() for n in sheet_names}
    for spec in FORMATS:
        if spec.sheet.casefold() in available:
            return spec
    return None


def parse_well(well_id: str) -> tuple[str, int] | None:
    m = WELL_RE.match(str(well_id).strip())
    if not m:
        return None
    return m.group(1).upper(), int(m.group(2))


def detect_orientation(well_ids: list[str]) -> FillOrientation:
    """Work out whether the plate was filled across rows or down columns.

    Decided by majority vote over consecutive well pairs, so a plate with a gap,
    an unused well or an out-of-order record still classifies correctly. This is
    what tells the analyst whether they are looking at a 1, 2, 3 run or a
    1, 13, 25 run.
    """
    across = down = 0
    previous = None
    for well_id in well_ids:
        current = parse_well(well_id)
        if current is None:
            continue
        if previous is not None:
            row_before, col_before = previous
            row_now, col_now = current
            if row_before == row_now and col_now == col_before + 1:
                across += 1
            elif col_before == col_now and ord(row_now) == ord(row_before) + 1:
                down += 1
        previous = current

    if across == down:
        return FillOrientation.UNKNOWN
    return (FillOrientation.ACROSS_ROWS if across > down
            else FillOrientation.DOWN_COLUMNS)


def classify_tox6(barcode: str,
                  controls: ControlSet) -> tuple[WellKind, ControlRole | None]:
    """Identify a Tox6 well by exact control name, falling back to sample."""
    spec = controls.by_name(barcode)
    if spec is None:
        return WellKind.SAMPLE, None

    kind = {
        ControlRole.QUANT_CAL: WellKind.CAL,
        ControlRole.QUAL_CAL: WellKind.CAL,
        ControlRole.NEG: WellKind.NEG,
    }.get(spec.role, WellKind.QC)
    return kind, spec.role
