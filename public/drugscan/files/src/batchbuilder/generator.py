"""Build Ascent batch files.

The output of this module is contract: Ascent already consumes these files, so
every quirk of the original layout is reproduced deliberately and the golden
regression test in tests/ enforces it byte-for-byte. Where a quirk looks like a
mistake it is commented as such rather than fixed.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .controls import Condition
from .models import (
    BatchRow, Finding, GeneratedFile, PbiSample, Plate, PlateWell, QcRecord,
    Severity, WellKind,
)

SINGLE_MBN = "X"


class GeneratorError(Exception):
    """The batch could not be built."""


@dataclass
class BatchSettings:
    """Values that do not vary per row. Overridable from config."""

    proc_method: str = "none"
    inj_vol: str = "10"
    dilut_fact: str = "1"
    wght_to_vol: str = "0"
    set_name: str = "SET1"
    comments: str = ""
    default_rack_code: str = "Deep Well MTP 96 Cooled"
    default_plate_type: str = "Deep Well MTP 96 Cooled"
    alt_rack_code: str = "3 Drawer"
    alt_plate_type: str = "2x DW96"
    #: Instruments that use the alternate rack/plate type.
    alt_instruments: tuple[str, ...] = ("LC_7",)
    #: Methods that use the alternate rack/plate type. The original tested for
    #: "TOX3", a string none of its method options could ever contain, so this
    #: branch has only ever been reachable via alt_instruments. Left empty to
    #: preserve that behaviour exactly; add "TO3" here once the lab confirms.
    alt_methods: tuple[str, ...] = ()


@dataclass
class BatchRequest:
    """Everything the analyst chose on the form."""

    instrument: str
    rack_pos: str
    plate_pos: str
    method: str
    stream: str
    mbn1: str
    plate_code: str
    mbn2: str = SINGLE_MBN
    date_stamp: str | None = None
    settings: BatchSettings = field(default_factory=BatchSettings)
    #: Explicit acquisition method (.dam) name. When unset the Tox4 convention
    #: of "<method>_Str<stream>" is used. Tox6 selects one from a list instead,
    #: because the .dam names are owned by the instrument, not derived.
    acq_method_override: str | None = None
    #: Tox6 only: which analyses the plate runs. Detected from the plate.
    condition: Condition = Condition.NOT_APPLICABLE
    #: Build straight from the plate with no Apollo lookup and no MBN. Used for
    #: sponsor mockups, where the specimens are not real and no batch exists.
    mockup: bool = False

    @property
    def is_single_mbn(self) -> bool:
        return self.mbn2 == SINGLE_MBN or not self.mbn2

    @property
    def mbns(self) -> list[str]:
        return [self.mbn1] if self.is_single_mbn else [self.mbn1, self.mbn2]

    @property
    def acq_method(self) -> str:
        return self.acq_method_override or f"{self.method}_Str{self.stream}"

    @property
    def stamp(self) -> str:
        """Month+day with leading zeros stripped, e.g. 19 June -> '619'.

        Computed when the batch is built. The original computed it once at
        import, so an application left open overnight stamped the previous day.
        """
        return self.date_stamp or time.strftime("%m%d").lstrip("0")

    @property
    def combined_stem(self) -> str:
        if self.mockup:
            # No MBN exists, so the condition identifies the file instead.
            return (f"{self.plate_code}_{self.condition.value}_{self.stamp}_"
                    f"{self.acq_method}_{self.instrument}")
        suffix = "" if self.is_single_mbn else f"_{self.mbn2}"
        return (f"{self.plate_code}_{self.mbn1}{suffix}_{self.stamp}_"
                f"{self.acq_method}_{self.instrument}")

    def stem_for(self, mbn: str) -> str:
        return (f"{self.plate_code}_{mbn}_{self.stamp}_{self.acq_method}_"
                f"{self.instrument}")

    def rack_and_plate(self) -> tuple[str, str]:
        s = self.settings
        if self.instrument in s.alt_instruments or any(
            m in self.method for m in s.alt_methods
        ):
            return s.alt_rack_code, s.alt_plate_type
        return s.default_rack_code, s.default_plate_type


def resolve_first_block(controls: list[PlateWell],
                        records: list[QcRecord]) -> dict[str, str]:
    """Map control well -> specimen number for the opening QC block.

    A record matches when its first two characters appear in the well barcode.
    Records whose qcid ends in "2" are the second replicate and belong to the
    later blocks. Last match wins, as in the original.
    """
    out: dict[str, str] = {}
    for well in controls:
        for rec in records:
            # Matched against the display name, not the raw barcode: the plate
            # spells it EXT-1 while Apollo spells it Ext-1, and the match is
            # case-sensitive.
            if rec.qcid[:2] in well.display_name and not rec.is_replicate_two:
                out[well.display_name] = rec.qcspecno
    return out


def resolve_repeat_block(controls: list[PlateWell],
                         records: list[QcRecord]) -> list[tuple[PlateWell, str]]:
    """Well/specimen pairs for a repeated QC block (replicate 2 records only).

    HYD and Ext-1 fall out naturally because their qcids do not end in "2". The
    original also carried an explicit `!= "HYD" or != "Ext-1"` guard, which is
    always true and therefore did nothing; it is not reproduced.
    """
    out: list[tuple[PlateWell, str]] = []
    for well in controls:
        for rec in records:
            if rec.qcid[:2] in well.display_name and rec.is_replicate_two:
                out.append((well, rec.qcspecno))
    return out


class _RowFactory:
    """Builds rows for one file, tracking the injection counter."""

    def __init__(self, request: BatchRequest, neg_well: PlateWell,
                 neg_specno: str, start_filenum: int = 1):
        self.r = request
        self.s = request.settings
        self.rack_code, self.plate_type = request.rack_and_plate()
        self.neg_well = neg_well
        self.neg_specno = neg_specno
        self.filenum = start_filenum
        self.wash = 0
        self.rows: list[BatchRow] = []

    def _output_file(self) -> str:
        # Always the combined stem, even inside the per-MBN files.
        return f"{self.r.combined_stem}-{self.filenum:03}"

    def _add(self, *, name: str, sample_id: str, row_type: str, vial_pos,
             lot: str, level: str, qc_name: str = "",
             kind: WellKind | None = None) -> None:
        self.rows.append(BatchRow(
            sample_name=name,
            sample_id=sample_id,
            row_type=row_type,
            comments=self.s.comments,
            acq_method=f"{self.r.acq_method}.dam",
            proc_method=self.s.proc_method,
            rack_code=self.rack_code,
            plate_code_col=self.plate_type,
            vial_pos=str(vial_pos),
            inj_vol=self.s.inj_vol,
            dilut_fact=self.s.dilut_fact,
            wght_to_vol=self.s.wght_to_vol,
            rack_pos=self.r.rack_pos,
            plate_pos=self.r.plate_pos,
            set_name=self.s.set_name,
            output_file=self._output_file(),
            instrument=self.r.instrument,
            lot=lot,
            level=level,
            plate_id=self.r.plate_code,
            qc_name=qc_name,
            kind=kind,
        ))
        self.filenum += 1

    def add(self, **kw) -> None:
        """Public entry point so other assay generators can emit a row."""
        self._add(**kw)

    def wash_row(self) -> None:
        """The negative that opens the file, then a wash between each block."""
        if self.wash == 0:
            name, sample_id = "NEG1", self.neg_specno
        else:
            name = sample_id = f"WASH-{self.wash}"
        self._add(name=name, sample_id=sample_id, row_type="QC",
                  vial_pos=self.neg_well.position, lot="NEG", level="NEG",
                  qc_name="NEG", kind=WellKind.NEG)
        self.wash += 1

    def cal_rows(self, cals: list[PlateWell]) -> None:
        for i, well in enumerate(cals, start=1):
            self._add(name=well.barcode, sample_id=well.barcode,
                      row_type="Standard", vial_pos=well.position,
                      lot=f"S{i}", level=f"S{i}", kind=WellKind.CAL)

    def qc_rows(self, pairs: list[tuple[PlateWell, str]]) -> None:
        """Write a QC block.

        The level counter increments for any well whose barcode contains "QC",
        including QC_HYD -- which is labelled HYD but still advances the count.
        That is why the opening block reads QC2..QC5 while later blocks read
        QC1..QC4. Ascent consumes this today; do not "fix" it without new
        golden files.
        """
        counter = 1
        for well, specno in pairs:
            name = well.display_name
            if "HYD" in name:
                label = "HYD"
            elif "QC" in name:
                label = f"QC{counter}"
            else:
                label = "Ext-1"
            self._add(name=name, sample_id=specno, row_type="QC",
                      vial_pos=well.position, lot=label, level=label,
                      kind=well.kind)
            if "QC" in name:
                counter += 1

    def sample_rows(self, plate: Plate, pbi: list[PbiSample], mbn: str) -> None:
        """Patient samples for one MBN, in Apollo order."""
        for spec in pbi:
            if spec.mbatch != mbn:
                continue
            well = plate.find_sample(spec.barcode)
            # "ERROR" in the position column is the original's marker for a
            # specimen Apollo expects that the plate does not have. Validation
            # blocks this case before generation, so it should be unreachable.
            vial_pos = well.position if well else "ERROR"
            self._add(name=spec.barcode, sample_id=spec.barcode,
                      row_type="Unknown", vial_pos=vial_pos, lot="", level="",
                      kind=WellKind.SAMPLE)

    def repeat_rows(self, plate: Plate,
                    pbi: list[PbiSample]) -> list[Finding]:
        """Wells on the plate that belong to no MBN, in plate order."""
        known = {s.barcode for s in pbi}
        notes: list[Finding] = []
        for well in plate.samples:
            if well.barcode in known:
                continue
            self._add(name=well.barcode, sample_id=well.barcode,
                      row_type="Unknown", vial_pos=well.position, lot="",
                      level="", kind=WellKind.SAMPLE)
            notes.append(Finding(
                Severity.NOTE,
                f"Non-MBN sample {well.barcode} in well {well.well_id} "
                f"(position {well.position}) added to the batch.",
                subject=well.barcode,
            ))
        return notes


#: Public alias: the Tox6 generator builds its rows with the same factory.
RowFactory = _RowFactory


def _neg_specno(records: list[QcRecord]) -> str | None:
    for rec in records:
        if rec.qcid == "NEG":
            return rec.qcspecno
    return None


def build(request: BatchRequest, plate: Plate, pbi: list[PbiSample],
          qc_by_mbn: dict[str, list[QcRecord]]
          ) -> tuple[list[GeneratedFile], list[Finding]]:
    """Build every batch file for this request.

    Two MBNs produce three files: a combined file, then one per MBN. A single
    MBN produces one file. Returns the files and any notes raised while
    building them.
    """
    if not plate.negatives:
        raise GeneratorError(
            "The plate has no NEG well, so the negative and wash rows cannot be "
            "placed. Check the Hamilton report."
        )
    if not plate.cals:
        raise GeneratorError("The plate has no calibrator wells.")

    neg_well = plate.negatives[0]
    controls = plate.controls
    notes: list[Finding] = []

    qc1 = qc_by_mbn.get(request.mbn1, [])
    neg1 = _neg_specno(qc1)
    if neg1 is None:
        raise GeneratorError(
            f"Apollo returned no NEG control for MBN {request.mbn1}."
        )

    def opening_pairs(records: list[QcRecord]) -> list[tuple[PlateWell, str]]:
        resolved = resolve_first_block(controls, records)
        missing = [w.display_name for w in controls
                   if w.display_name not in resolved]
        if missing:
            raise GeneratorError(
                "Apollo returned no control specimen for: "
                + ", ".join(missing)
                + ". The plate and the MBN do not agree on which controls ran."
            )
        return [(w, resolved[w.display_name]) for w in controls]

    files: list[GeneratedFile] = []

    if request.is_single_mbn:
        f = _RowFactory(request, neg_well, neg1)
        f.wash_row()
        f.cal_rows(plate.cals)
        f.qc_rows(opening_pairs(qc1))
        f.wash_row()
        f.sample_rows(plate, pbi, request.mbn1)
        f.wash_row()
        notes += f.repeat_rows(plate, pbi)
        f.qc_rows(resolve_repeat_block(controls, qc1))
        f.wash_row()
        files.append(GeneratedFile(f"{request.stem_for(request.mbn1)}.txt", f.rows))
        return files, notes

    qc2 = qc_by_mbn.get(request.mbn2, [])
    neg2 = _neg_specno(qc2)
    if neg2 is None:
        raise GeneratorError(
            f"Apollo returned no NEG control for MBN {request.mbn2}."
        )

    # --- combined file -----------------------------------------------------
    c = _RowFactory(request, neg_well, neg1)
    c.wash_row()
    c.cal_rows(plate.cals)
    c.qc_rows(opening_pairs(qc1))
    c.wash_row()
    c.sample_rows(plate, pbi, request.mbn1)
    c.wash_row()
    c.qc_rows(resolve_repeat_block(controls, qc1))
    c.wash_row()
    # The per-MBN2 file continues this counter rather than restarting, so the
    # two files agree on injection numbers for the same physical vials.
    mbn2_start = c.filenum
    c.sample_rows(plate, pbi, request.mbn2)
    notes += c.repeat_rows(plate, pbi)
    c.wash_row()
    c.qc_rows(resolve_repeat_block(controls, qc2))
    c.wash_row()
    files.append(GeneratedFile(f"{request.combined_stem}.txt", c.rows))

    # --- MBN1 file ---------------------------------------------------------
    a = _RowFactory(request, neg_well, neg1)
    a.wash_row()
    a.cal_rows(plate.cals)
    a.qc_rows(opening_pairs(qc1))
    a.wash_row()
    a.sample_rows(plate, pbi, request.mbn1)
    a.wash_row()
    a.qc_rows(resolve_repeat_block(controls, qc1))
    a.wash_row()
    files.append(GeneratedFile(f"{request.stem_for(request.mbn1)}.txt", a.rows))

    # --- MBN2 file ---------------------------------------------------------
    b = _RowFactory(request, neg_well, neg2)
    b.wash_row()
    b.cal_rows(plate.cals)
    b.qc_rows(opening_pairs(qc2))
    b.wash_row()
    b.filenum = mbn2_start
    b.sample_rows(plate, pbi, request.mbn2)
    b.repeat_rows(plate, pbi)  # notes already collected from the combined file
    b.wash_row()
    b.qc_rows(resolve_repeat_block(controls, qc2))
    b.wash_row()
    files.append(GeneratedFile(f"{request.stem_for(request.mbn2)}.txt", b.rows))

    return files, notes
