"""Run the verbatim reference implementation against the derived fixture and
diff byte-for-byte against the shipped sample output.

A pass proves the fixture is behaviourally equivalent to real Apollo for this
batch, which is what makes the golden regression test meaningful.
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reference_impl as ref  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
EXP = FIX / "expected"

fixture = json.loads((FIX / "apollo_fixture.json").read_text())
b = fixture["batch"]
qc_data = {k: [tuple(r) for r in v] for k, v in fixture["qc_data"].items()}
pbi = [tuple(r) for r in fixture["pbi"]]

batchdata = ref.hamilton_intake(str(FIX / "260610__401_FULL_REPORT.xls"))
print(f"parsed {len(batchdata)} plate rows from the .xls")

out = Path(tempfile.mkdtemp(prefix="bbref_"))
written = ref.file_writer(
    outdir=str(out), filedt=b["filedt"], qc_lookup=lambda m: qc_data[m],
    instrument=b["instrument"], rack_pos=b["rack_pos"], plate_pos=b["plate_pos"],
    method=b["method"], stream=b["stream"], MBN1=b["MBN1"], MBN2=b["MBN2"],
    plate_code=b["plate_code"], batchdata=batchdata, pbi=pbi,
)

failures = 0
for p in written:
    p = Path(p)
    expected = EXP / p.name
    if not expected.exists():
        print(f"  ?? {p.name}: no shipped counterpart")
        failures += 1
        continue
    got, want = p.read_bytes(), expected.read_bytes()
    if got == want:
        print(f"  OK {p.name}  ({len(want)} bytes identical)")
    else:
        failures += 1
        print(f"  FAIL {p.name}: {len(got)} bytes vs expected {len(want)}")
        gl, wl = got.split(b"\r\n"), want.split(b"\r\n")
        for i, (a, e) in enumerate(zip(gl, wl)):
            if a != e:
                print(f"       first diff line {i + 1}")
                print(f"         got : {a.decode(errors='replace')}")
                print(f"         want: {e.decode(errors='replace')}")
                break
        if len(gl) != len(wl):
            print(f"       line count {len(gl)} vs {len(wl)}")

missing = {p.name for p in EXP.glob('*.txt')} - {Path(p).name for p in written}
if missing:
    print(f"  NOT GENERATED: {sorted(missing)}")
    failures += 1

shutil.rmtree(out, ignore_errors=True)
print("\nFIXTURE VALIDATED" if not failures else f"\n{failures} FAILURE(S)")
sys.exit(1 if failures else 0)
