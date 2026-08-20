# Tox6 mockup batch files — FOR REVIEW, NOT FOR USE

Generated from the three plate files the project sponsor supplied on 18 August 2026.

**These are a proposal.** No Tox6 reference output exists yet, so the block
order and the `_Lot` / `_Level` labels below are our reading of the description
in the email thread, not a confirmed specification. They have not been validated
against Ascent and the specimen barcodes are the sponsor's mock values
(`Sample Barcode01` …), not real specimens.

| File | Source plate | Injections | Samples |
| --- | --- | --- | --- |
| `Barcode05_Combo_819_TO6_Str1_LC_13.txt` | Tox6 Combo | 104 | 80 |
| `Barcode05_Quant_819_TO6_Str1_LC_13.txt` | Tox6 Quant | 103 | 84 |
| `Barcode05_Qual_819_TO6_Str1_LC_13.txt` | Tox6 Qual | 100 | 90 |

## What is settled

**The vial sequence.** Samples come out 1, 13, 25, 37, 49, 61, 73, 85, 2, 14 …
exactly as agreed. Worth noting: this needed **no change to the position
formula**. The plate is filled down columns instead of across rows, and the
existing formula turns that fill order into the 1/13/25 sequence on its own.

**Condition detection.** Combo, Quant and Qual are told apart automatically from
which control wells are present — a cutoff calibrator means qualitative analysis
is running, a six-point curve means quantitative, both means Combo. The analyst
can override it.

## What needs your review

### 1. Block order

Qualitative controls bracket the samples, since they exist to cover analytes the
quantitative QCs do not contain:

```
Combo:  NEG1 -> Cal 1-6 -> Cutoff Cal -> Hydro QC -> QC L1-L4 -> Low QC -> High QC
        -> WASH -> [80 samples] -> WASH
        -> QC L1-L4 -> Low QC -> High QC -> WASH

Quant:  NEG1 -> Cal 1-6 -> Hydro QC -> QC L1-L4
        -> WASH -> [84 samples] -> WASH -> QC L1-L4 -> WASH

Qual:   NEG1 -> Cutoff Cal -> Hydro QC -> Low QC -> High QC
        -> WASH -> [90 samples] -> WASH -> Low QC -> High QC -> WASH
```

Open questions: should the closing bracket repeat the hydrolysis QC? Should the
cutoff calibrator also appear at the end? Should washes fall anywhere else?

### 2. Control labels

The `_Lot` and `_Level` columns. These are invented:

| Well | Proposed label |
| --- | --- |
| Cal 1 … Cal 6 | `S1` … `S6` |
| QC L1 … QC L4 | `QC1` … `QC4` |
| Neg QC | `NEG` |
| Hydro QC | `HYD` |
| Cutoff Cal | `CUTOFF` |
| Low QC | `QLOW` |
| High QC | `QHIGH` |

### 3. The `.dam` name

`TO6_Str1.dam` is a placeholder. The application offers a dropdown of
acquisition methods so the real names can be selected once known.

### 4. Control identity

Tox4 pulls each control's specimen number from Apollo. These mockups have no
Apollo batch, so every control names itself instead. Once Tox6 controls are
registered in Apollo the real specimen numbers will be used automatically —
we need to know what they will be called there.

## Changing any of this

None of the above is hard-coded. The block order lives in
`src/batchbuilder/generator_tox6.py` (`BlockLayout`) and the labels in
`src/batchbuilder/controls.py` (`TOX6_CONTROLS`) — both plain tables. Corrections
are a data edit, not a rewrite.
