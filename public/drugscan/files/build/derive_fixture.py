"""One-shot: derive an Apollo fixture from the three shipped sample outputs.

The real Apollo DB is unreachable from a dev machine, so the golden regression
test needs stand-in query results.  Everything here is *inferred* from the
known-good output files; the golden test is what proves the inference is
behaviourally equivalent to the real database for this batch.
"""
import json
from pathlib import Path

FIX = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
EXP = FIX / "expected"
MBN1, MBN2 = "500101", "500102"


def rows(name):
    raw = (EXP / name).read_bytes()
    return [ln.decode().split("\t") for ln in raw.split(b"\r\n") if ln.strip()]


def barcode_split(bc):
    # sample_write emits str(pspecno) + str(pcont); an 8+2 split reproduces the
    # 10-digit container barcode.  Only the concatenation is load-bearing.
    return bc[:-2], bc[-2:]


comb = rows(f"abc1234_{MBN1}_{MBN2}_619_TO4_Str1_LC_13.txt")
wash = [i for i, r in enumerate(comb) if r[0].startswith("WASH")]
w1, w2, w3, w4 = wash[0], wash[1], wash[2], wash[3]

mbn1_samples = [r[0] for r in comb[w1 + 1:w2]]
block3 = [(r[0], int(r[8])) for r in comb[w3 + 1:w4]]
# repeats are emitted in plate order after the MBN2 samples, so the single
# position decrease marks the boundary
drop = next(i for i in range(1, len(block3)) if block3[i][1] < block3[i - 1][1])
mbn2_samples = [bc for bc, _ in block3[:drop]]
repeats = [bc for bc, _ in block3[drop:]]

pbi = [list(barcode_split(bc)) + [MBN1] for bc in mbn1_samples]
pbi += [list(barcode_split(bc)) + [MBN2] for bc in mbn2_samples]

# qc_query returns (qcid, qcspecno).  qcid encodes level+replicate: replicate 1
# ids are consumed by the first QC block, replicate 2 by the later blocks.
def qc_set(base):
    n = int(base)
    return [
        ["NEG",   f"Q0494{n + 0}"],
        ["L11",   f"Q0494{n + 1}"],
        ["L21",   f"Q0494{n + 2}"],
        ["L31",   f"Q0494{n + 3}"],
        ["L41",   f"Q0494{n + 4}"],
        ["Ext-1", f"Q0494{n + 5}"],
        ["L12",   f"Q0494{n + 6}"],
        ["L22",   f"Q0494{n + 7}"],
        ["L32",   f"Q0494{n + 8}"],
        ["L42",   f"Q0494{n + 9}"],
        ["HYD",   f"Q0494{n + 10}"],
    ]


fixture = {
    "_note": "Inferred from the shipped sample outputs; not real Apollo data.",
    "batch": {"MBN1": MBN1, "MBN2": MBN2, "plate_code": "abc1234",
              "instrument": "LC_13", "method": "TO4", "stream": "1",
              "rack_pos": "1", "plate_pos": "2", "filedt": "619"},
    "valid_mbns": [MBN1, MBN2],
    "pbi": pbi,
    "qc_data": {MBN1: qc_set(3636), MBN2: qc_set(3647)},
    "_expected_counts": {"mbn1_samples": len(mbn1_samples),
                         "mbn2_samples": len(mbn2_samples),
                         "repeats": len(repeats)},
}

(FIX / "apollo_fixture.json").write_text(json.dumps(fixture, indent=2) + "\n")
print(f"MBN1 samples: {len(mbn1_samples)}  MBN2 samples: {len(mbn2_samples)}  "
      f"repeats: {len(repeats)}  total plate samples: "
      f"{len(mbn1_samples) + len(mbn2_samples) + len(repeats)}")
print(f"pbi rows: {len(pbi)}")
