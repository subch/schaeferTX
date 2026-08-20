"""Configuration and path handling.

The application must run correctly with no config file present, so every value
has a built-in default matching the tool it replaces. A ``batchbuilder.json``
placed next to the executable overrides any subset of them, which is what lets
the lab add an instrument or a method without a rebuild.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .generator import BatchSettings
from .validation import ControlExpectations

CONFIG_NAME = "batchbuilder.json"
INPUT_DIR_NAME = "hamilton files"
OUTPUT_DIR_NAME = "ins_files"

# Credentials are read-only and scoped to the lab network. They are compiled in
# so the tool works with no config file at all; a config file may override them.
DEFAULT_APOLLO = {
    "server": r"YOUR_SQL_SERVER\INSTANCE",
    "database": "YOUR_DATABASE",
    "uid": "APOLLO_USER",
    "pwd": "APOLLO_PASSWORD",
    "driver": None,  # None = auto-detect the newest installed driver
    "timeout": 10,
}

DEFAULT_INSTRUMENTS = [
    "LC_5", "LC_7", "LC_9", "LC_12", "LC_13", "LC_15", "LC_17", "LC_18",
    "LC_19", "LC_20", "LC_21", "LC_23", "LC_24", "LC_25", "LC_27", "LC_28",
]

# TO3, TO3b and PSY were commented out of the original and are left disabled
# here. Add them to this list in batchbuilder.json to bring them back.
DEFAULT_METHODS = ["TO4", "TO6"]

# Acquisition method (.dam) names offered in the form. Tox4 derives its own from
# "<method>_Str<stream>"; the Tox6 names are owned by the instrument, so they are
# picked from this list rather than guessed. TO6_Str1/TO6_Str2 are placeholders
# pending confirmation of the real .dam names.
DEFAULT_ACQ_METHODS = ["TO6_Str1", "TO6_Str2"]

DEFAULT_RACK_POSITIONS = ["1", "2"]
DEFAULT_PLATE_POSITIONS = ["1", "2", "3"]
DEFAULT_STREAMS = ["1", "2"]


def base_dir() -> Path:
    """The folder the application was launched from.

    Under PyInstaller this is the folder holding the .exe, not the temporary
    extraction directory.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def user_data_dir() -> Path:
    """Per-user fallback for when the install folder is not writable."""
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    base = Path(root) if root else Path(tempfile.gettempdir())
    return base / "BatchBuilder"


def _is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".write_test_{os.getpid()}"
        probe.write_text("")
        probe.unlink()
        return True
    except OSError:
        return False


def resolve_output_dir(preferred: Path | None = None) -> tuple[Path, str | None]:
    """Pick a writable output folder.

    Prefers ``ins_files`` beside the executable so output keeps landing where
    the lab expects it, and falls back to the user's own profile when the
    install folder sits on a read-only share. Returns the folder and a note to
    show the analyst if the fallback was used.
    """
    candidates: list[Path] = []
    if preferred:
        candidates.append(Path(preferred))
    candidates.append(base_dir() / OUTPUT_DIR_NAME)
    fallback = user_data_dir() / OUTPUT_DIR_NAME

    for path in candidates:
        if _is_writable(path):
            return path, None

    if _is_writable(fallback):
        return fallback, (
            f"{candidates[0]} is not writable, so output is being written to "
            f"{fallback} instead."
        )
    raise OSError(
        f"No writable output folder. Tried {', '.join(str(c) for c in candidates)} "
        f"and {fallback}."
    )


@dataclass
class ApolloConfig:
    server: str = DEFAULT_APOLLO["server"]
    database: str = DEFAULT_APOLLO["database"]
    uid: str = DEFAULT_APOLLO["uid"]
    pwd: str = DEFAULT_APOLLO["pwd"]
    driver: str | None = DEFAULT_APOLLO["driver"]
    timeout: int = DEFAULT_APOLLO["timeout"]


@dataclass
class FormOptions:
    instruments: list[str] = field(default_factory=lambda: list(DEFAULT_INSTRUMENTS))
    methods: list[str] = field(default_factory=lambda: list(DEFAULT_METHODS))
    rack_positions: list[str] = field(default_factory=lambda: list(DEFAULT_RACK_POSITIONS))
    plate_positions: list[str] = field(default_factory=lambda: list(DEFAULT_PLATE_POSITIONS))
    streams: list[str] = field(default_factory=lambda: list(DEFAULT_STREAMS))
    acq_methods: list[str] = field(default_factory=lambda: list(DEFAULT_ACQ_METHODS))


@dataclass
class Config:
    apollo: ApolloConfig = field(default_factory=ApolloConfig)
    form: FormOptions = field(default_factory=FormOptions)
    settings: BatchSettings = field(default_factory=BatchSettings)
    expectations: ControlExpectations = field(default_factory=ControlExpectations)
    position_strategy: str = "row_major_12"
    #: Statuses accepted in ADDITION to the ones each input format defines
    #: ("No Error" for Tox4, "Correct pipetting" for Tox6). Additive so a
    #: local override cannot accidentally break the other format.
    extra_ok_statuses: list[str] = field(default_factory=list)
    #: Per-method overrides, e.g. {"TO3": {"expectations": {"cal_levels": 6}}}
    method_overrides: dict = field(default_factory=dict)
    output_dir: str | None = None
    input_dir: str | None = None
    port: int = 0  # 0 = pick a free port
    open_browser: bool = True

    source_path: Path | None = None
    load_error: str | None = None

    def expectations_for(self, method: str) -> ControlExpectations:
        override = (self.method_overrides.get(method) or {}).get("expectations")
        if not override:
            return self.expectations
        merged = asdict(self.expectations)
        merged.update(override)
        return ControlExpectations(**merged)

    def settings_for(self, method: str) -> BatchSettings:
        override = (self.method_overrides.get(method) or {}).get("settings")
        if not override:
            return self.settings
        merged = asdict(self.settings)
        merged.update(override)
        for key in ("alt_instruments", "alt_methods"):
            if isinstance(merged.get(key), list):
                merged[key] = tuple(merged[key])
        return BatchSettings(**merged)

    @property
    def input_path(self) -> Path:
        return Path(self.input_dir) if self.input_dir else base_dir() / INPUT_DIR_NAME


def _apply(target, values: dict) -> None:
    for key, value in values.items():
        if hasattr(target, key):
            setattr(target, key, value)


def load(path: Path | None = None) -> Config:
    """Load configuration, falling back to built-in defaults.

    A malformed config file is reported rather than fatal: the application still
    starts on defaults and shows the problem, because an analyst mid-run needs
    the tool more than they need strict config validation.
    """
    config = Config()
    target = Path(path) if path else base_dir() / CONFIG_NAME
    if not target.exists():
        return config

    config.source_path = target
    try:
        raw = json.loads(target.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        config.load_error = f"{target} could not be read ({exc}). Using defaults."
        return config

    try:
        _apply(config.apollo, raw.get("apollo", {}))
        _apply(config.form, raw.get("form", {}))
        _apply(config.settings, raw.get("settings", {}))
        _apply(config.expectations, raw.get("expectations", {}))
        for key in ("alt_instruments", "alt_methods"):
            value = getattr(config.settings, key)
            if isinstance(value, list):
                setattr(config.settings, key, tuple(value))
        for key in ("position_strategy", "extra_ok_statuses", "method_overrides",
                    "output_dir", "input_dir", "port", "open_browser"):
            if key in raw:
                setattr(config, key, raw[key])
    except (TypeError, ValueError) as exc:
        config.load_error = f"{target} contains an invalid value ({exc}). Using defaults."
        return Config(source_path=target, load_error=config.load_error)

    return config
