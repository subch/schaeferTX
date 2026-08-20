"""Core data types shared by the parser, validators, generator and web UI."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .controls import Condition, ControlRole


class WellKind(str, Enum):
    """What a plate well holds.

    Classification is by barcode substring, matching the original tool's
    precedence exactly: CAL, then QC, then EXT-1, then NEG, then sample.
    """

    CAL = "cal"
    QC = "qc"
    EXT = "ext"
    NEG = "neg"
    SAMPLE = "sample"


class FillOrientation(str, Enum):
    """The order the Hamilton filled the plate.

    ACROSS_ROWS walks A1, A2, A3 ... so consecutive wells are consecutive vial
    positions: the 1, 2, 3 scheme Tox4 uses.

    DOWN_COLUMNS walks A1, B1, C1 ... so consecutive wells are twelve vial
    positions apart: the 1, 13, 25 scheme Tox6 uses. The vial position formula
    is identical in both cases -- only the fill order differs.
    """

    ACROSS_ROWS = "across_rows"
    DOWN_COLUMNS = "down_columns"
    UNKNOWN = "unknown"

    @property
    def label(self) -> str:
        return {
            FillOrientation.ACROSS_ROWS: "Across rows (1, 2, 3 ...)",
            FillOrientation.DOWN_COLUMNS: "Down columns (1, 13, 25 ...)",
            FillOrientation.UNKNOWN: "Indeterminate",
        }[self]

    @property
    def short(self) -> str:
        return {
            FillOrientation.ACROSS_ROWS: "1, 2, 3",
            FillOrientation.DOWN_COLUMNS: "1, 13, 25",
            FillOrientation.UNKNOWN: "?",
        }[self]


class Severity(str, Enum):
    NOTE = "NOTES"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"


@dataclass(frozen=True)
class Finding:
    """One validation result. ERROR blocks generation; the rest are advisory."""

    severity: Severity
    message: str
    subject: str = ""

    @property
    def blocking(self) -> bool:
        return self.severity is Severity.ERROR


@dataclass
class PlateWell:
    """A single aspirated well from the Hamilton report."""

    barcode: str
    well_id: str
    position: int
    status: str
    kind: WellKind
    #: Finer-grained identity for assays that distinguish control types.
    role: ControlRole | None = None
    #: Order the Hamilton visited this well, 1-based. Drives injection order.
    record_index: int = 0

    @property
    def display_name(self) -> str:
        """The name written to the batch file.

        EXT-1 is title-cased on the way out, as the original did.
        """
        return "Ext-1" if self.kind is WellKind.EXT else self.barcode


@dataclass
class Plate:
    """Everything the Hamilton report told us about one plate."""

    wells: list[PlateWell] = field(default_factory=list)
    dropped: list[PlateWell] = field(default_factory=list)
    source_name: str = ""
    #: Which reader parsed this plate, for display.
    format_name: str = ""
    #: Assay family the input format belongs to: TO4 or TO6.
    assay: str = "TO4"
    orientation: FillOrientation = FillOrientation.UNKNOWN
    condition: Condition = Condition.NOT_APPLICABLE

    def of_kind(self, kind: WellKind) -> list[PlateWell]:
        return [w for w in self.wells if w.kind is kind]

    @property
    def cals(self) -> list[PlateWell]:
        return sorted(self.of_kind(WellKind.CAL), key=lambda w: w.barcode)

    @property
    def controls(self) -> list[PlateWell]:
        """QC and Ext-1 wells, name-sorted, as the batch file orders them."""
        both = self.of_kind(WellKind.QC) + self.of_kind(WellKind.EXT)
        return sorted(both, key=lambda w: w.display_name)

    @property
    def negatives(self) -> list[PlateWell]:
        return self.of_kind(WellKind.NEG)

    @property
    def samples(self) -> list[PlateWell]:
        """Patient specimens, in plate order."""
        return self.of_kind(WellKind.SAMPLE)

    def find_sample(self, barcode: str) -> PlateWell | None:
        found = None
        for w in self.samples:
            if w.barcode == barcode:
                found = w  # last match wins, as the original did
        return found


@dataclass(frozen=True)
class PbiSample:
    """A specimen Apollo says belongs to an MBN."""

    pspecno: str
    pcont: str
    mbatch: str

    @property
    def barcode(self) -> str:
        return f"{self.pspecno}{self.pcont}"


@dataclass(frozen=True)
class QcRecord:
    """A (qcid, qcspecno) pair from Apollo.

    qcid encodes level and replicate, e.g. L11 = level 1 replicate 1, L12 =
    level 1 replicate 2. The generator matches it to a plate well by testing
    whether the first two characters appear in the well's barcode, and reads the
    trailing character to decide which QC block the record belongs to.
    """

    qcid: str
    qcspecno: str

    @property
    def is_replicate_two(self) -> bool:
        return self.qcid[-1:] == "2"


@dataclass
class BatchRow:
    """One line of an Ascent batch file, before it is joined with tabs."""

    sample_name: str
    sample_id: str
    row_type: str
    comments: str
    acq_method: str
    proc_method: str
    rack_code: str
    plate_code_col: str
    vial_pos: str
    inj_vol: str
    dilut_fact: str
    wght_to_vol: str
    rack_pos: str
    plate_pos: str
    set_name: str
    output_file: str
    instrument: str
    lot: str
    level: str
    plate_id: str
    qc_name: str
    # not written to the file; drives the UI preview only
    kind: WellKind | None = None

    def to_fields(self) -> list[str]:
        return [
            self.sample_name, self.sample_id, self.row_type, self.comments,
            self.acq_method, self.proc_method, self.rack_code,
            self.plate_code_col, self.vial_pos, self.inj_vol, self.dilut_fact,
            self.wght_to_vol, self.rack_pos, self.plate_pos, self.set_name,
            self.output_file, self.instrument, self.lot, self.level,
            self.plate_id, self.qc_name,
        ]


@dataclass
class GeneratedFile:
    name: str
    rows: list[BatchRow]

    def render(self) -> bytes:
        """Serialise to the exact on-disk bytes: tab separated, CRLF, trailing newline."""
        lines = [TAB.join(FILE_HEADERS)]
        lines += [TAB.join(r.to_fields()) for r in self.rows]
        return ("\r\n".join(lines) + "\r\n").encode("ascii")


TAB = "\t"

FILE_HEADERS = [
    "% header=SampleName", "SampleID", "Type", "Comments", "AcqMethod",
    "ProcMethod", "RackCode", "PlateCode", "VialPos", "SmplInjVol", "DilutFact",
    "WghtToVol", "RackPos", "PlatePos", "SetName", "OutputFile", "_Instrument",
    "_Lot", "_Level", "_PlateID", "_QCNAME",
]
