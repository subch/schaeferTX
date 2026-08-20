"""Well-ID to vial-position mapping.

Isolated behind a named strategy because the lab expects this rule to change:
how a plate location becomes an Ascent vial position is the one piece of logic
most likely to be revisited. Adding a new rule means adding a function here and
naming it in the config, not editing the generator.
"""
from __future__ import annotations

import re
from typing import Callable

WELL_RE = re.compile(r"^([A-Za-z])\s*(\d{1,2})$")


class PositionError(ValueError):
    """A well ID could not be mapped to a vial position."""


def _parse_well(well_id: str) -> tuple[str, int]:
    m = WELL_RE.match(str(well_id).strip())
    if not m:
        raise PositionError(f"{well_id!r} is not a well ID like A1 or H12")
    letter, number = m.group(1).upper(), int(m.group(2))
    if not ("A" <= letter <= "H"):
        raise PositionError(f"{well_id!r} has row letter {letter}, expected A-H")
    if not (1 <= number <= 12):
        raise PositionError(f"{well_id!r} has column {number}, expected 1-12")
    return letter, number


def row_major_12(well_id: str) -> int:
    """A1..A12 -> 1..12, B1 -> 13, ... H12 -> 96.

    This is the rule the original tool used and the one Ascent currently
    expects. Do not change it without regenerating the golden files.
    """
    letter, number = _parse_well(well_id)
    return (ord(letter) - ord("A")) * 12 + number


def column_major_8(well_id: str) -> int:
    """A1..H1 -> 1..8, A2 -> 9, ... H12 -> 96.

    Standard column-wise plate ordering. Not used by any current method; present
    so switching is a config change rather than a code change.
    """
    letter, number = _parse_well(well_id)
    return (number - 1) * 8 + (ord(letter) - ord("A") + 1)


STRATEGIES: dict[str, Callable[[str], int]] = {
    "row_major_12": row_major_12,
    "column_major_8": column_major_8,
}

DEFAULT_STRATEGY = "row_major_12"


def get_strategy(name: str | None = None) -> Callable[[str], int]:
    key = name or DEFAULT_STRATEGY
    try:
        return STRATEGIES[key]
    except KeyError:
        raise PositionError(
            f"Unknown position strategy {key!r}. Available: "
            f"{', '.join(sorted(STRATEGIES))}"
        ) from None
