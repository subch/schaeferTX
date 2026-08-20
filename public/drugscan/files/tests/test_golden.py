"""The regression net.

These files are already being consumed by Ascent in production. Any change to
the generator that alters a single byte of them is a change to a live interface
and must be a deliberate, separately reviewed decision -- not a side effect of a
refactor. Do not update the expected files to make this test pass.
"""
import pytest

from batchbuilder import generator, hamilton
from batchbuilder.generator import BatchRequest
from conftest import EXPECTED, SAMPLE_XLS


@pytest.fixture(scope="module")
def plate():
    p, findings = hamilton.parse(str(SAMPLE_XLS))
    assert not [f for f in findings if f.blocking], findings
    return p


@pytest.fixture(scope="module")
def generated(plate, apollo, batch_params):
    b = batch_params
    request = BatchRequest(
        instrument=b["instrument"], rack_pos=b["rack_pos"],
        plate_pos=b["plate_pos"], method=b["method"], stream=b["stream"],
        mbn1=b["MBN1"], mbn2=b["MBN2"], plate_code=b["plate_code"],
        date_stamp=b["filedt"],
    )
    pbi = apollo.pbi_samples(b["MBN1"]) + apollo.pbi_samples(b["MBN2"])
    qc = {m: apollo.qc_records(m) for m in (b["MBN1"], b["MBN2"])}
    files, notes = generator.build(request, plate, pbi, qc)
    return {f.name: f for f in files}, notes


def test_produces_exactly_three_files(generated):
    files, _ = generated
    assert sorted(files) == sorted(p.name for p in EXPECTED.glob("*.txt"))


@pytest.mark.parametrize("name", sorted(p.name for p in EXPECTED.glob("*.txt")))
def test_file_is_byte_identical(generated, name):
    files, _ = generated
    assert name in files, f"{name} was not generated"
    got = files[name].render()
    want = (EXPECTED / name).read_bytes()

    if got != want:
        got_lines, want_lines = got.split(b"\r\n"), want.split(b"\r\n")
        for i, (a, e) in enumerate(zip(got_lines, want_lines), start=1):
            if a != e:
                pytest.fail(
                    f"{name} differs at line {i}\n"
                    f"  got : {a.decode(errors='replace')}\n"
                    f"  want: {e.decode(errors='replace')}"
                )
        pytest.fail(
            f"{name} line count differs: {len(got_lines)} vs {len(want_lines)}"
        )


def test_crlf_line_endings_and_trailing_newline(generated):
    files, _ = generated
    for name, f in files.items():
        raw = f.render()
        assert raw.endswith(b"\r\n"), f"{name} must end with a newline"
        assert b"\r\n" in raw, f"{name} must use CRLF"
        assert raw.replace(b"\r\n", b"") .count(b"\n") == 0, (
            f"{name} contains a bare LF"
        )


def test_non_mbn_samples_are_reported(generated):
    _, notes = generated
    assert len(notes) == 23, "the sample plate carries 23 non-MBN specimens"
    assert all("Non-MBN sample" in n.message for n in notes)


def test_single_mbn_produces_one_file(plate, apollo, batch_params):
    b = batch_params
    request = BatchRequest(
        instrument=b["instrument"], rack_pos=b["rack_pos"],
        plate_pos=b["plate_pos"], method=b["method"], stream=b["stream"],
        mbn1=b["MBN1"], plate_code=b["plate_code"], date_stamp=b["filedt"],
    )
    pbi = apollo.pbi_samples(b["MBN1"])
    qc = {b["MBN1"]: apollo.qc_records(b["MBN1"])}
    files, _ = generator.build(request, plate, pbi, qc)
    assert [f.name for f in files] == [
        f"{b['plate_code']}_{b['MBN1']}_{b['filedt']}_"
        f"{b['method']}_Str{b['stream']}_{b['instrument']}.txt"
    ]
