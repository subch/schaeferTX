"""Web layer: routes, uploads, and the guards on path handling."""
import io
import time

import pytest

from batchbuilder.config import Config
from batchbuilder.webapp import create_app
from conftest import EXPECTED, FIXTURES, SAMPLE_XLS


@pytest.fixture
def app(apollo, tmp_path):
    config = Config()
    config.output_dir = str(tmp_path / "ins_files")
    application = create_app(config, apollo)
    application.config["TESTING"] = True
    yield application
    application.cleanup_uploads()


@pytest.fixture
def client(app):
    return app.test_client()


def upload(client, path=SAMPLE_XLS, name="report.xls"):
    data = {"file": (io.BytesIO(path.read_bytes()), name)}
    return client.post("/api/upload", data=data,
                       content_type="multipart/form-data")


def mbn_key(name):
    """Identify a batch file by its MBN part, ignoring the date stamp."""
    parts = name.replace(".txt", "").split("_")
    return tuple(p for p in parts if p.isdigit() and len(p) == 6)


def form(token, batch_params, **kw):
    b = batch_params
    payload = {
        "token": token, "instrument": b["instrument"],
        "rack_pos": b["rack_pos"], "plate_pos": b["plate_pos"],
        "method": b["method"], "stream": b["stream"], "mbn1": b["MBN1"],
        "mbn2": b["MBN2"], "plate_code": b["plate_code"],
    }
    payload.update(kw)
    return payload


class TestPage:
    def test_index_renders_the_form(self, client):
        r = client.get("/")
        assert r.status_code == 200
        body = r.get_data(as_text=True)
        assert "Batch Builder" in body
        assert "LC_13" in body and "TO4" in body
        assert 'name="mbn1"' in body and 'name="plate_code"' in body

    def test_static_assets_are_served(self, client):
        assert client.get("/static/app.css").status_code == 200
        assert client.get("/static/app.js").status_code == 200

    def test_health_reports_the_backend(self, client):
        # The probe runs on a background thread, so it may still be checking on
        # the first call. Poll rather than racing it.
        for _ in range(50):
            d = client.get("/api/health").get_json()
            if d["state"] != "checking":
                break
            time.sleep(0.02)
        assert d["state"] == "ok"
        assert d["ok"] is True

    def test_health_never_blocks_on_a_dead_server(self, tmp_path):
        """A health check must return at once even when Apollo is unreachable,
        or a browser polling it would tie up every worker thread."""
        import time as _time
        from batchbuilder.apollo import ApolloError

        class Hanging:
            description = "hanging server"

            def check(self):
                _time.sleep(3)
                raise ApolloError("nope")

        config = Config()
        config.output_dir = str(tmp_path / "ins_files")
        app = create_app(config, Hanging())
        c = app.test_client()
        started = _time.monotonic()
        d = c.get("/api/health").get_json()
        assert _time.monotonic() - started < 1.0
        assert d["state"] == "checking"
        assert d["ok"] is False
        app.cleanup_uploads()


class TestUpload:
    def test_upload_returns_a_plate_preview(self, client):
        d = upload(client).get_json()
        assert d["ok"] is True
        assert d["token"]
        assert d["summary"]["wells"] == 96
        assert d["preview"]["counts"]["sample"] == 82
        assert len(d["preview"]["wells"]) == 96

    def test_upload_without_a_file_is_rejected(self, client):
        r = client.post("/api/upload", data={}, content_type="multipart/form-data")
        assert r.status_code == 400
        assert "No file" in r.get_json()["error"]

    def test_unreadable_upload_is_explained(self, client, tmp_path):
        junk = tmp_path / "bad.xls"
        junk.write_text("not a workbook")
        r = upload(client, junk)
        assert r.status_code == 400
        assert "Excel 97-2003" in r.get_json()["error"]


class TestCheckAndGenerate:
    def test_check_validates_without_writing(self, client, batch_params):
        token = upload(client).get_json()["token"]
        d = client.post("/api/check", data=form(token, batch_params)).get_json()
        assert d["ok"] is True
        assert len(d["files"]) == 3
        assert "output_dir" not in d
        assert d["blocking"] == 0

    def test_generate_writes_and_offers_downloads(self, client, batch_params):
        # The web form carries no date, so file names take today's stamp rather
        # than the fixture's. Content is still the contract.
        token = upload(client).get_json()["token"]
        d = client.post("/api/generate", data=form(token, batch_params)).get_json()
        assert d["ok"] is True
        assert d["run"]
        assert len(d["files"]) == 3

        # The stamp also appears inside the files, in the OutputFile column.
        today = time.strftime("%m%d").lstrip("0").encode()
        stamp = batch_params["filedt"].encode()
        shipped = {mbn_key(p.name): p.read_bytes() for p in EXPECTED.glob("*.txt")}
        for f in d["files"]:
            r = client.get(f"/api/download/{d['run']}/{f['name']}")
            assert r.status_code == 200
            normalised = r.data.replace(b"_" + today + b"_", b"_" + stamp + b"_")
            assert normalised == shipped[mbn_key(f["name"])]

    def test_generated_zip_contains_every_file(self, client, batch_params):
        import zipfile
        token = upload(client).get_json()["token"]
        d = client.post("/api/generate", data=form(token, batch_params)).get_json()
        r = client.get(f"/api/download/{d['run']}")
        assert r.status_code == 200
        with zipfile.ZipFile(io.BytesIO(r.data)) as z:
            names = sorted(z.namelist())
        assert len(names) == 4
        assert "run_report.txt" in names
        assert sorted(mbn_key(n) for n in names if n != "run_report.txt") == \
            sorted(mbn_key(p.name) for p in EXPECTED.glob("*.txt"))

    def test_bad_form_blocks_and_writes_nothing(self, client, batch_params):
        token = upload(client).get_json()["token"]
        d = client.post("/api/generate",
                        data=form(token, batch_params, plate_code="")).get_json()
        assert d["ok"] is False
        assert "output_dir" not in d
        assert any("plate code is blank" in f["message"] for f in d["findings"])

    def test_blank_mbn2_is_treated_as_a_single_mbn_run(self, client, batch_params):
        token = upload(client).get_json()["token"]
        d = client.post("/api/check",
                        data=form(token, batch_params, mbn2="")).get_json()
        assert d["ok"] is True
        assert len(d["files"]) == 1

    def test_stale_token_is_reported_not_crashed(self, client, batch_params):
        r = client.post("/api/generate", data=form("gone.xls", batch_params))
        assert r.status_code == 400
        assert "no longer available" in r.get_json()["error"]


class TestPathGuards:
    @pytest.mark.parametrize("evil", [
        "../secret", "..%2Fsecret", "....//secret",
    ])
    def test_run_folder_traversal_is_refused(self, client, evil):
        r = client.get(f"/api/download/{evil}")
        assert r.status_code in (307, 308, 404)

    def test_file_traversal_within_a_run_is_refused(self, client, batch_params):
        token = upload(client).get_json()["token"]
        d = client.post("/api/generate", data=form(token, batch_params)).get_json()
        r = client.get(f"/api/download/{d['run']}/../run_report.txt")
        assert r.status_code in (307, 308, 404)

    def test_upload_token_traversal_is_refused(self, client, batch_params):
        r = client.post("/api/generate",
                        data=form("../../etc/passwd", batch_params))
        assert r.status_code == 400


class TestRuns:
    def test_history_lists_generated_runs(self, client, batch_params):
        token = upload(client).get_json()["token"]
        made = client.post("/api/generate", data=form(token, batch_params)).get_json()
        d = client.get("/api/runs").get_json()
        assert d["ok"] is True
        assert any(r["run"] == made["run"] for r in d["runs"])

    def test_history_is_empty_before_any_run(self, client):
        assert client.get("/api/runs").get_json()["runs"] == []


TOX6_QUAL = FIXTURES / "Destination_Plate_Barcode05_7_Tox6 Qual.xls"


def tox6_form(token, **kw):
    payload = {
        "token": token, "instrument": "LC_13", "rack_pos": "1",
        "plate_pos": "2", "method": "TO6", "stream": "1",
        "plate_code": "Barcode05", "acq_method": "TO6_Str1", "mockup": "1",
    }
    payload.update(kw)
    return payload


class TestTox6Web:
    def test_upload_reports_what_it_detected(self, client):
        d = upload(client, TOX6_QUAL, "Tox6 Qual.xls").get_json()
        assert d["ok"] is True
        assert d["detected"]["assay"] == "TO6"
        assert d["detected"]["condition"] == "Qual"
        assert d["detected"]["orientation_short"] == "1, 13, 25"
        assert "Tox6" in d["detected"]["format"]

    def test_tox4_upload_reports_the_other_orientation(self, client):
        d = upload(client).get_json()
        assert d["detected"]["assay"] == "TO4"
        assert d["detected"]["orientation_short"] == "1, 2, 3"
        assert d["detected"]["condition"] == ""

    def test_mockup_generates_without_an_mbn(self, client):
        token = upload(client, TOX6_QUAL, "Tox6 Qual.xls").get_json()["token"]
        d = client.post("/api/generate", data=tox6_form(token)).get_json()
        assert d["ok"] is True, d.get("error")
        assert len(d["files"]) == 1
        assert d["files"][0]["name"].startswith("Barcode05_Qual_")

    def test_mockup_is_labelled_unverified(self, client):
        token = upload(client, TOX6_QUAL, "Tox6 Qual.xls").get_json()["token"]
        d = client.post("/api/generate", data=tox6_form(token)).get_json()
        assert any("Not for production use" in f["message"] for f in d["findings"])

    def test_without_mockup_an_mbn_is_still_required(self, client):
        token = upload(client, TOX6_QUAL, "Tox6 Qual.xls").get_json()["token"]
        d = client.post("/api/check",
                        data=tox6_form(token, mockup="")).get_json()
        assert d["ok"] is False
        assert any("MBN1 is blank" in f["message"] for f in d["findings"])

    def test_condition_can_be_overridden(self, client):
        token = upload(client, TOX6_QUAL, "Tox6 Qual.xls").get_json()["token"]
        d = client.post("/api/check",
                        data=tox6_form(token, condition="Quant")).get_json()
        # A Qual plate has no quantitative curve, so forcing Quant must fail loudly.
        assert d["ok"] is False
        assert any("quantitative calibrator" in f["message"] for f in d["findings"])

    def test_selecting_the_wrong_method_for_the_file_is_refused(self, client):
        token = upload(client, TOX6_QUAL, "Tox6 Qual.xls").get_json()["token"]
        d = client.post("/api/check",
                        data=tox6_form(token, method="TO4")).get_json()
        assert d["ok"] is False
        assert any("does not" in f["message"] or "but this file is" in f["message"]
                   for f in d["findings"])

    def test_acq_method_dropdown_is_rendered(self, client):
        body = client.get("/").get_data(as_text=True)
        assert 'name="acq_method"' in body
        assert "TO6_Str1" in body and "TO6_Str2" in body

    def test_condition_and_mockup_controls_are_rendered(self, client):
        body = client.get("/").get_data(as_text=True)
        assert 'name="condition"' in body
        assert 'name="mockup"' in body
        for c in ("Combo", "Quant", "Qual"):
            assert f">{c}<" in body

    def test_static_assets_are_version_stamped(self, client):
        body = client.get("/").get_data(as_text=True)
        assert "app.js?v=" in body and "app.css?v=" in body


class TestApolloDown:
    """When the lab network is unreachable the application must stay usable and
    must never leave a request hanging on a connect that cannot succeed."""

    @pytest.fixture
    def down_app(self, tmp_path):
        from batchbuilder.apollo import ApolloError

        class Down:
            description = "unreachable server"

            def check(self):
                raise ApolloError("Could not connect to Apollo (test).")

            def mbn_exists(self, mbn):
                raise AssertionError("must not be queried while known down")

            def pbi_samples(self, mbn):
                raise AssertionError("must not be queried while known down")

            def qc_records(self, mbn):
                raise AssertionError("must not be queried while known down")

        config = Config()
        config.output_dir = str(tmp_path / "ins_files")
        app = create_app(config, Down())
        app.config["TESTING"] = True
        yield app
        app.cleanup_uploads()

    @staticmethod
    def _settle(client):
        for _ in range(50):
            d = client.get("/api/health").get_json()
            if d["state"] != "checking":
                return d
            time.sleep(0.02)
        return d

    def test_page_still_loads(self, down_app):
        assert down_app.test_client().get("/").status_code == 200

    def test_plate_can_still_be_inspected(self, down_app):
        c = down_app.test_client()
        d = upload(c, TOX6_QUAL, "Tox6 Qual.xls").get_json()
        assert d["ok"] is True
        assert d["detected"]["condition"] == "Qual"
        assert len(d["preview"]["wells"]) == 96

    def test_health_reports_the_failure(self, down_app):
        d = self._settle(down_app.test_client())
        assert d["state"] == "error"
        assert "Could not connect" in d["error"]

    def test_mbn_run_fails_fast_without_querying(self, down_app, batch_params):
        c = down_app.test_client()
        self._settle(c)
        token = upload(c).get_json()["token"]
        started = time.monotonic()
        r = c.post("/api/check", data=form(token, batch_params))
        # The stub raises if queried at all; reaching here means it was skipped.
        assert r.status_code == 503
        assert time.monotonic() - started < 1.0
        body = r.get_json()
        assert body["apollo_down"] is True
        assert "not reachable" in body["error"]

    def test_mockup_still_generates(self, down_app):
        c = down_app.test_client()
        self._settle(c)
        token = upload(c, TOX6_QUAL, "Tox6 Qual.xls").get_json()["token"]
        d = c.post("/api/generate", data=tox6_form(token)).get_json()
        assert d["ok"] is True
        assert len(d["files"]) == 1

    def test_recheck_endpoint_exists(self, down_app):
        d = down_app.test_client().post("/api/health/recheck").get_json()
        assert d["state"] in ("checking", "error", "ok")
