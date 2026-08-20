"""Checks that the pre-flight validation catches what it is supposed to."""
import copy

import pytest

from batchbuilder import hamilton
from batchbuilder.generator import BatchRequest
from batchbuilder.models import Finding, PlateWell, Severity, WellKind
from batchbuilder.validation import (
    ControlExpectations, check_controls, check_form, reconcile, validate,
    ValidationResult,
)
from conftest import SAMPLE_XLS


@pytest.fixture
def plate():
    p, _ = hamilton.parse(str(SAMPLE_XLS))
    return p


def make_request(**kw):
    base = dict(instrument="LC_13", rack_pos="1", plate_pos="2", method="TO4",
                stream="1", mbn1="500101", mbn2="500102", plate_code="abc1234")
    base.update(kw)
    return BatchRequest(**base)


def errors(findings):
    return [f.message for f in findings if f.severity is Severity.ERROR]


class TestForm:
    def test_clean_form_passes(self):
        assert check_form(make_request()) == []

    def test_blank_plate_code_blocks(self):
        assert any("plate code is blank" in m
                   for m in errors(check_form(make_request(plate_code=""))))

    def test_plate_code_with_path_separator_blocks(self):
        msgs = errors(check_form(make_request(plate_code="abc/1234")))
        assert any("cannot be used in a file name" in m for m in msgs)

    def test_blank_instrument_blocks(self):
        assert any("instrument" in m
                   for m in errors(check_form(make_request(instrument=""))))

    def test_same_mbn_twice_blocks(self):
        msgs = errors(check_form(make_request(mbn1="500101", mbn2="500101")))
        assert any("same batch number" in m for m in msgs)

    def test_single_mbn_does_not_validate_mbn2(self):
        assert check_form(make_request(mbn2="X")) == []

    def test_blank_mbn1_blocks(self):
        assert any("MBN1 is blank" in m
                   for m in errors(check_form(make_request(mbn1=""))))


class TestControls:
    def test_full_plate_passes(self, plate):
        assert check_controls(plate, ControlExpectations()) == []

    def test_missing_neg_blocks(self, plate):
        p = copy.deepcopy(plate)
        p.wells = [w for w in p.wells if w.kind is not WellKind.NEG]
        assert any("no NEG well" in m
                   for m in errors(check_controls(p, ControlExpectations())))

    def test_short_cal_set_blocks(self, plate):
        p = copy.deepcopy(plate)
        cals = [w for w in p.wells if w.kind is WellKind.CAL]
        p.wells.remove(cals[0])
        msgs = errors(check_controls(p, ControlExpectations()))
        assert any("6 calibrator well(s); 7 were expected" in m for m in msgs)

    def test_missing_hyd_blocks(self, plate):
        p = copy.deepcopy(plate)
        p.wells = [w for w in p.wells if "HYD" not in w.barcode.upper()]
        assert any("no QC_HYD" in m
                   for m in errors(check_controls(p, ControlExpectations())))

    def test_missing_ext_blocks(self, plate):
        p = copy.deepcopy(plate)
        p.wells = [w for w in p.wells if w.kind is not WellKind.EXT]
        assert any("no EXT-1" in m
                   for m in errors(check_controls(p, ControlExpectations())))

    def test_expectations_are_configurable(self, plate):
        p = copy.deepcopy(plate)
        p.wells = [w for w in p.wells if w.kind is not WellKind.EXT]
        loose = ControlExpectations(require_ext=False)
        assert not any("EXT-1" in m for m in errors(check_controls(p, loose)))

    def test_second_neg_warns_but_does_not_block(self, plate):
        p = copy.deepcopy(plate)
        neg = next(w for w in p.wells if w.kind is WellKind.NEG)
        p.wells.append(PlateWell("NEG", "H7", 91, "No Error", WellKind.NEG))
        found = check_controls(p, ControlExpectations())
        assert errors(found) == []
        assert any(f.severity is Severity.WARNING for f in found)
        assert neg.position == 92


class TestReconcile:
    def test_missing_specimen_blocks(self, plate, apollo):
        result = ValidationResult()
        result.pbi = apollo.pbi_samples("500101")
        p = copy.deepcopy(plate)
        victim = next(w for w in p.samples if w.barcode == result.pbi[0].barcode)
        p.wells.remove(victim)
        reconcile(p, result)
        assert any("is not on the Hamilton plate" in m
                   for m in errors(result.findings))

    def test_orphans_are_notes_not_errors(self, plate, apollo):
        result = ValidationResult()
        result.pbi = apollo.pbi_samples("500101") + apollo.pbi_samples("500102")
        reconcile(plate, result)
        assert errors(result.findings) == []
        assert len(result.orphans) == 23
        assert len(result.by_severity(Severity.NOTE)) == 23


class TestEndToEnd:
    def test_known_good_batch_is_not_blocked(self, plate, apollo):
        result = validate(make_request(), plate, apollo)
        assert not result.blocked, errors(result.findings)
        assert len(result.pbi) == 59

    def test_unknown_mbn_blocks(self, plate, apollo):
        result = validate(make_request(mbn2="999999"), plate, apollo)
        assert any("not an active batch" in m for m in errors(result.findings))

    def test_apollo_is_not_queried_when_the_form_is_bad(self, plate, apollo):
        result = validate(make_request(plate_code=""), plate, apollo)
        assert result.blocked
        assert result.pbi == []
