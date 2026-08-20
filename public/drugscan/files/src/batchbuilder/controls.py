"""What lives in a control well, per assay.

Tox4 and Tox6 name their controls completely differently, and Tox6 splits them
across two analyses:

* **Quantitative** -- a six-point calibration curve plus four QC levels, used to
  put a number on an analyte.
* **Qualitative** -- a single cutoff calibrator plus a low and a high QC that
  bracket it, used to call an analyte present or absent. These cover analytes
  the Tox4 quantitative QCs do not contain, which is why a Combo plate carries
  both sets.

Matching is by explicit name, not substring. The Tox4 generator matched an
Apollo control to a plate well by testing whether the first two characters of
the qcid appeared in the well name; that cannot work here, because "QC" appears
in Neg QC, QC L1, Hydro QC, Low QC and High QC, and "Ca" appears in both Cal 1
and Cutoff Cal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ControlRole(str, Enum):
    QUANT_CAL = "quant_cal"
    QUANT_QC = "quant_qc"
    QUAL_CAL = "qual_cal"
    QUAL_QC = "qual_qc"
    NEG = "neg"
    HYDRO = "hydro"
    EXTRACTION = "extraction"


class Condition(str, Enum):
    """Which analyses a Tox6 plate is set up for."""

    QUANT = "Quant"
    QUAL = "Qual"
    COMBO = "Combo"
    NOT_APPLICABLE = "n/a"

    @property
    def label(self) -> str:
        return {
            Condition.QUANT: "Quantitative",
            Condition.QUAL: "Qualitative",
            Condition.COMBO: "Combo (quantitative + qualitative)",
            Condition.NOT_APPLICABLE: "",
        }[self]


@dataclass(frozen=True)
class ControlSpec:
    """One named control well and how it should appear in the batch file."""

    name: str
    role: ControlRole
    #: Value written to the _Lot and _Level columns.
    label: str
    #: True when the SampleID comes from Apollo; False when the control names
    #: itself, as Tox4 calibrators do.
    from_apollo: bool = True
    #: Apollo qcid for this control, when it differs from the name.
    qcid: str | None = None


@dataclass
class ControlSet:
    """The controls one assay can carry, and what a complete plate looks like."""

    specs: list[ControlSpec] = field(default_factory=list)

    def by_name(self, name: str) -> ControlSpec | None:
        target = name.strip().casefold()
        for spec in self.specs:
            if spec.name.casefold() == target:
                return spec
        return None

    def of_role(self, *roles: ControlRole) -> list[ControlSpec]:
        return [s for s in self.specs if s.role in roles]

    @property
    def names(self) -> set[str]:
        return {s.name.casefold() for s in self.specs}


# --------------------------------------------------------------------------
# Tox6
# --------------------------------------------------------------------------
# Labels are a proposal, not confirmed by the lab. They are the one part of the
# Tox6 output nobody has given us a reference for, so they live here as data and
# can be overridden from batchbuilder.json without touching the generator.

TOX6_CONTROLS = ControlSet([
    ControlSpec("Cal 1", ControlRole.QUANT_CAL, "S1", from_apollo=False),
    ControlSpec("Cal 2", ControlRole.QUANT_CAL, "S2", from_apollo=False),
    ControlSpec("Cal 3", ControlRole.QUANT_CAL, "S3", from_apollo=False),
    ControlSpec("Cal 4", ControlRole.QUANT_CAL, "S4", from_apollo=False),
    ControlSpec("Cal 5", ControlRole.QUANT_CAL, "S5", from_apollo=False),
    ControlSpec("Cal 6", ControlRole.QUANT_CAL, "S6", from_apollo=False),
    ControlSpec("QC L1", ControlRole.QUANT_QC, "QC1"),
    ControlSpec("QC L2", ControlRole.QUANT_QC, "QC2"),
    ControlSpec("QC L3", ControlRole.QUANT_QC, "QC3"),
    ControlSpec("QC L4", ControlRole.QUANT_QC, "QC4"),
    ControlSpec("Neg QC", ControlRole.NEG, "NEG"),
    ControlSpec("Hydro QC", ControlRole.HYDRO, "HYD"),
    ControlSpec("Cutoff Cal", ControlRole.QUAL_CAL, "CUTOFF", from_apollo=False),
    ControlSpec("Low QC", ControlRole.QUAL_QC, "QLOW"),
    ControlSpec("High QC", ControlRole.QUAL_QC, "QHIGH"),
])

#: Which roles each condition must carry for the plate to be complete.
CONDITION_REQUIREMENTS: dict[Condition, dict[ControlRole, int]] = {
    Condition.QUANT: {
        ControlRole.QUANT_CAL: 6,
        ControlRole.QUANT_QC: 4,
        ControlRole.NEG: 1,
        ControlRole.HYDRO: 1,
    },
    Condition.QUAL: {
        ControlRole.QUAL_CAL: 1,
        ControlRole.QUAL_QC: 2,
        ControlRole.NEG: 1,
        ControlRole.HYDRO: 1,
    },
    Condition.COMBO: {
        ControlRole.QUANT_CAL: 6,
        ControlRole.QUANT_QC: 4,
        ControlRole.QUAL_CAL: 1,
        ControlRole.QUAL_QC: 2,
        ControlRole.NEG: 1,
        ControlRole.HYDRO: 1,
    },
}

#: Expected patient sample count per condition, from the sponsor's mock plates.
#: Advisory only -- a short plate is normal, an over-full one is not.
CONDITION_SAMPLE_COUNTS: dict[Condition, int] = {
    Condition.COMBO: 80,
    Condition.QUANT: 84,
    Condition.QUAL: 90,
}


def detect_condition(control_names: list[str],
                     controls: ControlSet = TOX6_CONTROLS) -> Condition:
    """Work out which analyses a plate is set up for from its control wells.

    The three conditions are distinguishable without ambiguity: a qualitative
    cutoff calibrator means qualitative analysis is running, a quantitative
    calibration curve means quantitative analysis is running, and a plate
    carrying both is a Combo.
    """
    roles = set()
    for name in control_names:
        spec = controls.by_name(name)
        if spec is not None:
            roles.add(spec.role)

    has_quant = ControlRole.QUANT_CAL in roles or ControlRole.QUANT_QC in roles
    has_qual = ControlRole.QUAL_CAL in roles or ControlRole.QUAL_QC in roles

    if has_quant and has_qual:
        return Condition.COMBO
    if has_quant:
        return Condition.QUANT
    if has_qual:
        return Condition.QUAL
    return Condition.NOT_APPLICABLE
