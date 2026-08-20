"""Build Tox6 batch files.

Kept apart from the Tox4 generator on purpose. Tox4 output is a live interface
locked byte-for-byte by the golden tests, and nothing here can reach it.

**The block layout below is a proposal, not a confirmed specification.** No Tox6
reference output exists yet, so the sequence of blocks and the _Lot/_Level
labels are our best reading of the sponsor's description. Every part of it is
data -- see :data:`DEFAULT_LAYOUT` and
:data:`~batchbuilder.controls.TOX6_CONTROLS` -- so correcting it after review is
an edit to those tables, not to this logic.

Reasoning behind the proposed layout:

* Quantitative controls bracket the run the way Tox4 does -- a calibration curve
  and QC levels up front, QC levels repeated at the end.
* Qualitative controls (cutoff calibrator, low and high QC) exist because the
  Tox4 quantitative QCs do not contain the qualitative analytes. They bracket
  the samples for the qualitative analysis, so the low and high QCs are written
  both before and after the samples.
* A Combo plate runs both sets; Quant and Qual plates run only theirs.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .controls import (
    CONDITION_REQUIREMENTS, TOX6_CONTROLS, Condition, ControlRole, ControlSet,
)
from .generator import BatchRequest, GeneratorError, RowFactory
from .models import (
    Finding, GeneratedFile, PbiSample, Plate, PlateWell, QcRecord, Severity,
    WellKind,
)


@dataclass
class BlockLayout:
    """Which control roles appear before and after the samples."""

    opening: tuple[ControlRole, ...] = (
        ControlRole.QUANT_CAL,
        ControlRole.QUAL_CAL,
        ControlRole.HYDRO,
        ControlRole.QUANT_QC,
        ControlRole.QUAL_QC,
    )
    closing: tuple[ControlRole, ...] = (
        ControlRole.QUANT_QC,
        ControlRole.QUAL_QC,
    )
    #: Roles written as Type "Standard" rather than "QC".
    standard_roles: tuple[ControlRole, ...] = (
        ControlRole.QUANT_CAL,
        ControlRole.QUAL_CAL,
    )


DEFAULT_LAYOUT = BlockLayout()


@dataclass
class Tox6Context:
    """Everything the Tox6 build needs that is not on the request."""

    controls: ControlSet = TOX6_CONTROLS
    layout: BlockLayout = field(default_factory=BlockLayout)


def _ordered_controls(plate: Plate, controls: ControlSet,
                      roles: tuple[ControlRole, ...]) -> list[PlateWell]:
    """Control wells for the given roles, in declared order, not alphabetical.

    Tox4 sorts controls by name because its names happen to sort correctly.
    Tox6 names do not (High QC would precede Low QC would precede QC L1), so
    ordering comes from the control table instead.
    """
    by_name = {w.barcode.casefold(): w for w in plate.wells if w.role is not None}
    out: list[PlateWell] = []
    for role in roles:
        for spec in controls.of_role(role):
            well = by_name.get(spec.name.casefold())
            if well is not None:
                out.append(well)
    return out


def _sample_id_for(well: PlateWell, controls: ControlSet,
                   apollo_ids: dict[str, str], mockup: bool) -> tuple[str, list[Finding]]:
    """Resolve the SampleID for a control well.

    Calibrators name themselves, as Tox4 calibrators do. Controls take their
    specimen number from Apollo when one is available; in a plate-only mockup,
    or when Apollo has no record, they fall back to their own name and say so.
    """
    spec = controls.by_name(well.barcode)
    if spec is None or not spec.from_apollo:
        return well.barcode, []
    if mockup:
        return well.barcode, []

    key = (spec.qcid or spec.name).casefold()
    found = apollo_ids.get(key) or apollo_ids.get(spec.name.casefold())
    if found:
        return found, []
    return well.barcode, [Finding(
        Severity.WARNING,
        f"Apollo has no control specimen for {spec.name}; the batch file names "
        f"the control itself instead.",
        subject=spec.name,
    )]


def check_condition_controls(plate: Plate, condition: Condition,
                             controls: ControlSet = TOX6_CONTROLS) -> list[Finding]:
    """Confirm the plate carries the full control set for its condition."""
    required = CONDITION_REQUIREMENTS.get(condition)
    if not required:
        return [Finding(
            Severity.ERROR,
            "Could not determine whether this plate is a Combo, Quant or Qual "
            "run. No recognised calibrator or QC wells were found.",
        )]

    out: list[Finding] = []
    present: dict[ControlRole, list[str]] = {}
    for well in plate.wells:
        if well.role is not None:
            present.setdefault(well.role, []).append(well.barcode)

    role_names = {
        ControlRole.QUANT_CAL: "quantitative calibrator",
        ControlRole.QUANT_QC: "quantitative QC",
        ControlRole.QUAL_CAL: "qualitative cutoff calibrator",
        ControlRole.QUAL_QC: "qualitative bracketing QC",
        ControlRole.NEG: "negative QC",
        ControlRole.HYDRO: "hydrolysis QC",
    }

    for role, expected in required.items():
        found = present.get(role, [])
        if len(found) != expected:
            out.append(Finding(
                Severity.ERROR,
                f"A {condition.value} plate needs {expected} "
                f"{role_names.get(role, role.value)} well(s); the plate has "
                f"{len(found)} ({', '.join(sorted(found)) or 'none found'}).",
            ))

    unexpected = set(present) - set(required)
    for role in sorted(unexpected, key=lambda r: r.value):
        out.append(Finding(
            Severity.WARNING,
            f"A {condition.value} plate does not normally carry "
            f"{role_names.get(role, role.value)} wells, but this one has "
            f"{len(present[role])}: {', '.join(sorted(present[role]))}.",
        ))

    if not plate.samples:
        out.append(Finding(
            Severity.ERROR, "The plate contains no patient samples."))

    return out


def build(request: BatchRequest, plate: Plate,
          pbi: list[PbiSample] | None = None,
          qc_by_mbn: dict[str, list[QcRecord]] | None = None,
          context: Tox6Context | None = None
          ) -> tuple[list[GeneratedFile], list[Finding]]:
    """Build the Tox6 batch file.

    A single file per plate: unlike Tox4 there is no combined-plus-per-MBN
    split, because a Tox6 plate carries one condition. Samples are written in
    the order the Hamilton filled the plate, which is what produces the
    1, 13, 25 vial sequence for a column-wise plate.
    """
    ctx = context or Tox6Context()
    notes: list[Finding] = []

    if not plate.negatives:
        raise GeneratorError(
            "The plate has no Neg QC well, so the negative and wash rows cannot "
            "be placed."
        )
    neg_well = plate.negatives[0]

    apollo_ids: dict[str, str] = {}
    for records in (qc_by_mbn or {}).values():
        for rec in records:
            apollo_ids.setdefault(rec.qcid.casefold(), rec.qcspecno)

    neg_id, neg_notes = _sample_id_for(neg_well, ctx.controls, apollo_ids,
                                       request.mockup)
    notes += neg_notes

    f = RowFactory(request, neg_well, neg_id)

    def write_controls(roles: tuple[ControlRole, ...]) -> None:
        for well in _ordered_controls(plate, ctx.controls, roles):
            spec = ctx.controls.by_name(well.barcode)
            sample_id, extra = _sample_id_for(well, ctx.controls, apollo_ids,
                                              request.mockup)
            for note in extra:
                if note not in notes:
                    notes.append(note)
            is_standard = spec.role in ctx.layout.standard_roles
            f.add(
                name=well.barcode,
                sample_id=sample_id,
                row_type="Standard" if is_standard else "QC",
                vial_pos=well.position,
                lot=spec.label,
                level=spec.label,
                kind=WellKind.CAL if is_standard else WellKind.QC,
            )

    # Opening negative, then the opening control block.
    f.wash_row()
    write_controls(ctx.layout.opening)
    f.wash_row()

    # Samples, in the order the machine filled the plate.
    known = {s.barcode for s in (pbi or [])}
    for well in sorted(plate.samples, key=lambda w: w.record_index):
        f.add(name=well.barcode, sample_id=well.barcode, row_type="Unknown",
               vial_pos=well.position, lot="", level="", kind=WellKind.SAMPLE)
        if pbi and well.barcode not in known:
            notes.append(Finding(
                Severity.NOTE,
                f"Sample {well.barcode} in well {well.well_id} is on the plate "
                f"but in no MBN. It will be added to the batch as a repeat.",
                subject=well.barcode,
            ))

    # Closing bracket.
    f.wash_row()
    write_controls(ctx.layout.closing)
    f.wash_row()

    return [GeneratedFile(f"{request.combined_stem}.txt", f.rows)], notes
