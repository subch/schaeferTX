"""Parser behaviour, including the bugs the original had.

Synthetic workbooks are built with xlwt so failure modes that the one shipped
sample file cannot exercise -- aspiration errors, duplicates, bad wells -- are
actually covered.
"""
import pytest
import xlwt

from batchbuilder import hamilton
from batchbuilder.hamilton import HamiltonError, ParseOptions
from batchbuilder.models import Severity, WellKind
from batchbuilder.positions import PositionError, column_major_8, row_major_12
from conftest import SAMPLE_XLS

HEADERS = ["Transfer Name", "Channel Used", "Asp Rack BC", "Asp Container BC",
           "Asp LabID", "Asp PosID", "Asp Volume", "Asp Status", "Asp Recovery",
           "Disp Rack BC", "Disp Container BC", "Disp LabID", "Disp PosID",
           "Disp Volume", "Disp Status", "Disp Recovery", "Liquid Class"]

I_BARCODE, I_WELL, I_STATUS = 3, 12, 7


def write_xls(path, rows, sheet_name="Report", headers=HEADERS):
    """rows: list of (barcode, well, status)."""
    book = xlwt.Workbook()
    sheet = book.add_sheet(sheet_name)
    for c, h in enumerate(headers):
        sheet.write(0, c, h)
    special = {I_BARCODE, I_WELL, I_STATUS}
    for r, (barcode, well, status) in enumerate(rows, start=1):
        for c in range(len(headers)):
            if c not in special:
                sheet.write(r, c, "")
        sheet.write(r, I_BARCODE, barcode)
        sheet.write(r, I_WELL, well)
        sheet.write(r, I_STATUS, status)
    book.save(str(path))
    return str(path)


class TestPositions:
    @pytest.mark.parametrize("well,expected", [
        ("A1", 1), ("A12", 12), ("B1", 13), ("H1", 85), ("H12", 96),
    ])
    def test_row_major(self, well, expected):
        assert row_major_12(well) == expected

    def test_alternate_strategy_is_available(self):
        assert column_major_8("A1") == 1
        assert column_major_8("H1") == 8
        assert column_major_8("H12") == 96

    @pytest.mark.parametrize("bad", ["I1", "A13", "A0", "", "AA1", "1A", "Z9"])
    def test_invalid_wells_are_rejected(self, bad):
        with pytest.raises(PositionError):
            row_major_12(bad)


class TestClassification:
    @pytest.mark.parametrize("barcode,kind", [
        ("CAL_L1_TO4", WellKind.CAL),
        ("QC_L1_TO4", WellKind.QC),
        ("QC_HYD", WellKind.QC),
        ("EXT-1", WellKind.EXT),
        ("NEG", WellKind.NEG),
        ("4100000001", WellKind.SAMPLE),
    ])
    def test_kinds(self, barcode, kind):
        assert hamilton.classify(barcode) is kind


class TestSampleFile:
    def test_parses_a_full_plate(self):
        plate, findings = hamilton.parse(str(SAMPLE_XLS))
        assert len(plate.wells) == 96
        assert len(plate.cals) == 7
        assert len(plate.samples) == 82
        assert len(plate.negatives) == 1
        assert not findings

    def test_barcodes_do_not_gain_a_float_suffix(self):
        plate, _ = hamilton.parse(str(SAMPLE_XLS))
        assert all(not w.barcode.endswith(".0") for w in plate.wells)

    def test_positions_match_the_shipped_output(self):
        plate, _ = hamilton.parse(str(SAMPLE_XLS))
        by_id = {w.well_id: w.position for w in plate.wells}
        assert by_id["A1"] == 1 and by_id["H8"] == 92 and by_id["H12"] == 96


class TestErrorRows:
    def test_multiple_errored_samples_all_drop_correctly(self, tmp_path):
        """The original collected indices and deleted them one at a time, so
        every deletion after the first removed the wrong row."""
        rows = [(f"SPEC{i:02}", f"A{i}", "No Error") for i in range(1, 13)]
        for i in (2, 4, 6, 8):  # A2, A4, A6, A8 fail
            rows[i - 1] = (f"SPEC{i:02}", f"A{i}", "Liquid Level Error")
        path = write_xls(tmp_path / "errs.xls", rows)

        plate, findings = hamilton.parse(path)

        assert [w.barcode for w in plate.dropped] == [
            "SPEC02", "SPEC04", "SPEC06", "SPEC08"]
        assert [w.barcode for w in plate.wells] == [
            "SPEC01", "SPEC03", "SPEC05", "SPEC07", "SPEC09", "SPEC10",
            "SPEC11", "SPEC12"]
        assert len([f for f in findings if f.severity is Severity.WARNING]) == 4

    def test_unknown_status_is_treated_as_a_failure(self, tmp_path):
        path = write_xls(tmp_path / "u.xls", [
            ("SPEC01", "A1", "No Error"),
            ("SPEC02", "A2", "Clot Detected"),
        ])
        plate, findings = hamilton.parse(path)
        assert [w.barcode for w in plate.dropped] == ["SPEC02"]
        assert any("Clot Detected" in f.message for f in findings)

    def test_extra_ok_statuses_widen_the_allowlist(self, tmp_path):
        path = write_xls(tmp_path / "u.xls", [
            ("SPEC01", "A1", "No Error"),
            ("SPEC02", "A2", "Clot Detected"),
        ])
        opts = ParseOptions(extra_ok_statuses=("Clot Detected",))
        plate, _ = hamilton.parse(path, opts)
        assert plate.dropped == []


class TestBadInput:
    def test_duplicate_barcode_is_an_error(self, tmp_path):
        path = write_xls(tmp_path / "dup.xls", [
            ("SPEC01", "A1", "No Error"),
            ("SPEC02", "A2", "No Error"),
            ("SPEC01", "A3", "No Error"),
        ])
        _, findings = hamilton.parse(path)
        blocking = [f for f in findings if f.blocking]
        assert len(blocking) == 1
        assert "appears twice" in blocking[0].message

    def test_placeholder_rows_are_skipped(self, tmp_path):
        path = write_xls(tmp_path / "ph.xls", [
            ("-----", "A1", "-----"),
            ("SPEC01", "A2", "No Error"),
        ])
        plate, _ = hamilton.parse(path)
        assert [w.barcode for w in plate.wells] == ["SPEC01"]

    def test_bad_well_id_reports_the_row(self, tmp_path):
        path = write_xls(tmp_path / "bad.xls", [
            ("SPEC01", "A1", "No Error"),
            ("SPEC02", "Z9", "No Error"),
        ])
        plate, findings = hamilton.parse(path)
        assert [w.barcode for w in plate.wells] == ["SPEC01"]
        assert any("Row 3" in f.message and f.blocking for f in findings)

    def test_missing_sheet_is_explained(self, tmp_path):
        path = write_xls(tmp_path / "ns.xls", [("SPEC01", "A1", "No Error")],
                         sheet_name="Summary")
        with pytest.raises(HamiltonError, match="none of the sheets"):
            hamilton.parse(path)

    def test_missing_column_is_explained(self, tmp_path):
        headers = list(HEADERS)
        headers[I_STATUS] = "Something Else"
        path = write_xls(tmp_path / "mc.xls", [("SPEC01", "A1", "No Error")],
                         headers=headers)
        with pytest.raises(HamiltonError, match="Asp Status"):
            hamilton.parse(path)

    def test_empty_sheet_is_explained(self, tmp_path):
        with pytest.raises(HamiltonError, match="no data rows"):
            hamilton.parse(write_xls(tmp_path / "e.xls", []))

    def test_all_placeholder_rows_is_explained(self, tmp_path):
        path = write_xls(tmp_path / "all.xls", [("-----", "A1", "-----")])
        with pytest.raises(HamiltonError, match="No usable rows"):
            hamilton.parse(path)

    def test_not_an_xls_is_explained(self, tmp_path):
        junk = tmp_path / "nope.xls"
        junk.write_text("this is not a workbook")
        with pytest.raises(HamiltonError, match="Excel 97-2003"):
            hamilton.parse(str(junk))
