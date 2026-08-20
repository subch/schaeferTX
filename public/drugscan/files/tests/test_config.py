"""Configuration loading, and the example file we ship next to the executable."""
import json
from pathlib import Path

import pytest

from batchbuilder import config as config_mod
from batchbuilder.config import Config, load

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "batchbuilder.example.json"


class TestExampleConfig:
    def test_example_is_valid_json(self):
        """It is copied verbatim by anyone customising the deployment, so a
        syntax error in it becomes their problem, not ours."""
        json.loads(EXAMPLE.read_text())

    def test_example_loads_without_error(self, tmp_path):
        target = tmp_path / "batchbuilder.json"
        target.write_text(EXAMPLE.read_text())
        cfg = load(target)
        assert cfg.load_error is None, cfg.load_error

    def test_example_reproduces_the_built_in_defaults(self, tmp_path):
        """The example ships the current values, so loading it should be a
        no-op. If this fails, the example has drifted from the code."""
        target = tmp_path / "batchbuilder.json"
        target.write_text(EXAMPLE.read_text())
        loaded = load(target)
        default = Config()
        assert loaded.form.instruments == default.form.instruments
        assert loaded.form.methods == default.form.methods
        assert loaded.form.acq_methods == default.form.acq_methods
        assert loaded.apollo.server == default.apollo.server
        assert loaded.expectations == default.expectations
        assert loaded.position_strategy == default.position_strategy

    def test_example_documents_both_assays(self):
        data = json.loads(EXAMPLE.read_text())
        assert "TO4" in data["form"]["methods"]
        assert "TO6" in data["form"]["methods"]


class TestDefaults:
    def test_missing_file_is_not_an_error(self, tmp_path):
        cfg = load(tmp_path / "nope.json")
        assert cfg.load_error is None
        assert cfg.form.methods == config_mod.DEFAULT_METHODS

    def test_malformed_file_falls_back_and_reports(self, tmp_path):
        target = tmp_path / "batchbuilder.json"
        target.write_text("{ this is not json")
        cfg = load(target)
        assert cfg.load_error is not None
        assert cfg.form.instruments == config_mod.DEFAULT_INSTRUMENTS

    def test_partial_override_keeps_everything_else(self, tmp_path):
        target = tmp_path / "batchbuilder.json"
        target.write_text(json.dumps({"form": {"methods": ["TO4"]}}))
        cfg = load(target)
        assert cfg.form.methods == ["TO4"]
        assert cfg.form.instruments == config_mod.DEFAULT_INSTRUMENTS
        assert cfg.apollo.database == config_mod.DEFAULT_APOLLO["database"]

    def test_extra_ok_statuses_defaults_to_empty(self):
        assert Config().extra_ok_statuses == []

    @pytest.mark.parametrize("method", ["TO4", "TO6"])
    def test_settings_resolve_for_every_shipped_method(self, method):
        cfg = Config()
        assert cfg.settings_for(method) is not None
        assert cfg.expectations_for(method) is not None
