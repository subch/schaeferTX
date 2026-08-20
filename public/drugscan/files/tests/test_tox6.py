"""Tox6: the second input format, orientation and condition detection, and the
proposed batch layout.

The Tox4 suite guards a live interface byte-for-byte. Nothing here may weaken
it, so these tests also assert that the Tox4 path is untouched by the new
format.
"""
import copy

import pytest

from batchbuilder import generator_tox6, hamilton, service
from batchbuilder.apollo import RecordedApolloClient
from batchbuilder.config import Config
from batchbuilder.controls import (
    TOX6_CONTROLS, Condition, ControlRole, detect_condition,
)
from batchbuilder.generator import BatchRequest
from batchbuilder.models import FillOrientation, Severity, WellKind
from batchbuilder.readers import TOX4_REPORT, TOX6_MAPPING, detect_format, detect_orientation
from conftest import FIXTURES, SAMPLE_XLS

PLATES = {
    "Combo": FIXTURES / "Destination_Plate_Barcode05_7_Tox6 Combo.xls",
    "Quant": FIXTURES / "Destination_Plate_Barcode05_7_Tox6 Quant.xls",
    "Qual": FIXTURES / "Destination_Plate_Barcode05_7_Tox6 Qual.xls",
}

#: Sample counts the sponsor stated for each condition.
EXPECTED_SAMPLES = {"Combo": 80, "Quant": 84, "Qual": 90}


@pytest.fixture(params=sorted(PLATES))
def condition_name(request):
    return request.param


@pytest.fixture
def plate(condition_name):
    p, findings = hamilton.parse(str(PLATES[condition_name]))
    assert not [f for f in findings if f.blocking], findings
    return p


def make_request(**kw):
    base = dict(instrument="LC_13", rack_pos="1", plate_pos="2", method="TO6",
                stream="1", mbn1="", plate_code="Barcode05",
                acq_method_override="TO6_Str1", mockup=True, date_stamp="819")
    base.update(kw)
    return BatchRequest(**base)


class TestFormatDetection:
    def test_tox4_workbook_selects_the_report_reader(self):
        assert detect_format(["Status", "Sample", "Report", "LOAD"]) is TOX4_REPORT

    def test_tox6_workbook_selects_the_mapping_reader(self):
        assert detect_format(["ReportMapping"]) is TOX6_MAPPING

    def test_unknown_workbook_selects_nothing(self):
        assert detect_format(["Sheet1", "Summary"]) is None

    def test_the_two_formats_are_read_from_their_own_files(self, plate):
        assert plate.assay == "TO6"
        tox4, _ = hamilton.parse(str(SAMPLE_XLS))
        assert tox4.assay == "TO4"


class TestOrientation:
    def test_down_columns_is_detected(self):
        wells = [f"{L}{c}" for c in range(1, 13) for L in "ABCDEFGH"]
        assert detect_orientation(wells) is FillOrientation.DOWN_COLUMNS

    def test_across_rows_is_detected(self):
        wells = [f"{L}{c}" for L in "ABCDEFGH" for c in range(1, 13)]
        assert detect_orientation(wells) is FillOrientation.ACROSS_ROWS

    def test_a_gap_does_not_change_the_verdict(self):
        wells = [f"{L}{c}" for c in range(1, 13) for L in "ABCDEFGH"]
        del wells[40]
        assert detect_orientation(wells) is FillOrientation.DOWN_COLUMNS

    def test_tox6_plates_are_down_columns(self, plate):
        assert plate.orientation is FillOrientation.DOWN_COLUMNS
        assert plate.orientation.short == "1, 13, 25"

    def test_tox4_plate_is_across_rows(self):
        tox4, _ = hamilton.parse(str(SAMPLE_XLS))
        assert tox4.orientation is FillOrientation.ACROSS_ROWS
        assert tox4.orientation.short == "1, 2, 3"

    def test_down_column_fill_yields_the_1_13_25_sequence(self, plate):
        """The whole point of the change: the position formula is unchanged, the
        fill order is what produces 1, 13, 25."""
        positions = [w.position for w in
                     sorted(plate.samples, key=lambda w: w.record_index)[:8]]
        assert positions == [1, 13, 25, 37, 49, 61, 73, 85]


class TestConditionDetection:
    def test_each_plate_detects_its_own_condition(self, plate, condition_name):
        assert plate.condition.value == condition_name

    def test_sample_counts_match_the_sponsor_spec(self, plate, condition_name):
        assert len(plate.samples) == EXPECTED_SAMPLES[condition_name]

    def test_quant_needs_no_qualitative_controls(self):
        assert detect_condition(["Cal 1", "QC L1"]) is Condition.QUANT

    def test_qual_is_identified_by_the_cutoff_calibrator(self):
        assert detect_condition(["Cutoff Cal", "Low QC"]) is Condition.QUAL

    def test_both_sets_present_means_combo(self):
        assert detect_condition(["Cal 1", "Cutoff Cal"]) is Condition.COMBO

    def test_nothing_recognisable_is_not_applicable(self):
        assert detect_condition(["banana"]) is Condition.NOT_APPLICABLE


class TestControlNaming:
    def test_every_control_maps_to_exactly_one_role(self, plate):
        for well in plate.wells:
            if well.role is not None:
                assert TOX6_CONTROLS.by_name(well.barcode) is not None

    def test_substring_matching_would_have_been_ambiguous(self):
        """Why Tox6 matches by exact name: the Tox4 rule cannot separate these."""
        qc_named = [s.name for s in TOX6_CONTROLS.specs if "QC" in s.name]
        assert len(qc_named) > 2
        ca_named = [s.name for s in TOX6_CONTROLS.specs if "Ca" in s.name]
        assert len(ca_named) > 1

    def test_qualitative_controls_are_kept_apart_from_quantitative(self):
        combo, _ = hamilton.parse(str(PLATES["Combo"]))
        roles = {w.barcode: w.role for w in combo.wells if w.role}
        assert roles["Cutoff Cal"] is ControlRole.QUAL_CAL
        assert roles["Low QC"] is ControlRole.QUAL_QC
        assert roles["High QC"] is ControlRole.QUAL_QC
        assert roles["QC L1"] is ControlRole.QUANT_QC
        assert roles["Cal 1"] is ControlRole.QUANT_CAL
        assert roles["Neg QC"] is ControlRole.NEG
        assert roles["Hydro QC"] is ControlRole.HYDRO

    def test_unused_wells_are_not_treated_as_specimens(self):
        combo, findings = hamilton.parse(str(PLATES["Combo"]))
        assert len(combo.wells) == 95  # 96 less the deliberately unused A11
        assert not any("----------" in w.barcode for w in combo.wells)
        assert not [f for f in findings if f.blocking]


class TestControlCompleteness:
    def test_each_sponsor_plate_passes_its_own_checks(self, plate):
        findings = generator_tox6.check_condition_controls(plate, plate.condition)
        assert [f for f in findings if f.blocking] == []

    def test_a_missing_qualitative_qc_blocks_a_qual_plate(self):
        p, _ = hamilton.parse(str(PLATES["Qual"]))
        p.wells = [w for w in p.wells if w.barcode != "High QC"]
        findings = generator_tox6.check_condition_controls(p, Condition.QUAL)
        assert any("qualitative bracketing QC" in f.message
                   for f in findings if f.blocking)

    def test_a_short_calibration_curve_blocks_a_quant_plate(self):
        p, _ = hamilton.parse(str(PLATES["Quant"]))
        p.wells = [w for w in p.wells if w.barcode != "Cal 3"]
        findings = generator_tox6.check_condition_controls(p, Condition.QUANT)
        assert any("quantitative calibrator" in f.message
                   for f in findings if f.blocking)

    def test_qualitative_controls_on_a_quant_plate_warn(self):
        p, _ = hamilton.parse(str(PLATES["Combo"]))
        findings = generator_tox6.check_condition_controls(p, Condition.QUANT)
        assert any(f.severity is Severity.WARNING and "does not normally carry"
                   in f.message for f in findings)


class TestGeneratedBatch:
    def test_one_file_per_plate(self, plate, condition_name):
        files, _ = generator_tox6.build(
            make_request(condition=plate.condition), plate)
        assert len(files) == 1
        assert files[0].name == (
            f"Barcode05_{condition_name}_819_TO6_Str1_LC_13.txt")

    def test_samples_are_written_in_fill_order(self, plate):
        files, _ = generator_tox6.build(
            make_request(condition=plate.condition), plate)
        vials = [int(r.vial_pos) for r in files[0].rows if r.row_type == "Unknown"]
        assert vials[:8] == [1, 13, 25, 37, 49, 61, 73, 85]

    def test_every_sample_on_the_plate_is_present(self, plate, condition_name):
        files, _ = generator_tox6.build(
            make_request(condition=plate.condition), plate)
        rows = [r for r in files[0].rows if r.row_type == "Unknown"]
        assert len(rows) == EXPECTED_SAMPLES[condition_name]

    def test_qualitative_qcs_bracket_the_samples(self, plate, condition_name):
        if condition_name == "Quant":
            pytest.skip("a Quant plate carries no qualitative controls")
        files, _ = generator_tox6.build(
            make_request(condition=plate.condition), plate)
        names = [r.sample_name for r in files[0].rows]
        first_sample = next(i for i, r in enumerate(files[0].rows)
                            if r.row_type == "Unknown")
        last_sample = max(i for i, r in enumerate(files[0].rows)
                          if r.row_type == "Unknown")
        for control in ("Low QC", "High QC"):
            before = [i for i, n in enumerate(names) if n == control and i < first_sample]
            after = [i for i, n in enumerate(names) if n == control and i > last_sample]
            assert before and after, f"{control} must appear on both sides"

    def test_quantitative_qcs_bracket_the_samples(self, plate, condition_name):
        if condition_name == "Qual":
            pytest.skip("a Qual plate carries no quantitative QCs")
        files, _ = generator_tox6.build(
            make_request(condition=plate.condition), plate)
        names = [r.sample_name for r in files[0].rows]
        assert names.count("QC L1") == 2

    def test_calibrators_are_written_once_and_only_up_front(self, plate, condition_name):
        if condition_name == "Qual":
            pytest.skip("a Qual plate carries no quantitative calibrators")
        files, _ = generator_tox6.build(
            make_request(condition=plate.condition), plate)
        rows = files[0].rows
        first_sample = next(i for i, r in enumerate(rows) if r.row_type == "Unknown")
        cal_rows = [i for i, r in enumerate(rows) if r.sample_name.startswith("Cal ")]
        assert len(cal_rows) == 6
        assert all(i < first_sample for i in cal_rows)

    def test_calibrators_are_typed_as_standards(self, plate):
        files, _ = generator_tox6.build(
            make_request(condition=plate.condition), plate)
        for row in files[0].rows:
            if row.sample_name in ("Cal 1", "Cutoff Cal"):
                assert row.row_type == "Standard"

    def test_control_labels_come_from_the_control_table(self, plate):
        files, _ = generator_tox6.build(
            make_request(condition=plate.condition), plate)
        labels = {r.sample_name: r.lot for r in files[0].rows}
        for name, expected in (("Cal 1", "S1"), ("QC L1", "QC1"),
                               ("Hydro QC", "HYD"), ("Cutoff Cal", "CUTOFF"),
                               ("Low QC", "QLOW"), ("High QC", "QHIGH")):
            if name in labels:
                assert labels[name] == expected

    def test_the_run_opens_and_closes_on_a_wash(self, plate):
        files, _ = generator_tox6.build(
            make_request(condition=plate.condition), plate)
        rows = files[0].rows
        assert rows[0].sample_name == "NEG1"
        assert rows[-1].sample_name.startswith("WASH-")

    def test_injection_counter_is_sequential(self, plate):
        files, _ = generator_tox6.build(
            make_request(condition=plate.condition), plate)
        suffixes = [int(r.output_file.rsplit("-", 1)[1]) for r in files[0].rows]
        assert suffixes == list(range(1, len(suffixes) + 1))

    def test_acq_method_uses_the_selected_dam(self, plate):
        files, _ = generator_tox6.build(
            make_request(condition=plate.condition,
                         acq_method_override="TO6_Str2"), plate)
        assert all(r.acq_method == "TO6_Str2.dam" for r in files[0].rows)

    def test_output_is_crlf_with_a_trailing_newline(self, plate):
        files, _ = generator_tox6.build(
            make_request(condition=plate.condition), plate)
        raw = files[0].render()
        assert raw.endswith(b"\r\n")
        assert raw.replace(b"\r\n", b"").count(b"\n") == 0

    def test_header_matches_the_tox4_column_contract(self, plate):
        files, _ = generator_tox6.build(
            make_request(condition=plate.condition), plate)
        header = files[0].render().split(b"\r\n")[0].decode()
        assert header.startswith("% header=SampleName\t")
        assert len(header.split("\t")) == 21


class TestServiceIntegration:
    @pytest.fixture
    def config(self, tmp_path):
        c = Config()
        c.output_dir = str(tmp_path / "ins_files")
        return c

    def test_mockup_run_writes_a_batch_without_apollo(self, plate, condition_name,
                                                      config):
        apollo = RecordedApolloClient([], [], {})
        result = service.run(make_request(), str(PLATES[condition_name]),
                             apollo, config)
        assert result.ok, result.error
        assert len(result.files) == 1
        assert (result.output_dir / result.files[0].name).exists()

    def test_mockup_is_flagged_as_unverified(self, condition_name, config):
        apollo = RecordedApolloClient([], [], {})
        result = service.run(make_request(), str(PLATES[condition_name]),
                             apollo, config)
        assert any("Not for production use" in m
                   for m in result.messages(Severity.WARNING))
        assert "Not for production use" in result.report_text

    def test_preview_reports_orientation_and_condition(self, condition_name, config):
        apollo = RecordedApolloClient([], [], {})
        result = service.run(make_request(), str(PLATES[condition_name]),
                             apollo, config, write=False)
        assert result.preview.orientation_short == "1, 13, 25"
        assert result.preview.condition == condition_name
        assert result.preview.assay == "TO6"

    def test_preview_separates_qualitative_from_quantitative_wells(self, config):
        apollo = RecordedApolloClient([], [], {})
        result = service.run(make_request(), str(PLATES["Combo"]), apollo,
                             config, write=False)
        counts = result.preview.counts
        assert counts["cal"] == 6        # quantitative curve
        assert counts["qualcal"] == 1    # cutoff calibrator
        assert counts["qualqc"] == 2     # low + high
        assert sum(counts.values()) == 96


class TestTox4IsUnaffected:
    def test_tox4_plate_still_parses_identically(self):
        plate, findings = hamilton.parse(str(SAMPLE_XLS))
        assert plate.assay == "TO4"
        assert len(plate.wells) == 96
        assert len(plate.cals) == 7
        assert len(plate.samples) == 82
        assert findings == []

    def test_tox4_wells_carry_no_tox6_roles(self):
        plate, _ = hamilton.parse(str(SAMPLE_XLS))
        assert all(w.role is None for w in plate.wells)

    def test_tox4_classification_is_unchanged(self):
        assert hamilton.classify("CAL_L1_TO4") is WellKind.CAL
        assert hamilton.classify("QC_HYD") is WellKind.QC
        assert hamilton.classify("EXT-1") is WellKind.EXT
