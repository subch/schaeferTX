"""End-to-end: report file in, batch folder out."""
from pathlib import Path

import pytest

from batchbuilder import service
from batchbuilder.config import Config
from batchbuilder.generator import BatchRequest
from batchbuilder.models import Severity
from conftest import EXPECTED, SAMPLE_XLS


@pytest.fixture
def config(tmp_path):
    c = Config()
    c.output_dir = str(tmp_path / "ins_files")
    return c


def make_request(batch_params, **kw):
    b = batch_params
    base = dict(instrument=b["instrument"], rack_pos=b["rack_pos"],
                plate_pos=b["plate_pos"], method=b["method"], stream=b["stream"],
                mbn1=b["MBN1"], mbn2=b["MBN2"], plate_code=b["plate_code"],
                date_stamp=b["filedt"])
    base.update(kw)
    return BatchRequest(**base)


def test_run_writes_three_files_and_a_report(apollo, config, batch_params):
    result = service.run(make_request(batch_params), str(SAMPLE_XLS), apollo, config)

    assert result.ok, result.error
    assert result.output_dir.is_dir()
    written = sorted(p.name for p in result.output_dir.glob("*.txt"))
    assert written == sorted(
        [p.name for p in EXPECTED.glob("*.txt")] + ["run_report.txt"])
    assert result.report_path.exists()


def test_written_files_are_byte_identical(apollo, config, batch_params):
    result = service.run(make_request(batch_params), str(SAMPLE_XLS), apollo, config)
    for expected in EXPECTED.glob("*.txt"):
        assert (result.output_dir / expected.name).read_bytes() == expected.read_bytes()


def test_report_names_the_inputs_and_the_repeats(apollo, config, batch_params):
    result = service.run(make_request(batch_params), str(SAMPLE_XLS), apollo, config)
    text = result.report_text
    assert "500101" in text and "500102" in text
    assert "abc1234" in text and "LC_13" in text
    assert "Patient samples: 82" in text
    assert text.count("is on the plate but in no MBN") == 23


def test_dry_run_writes_nothing(apollo, config, batch_params):
    result = service.run(make_request(batch_params), str(SAMPLE_XLS), apollo,
                         config, write=False)
    assert result.ok
    assert result.output_dir is None
    assert len(result.files) == 3
    assert not Path(config.output_dir).exists()


def test_each_run_gets_its_own_folder(apollo, config, batch_params):
    a = service.run(make_request(batch_params), str(SAMPLE_XLS), apollo, config)
    b = service.run(make_request(batch_params), str(SAMPLE_XLS), apollo, config)
    assert a.output_dir != b.output_dir
    assert a.ok and b.ok


def test_bad_mbn_blocks_and_writes_nothing(apollo, config, batch_params, tmp_path):
    result = service.run(make_request(batch_params, mbn2="999999"),
                         str(SAMPLE_XLS), apollo, config)
    assert not result.ok
    assert result.output_dir is None
    assert any("not an active batch" in m
               for m in result.messages(Severity.ERROR))


def test_unreadable_input_is_reported_not_raised(apollo, config, batch_params, tmp_path):
    junk = tmp_path / "not_a_workbook.xls"
    junk.write_text("nope")
    result = service.run(make_request(batch_params), str(junk), apollo, config)
    assert not result.ok
    assert "Excel 97-2003" in result.error


def test_preview_covers_every_well(apollo, config, batch_params):
    result = service.run(make_request(batch_params), str(SAMPLE_XLS), apollo,
                         config, write=False)
    preview = result.preview
    assert len(preview.wells) == 96
    assert preview.counts["cal"] == 7
    assert preview.counts["mbn1"] == 30
    assert preview.counts["mbn2"] == 29
    assert preview.counts["repeat"] == 23
    assert preview.counts["neg"] == 1
    assert preview.counts["qc"] == 6


def test_inspect_describes_the_plate_without_apollo(config):
    plate, findings, preview = service.inspect(str(SAMPLE_XLS), config)
    assert len(plate.wells) == 96
    assert findings == []
    assert len(preview.wells) == 96
    assert preview.counts["sample"] == 82


def test_repeats_are_reported_once_not_twice(apollo, config, batch_params):
    """Validation and the generator both notice non-MBN samples; the report
    should mention each specimen once."""
    result = service.run(make_request(batch_params), str(SAMPLE_XLS), apollo, config)
    notes = [f for f in result.findings if f.severity is Severity.NOTE]
    subjects = [n.subject for n in notes]
    assert len(subjects) == len(set(subjects)) == 23


def test_report_names_the_file_the_analyst_chose(apollo, config, batch_params):
    result = service.run(make_request(batch_params), str(SAMPLE_XLS), apollo,
                         config, source_label="260610__401_FULL_REPORT.xls")
    source_line = next(line for line in result.report_text.splitlines()
                       if line.startswith("Hamilton report:"))
    assert source_line.strip() == "Hamilton report: 260610__401_FULL_REPORT.xls"
