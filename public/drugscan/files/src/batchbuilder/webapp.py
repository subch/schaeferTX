"""The local web interface.

Bound to the loopback address only. Nothing here is exposed to the network: the
analyst runs the executable on their own workstation and the browser talks to
127.0.0.1.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from flask import (
    Flask, jsonify, render_template, request as flask_request, send_file,
)

from . import APP_NAME, __version__, service
from .apollo import ApolloClient, ApolloError, HealthProbe
from .config import Config, resolve_output_dir
from .controls import Condition
from .generator import SINGLE_MBN, BatchRequest
from .hamilton import HamiltonError
from .models import Severity

MAX_UPLOAD_BYTES = 32 * 1024 * 1024


def _findings_payload(findings) -> list[dict]:
    return [{"severity": f.severity.value, "message": f.message,
             "subject": f.subject} for f in findings]


def _condition_from_form(form) -> Condition:
    """Blank means trust the plate; anything else is an explicit override."""
    raw = (form.get("condition") or "").strip()
    for candidate in Condition:
        if candidate.value.casefold() == raw.casefold():
            return candidate
    return Condition.NOT_APPLICABLE


def _request_from_form(form, config: Config) -> BatchRequest:
    mbn2 = (form.get("mbn2") or "").strip().upper().replace(" ", "")
    acq = (form.get("acq_method") or "").strip()
    return BatchRequest(
        acq_method_override=acq or None,
        condition=_condition_from_form(form),
        mockup=(form.get("mockup") or "").strip().lower() in ("1", "true", "on", "yes"),
        instrument=(form.get("instrument") or "").strip(),
        rack_pos=(form.get("rack_pos") or "").strip(),
        plate_pos=(form.get("plate_pos") or "").strip(),
        method=(form.get("method") or "").strip(),
        stream=(form.get("stream") or "").strip(),
        mbn1=(form.get("mbn1") or "").strip().replace(" ", ""),
        mbn2=mbn2 or SINGLE_MBN,
        plate_code=(form.get("plate_code") or "").strip().replace(" ", ""),
        settings=config.settings_for((form.get("method") or "").strip()),
    )


def create_app(config: Config, apollo: ApolloClient,
               health: HealthProbe | None = None) -> Flask:
    app = Flask(__name__)
    # Apollo is probed off the request thread; a health check must never be
    # able to block a worker, let alone all of them.
    probe = health if health is not None else HealthProbe(apollo)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    uploads = Path(tempfile.mkdtemp(prefix="batchbuilder_uploads_"))
    app.config["UPLOAD_DIR"] = uploads

    def stored_path(token: str) -> Path:
        """Resolve an upload token, refusing anything that escapes the folder."""
        candidate = (uploads / token).resolve()
        if candidate.parent != uploads.resolve() or not candidate.is_file():
            raise FileNotFoundError(token)
        return candidate

    @app.get("/")
    def index():
        output_root, note = resolve_output_dir(
            Path(config.output_dir) if config.output_dir else None)
        return render_template(
            "index.html",
            app_name=APP_NAME,
            version=__version__,
            form=asdict(config.form),
            conditions=[c.value for c in Condition
                        if c is not Condition.NOT_APPLICABLE],
            single_mbn=SINGLE_MBN,
            apollo=getattr(apollo, "description", "Apollo"),
            output_dir=str(output_root),
            output_note=note,
            config_note=config.load_error,
            config_path=str(config.source_path) if config.source_path else "",
        )

    @app.post("/api/upload")
    def upload():
        """Store the report and describe the plate, without touching Apollo."""
        uploaded = flask_request.files.get("file")
        if uploaded is None or not uploaded.filename:
            return jsonify({"ok": False, "error": "No file was selected."}), 400

        token = f"{uuid4().hex}.xls"
        target = uploads / token
        uploaded.save(target)

        try:
            plate, findings, preview = service.inspect(str(target), config)
        except HamiltonError as exc:
            target.unlink(missing_ok=True)
            return jsonify({"ok": False, "error": str(exc)}), 400

        return jsonify({
            "ok": True,
            "token": token,
            "filename": uploaded.filename,
            "findings": _findings_payload(findings),
            "preview": asdict(preview),
            "detected": {
                "assay": plate.assay,
                "format": plate.format_name,
                "orientation": plate.orientation.value,
                "orientation_label": plate.orientation.label,
                "orientation_short": plate.orientation.short,
                "condition": plate.condition.value if plate.assay == "TO6" else "",
                "condition_label": plate.condition.label if plate.assay == "TO6" else "",
            },
            # Counts come from the same preview the plate map draws, so the
            # summary line and the map can never disagree.
            "summary": {
                "wells": len(plate.wells),
                "dropped": len(plate.dropped),
            },
        })

    @app.post("/api/check")
    def check():
        """Full validation and a dry-run build. Writes nothing."""
        return _run(write=False)

    @app.post("/api/generate")
    def generate():
        return _run(write=True)

    def _run(write: bool):
        form = flask_request.form
        token = (form.get("token") or "").strip()
        label = (form.get("filename") or "").strip() or None
        try:
            path = stored_path(token)
        except FileNotFoundError:
            return jsonify({
                "ok": False,
                "error": "The uploaded report is no longer available. "
                         "Please choose the file again.",
            }), 400

        batch = _request_from_form(form, config)

        # Every path below this point that touches Apollo would otherwise block
        # the worker for as long as the driver takes to give up. If the probe
        # already knows the server is unreachable, say so at once.
        state = probe.snapshot()
        if not batch.mockup and state["state"] == "error":
            return jsonify({
                "ok": False,
                "error": "Apollo is not reachable, so this batch cannot be "
                         "validated. " + (state["error"] or ""),
                "findings": [],
                "apollo_down": True,
            }), 503

        try:
            result = service.run(batch, str(path), apollo, config,
                                 write=write, source_label=label)
        except ApolloError as exc:
            return jsonify({"ok": False, "error": str(exc),
                            "findings": []}), 502
        except OSError as exc:
            return jsonify({"ok": False, "error": str(exc),
                            "findings": []}), 500

        payload = {
            "ok": result.ok,
            "error": result.error,
            "findings": _findings_payload(result.findings),
            "files": [{"name": f.name, "rows": len(f.rows)} for f in result.files],
            "preview": asdict(result.preview) if result.preview else None,
            "blocking": sum(1 for f in result.findings if f.blocking),
        }
        if result.output_dir:
            payload["output_dir"] = str(result.output_dir)
            payload["run"] = result.output_dir.name
            payload["report"] = result.report_text
        return jsonify(payload)

    @app.get("/api/runs")
    def runs():
        """Recent output folders, newest first, so an earlier batch can be pulled again."""
        output_root, _ = resolve_output_dir(
            Path(config.output_dir) if config.output_dir else None)
        found = []
        for folder in sorted(output_root.glob("*"), reverse=True):
            if not folder.is_dir():
                continue
            files = sorted(p.name for p in folder.glob("*.txt"))
            if not files:
                continue
            found.append({
                "run": folder.name,
                "files": files,
                "when": folder.stat().st_mtime,
            })
            if len(found) >= 25:
                break
        return jsonify({"ok": True, "runs": found, "root": str(output_root)})

    def _run_folder(run: str) -> Path:
        output_root, _ = resolve_output_dir(
            Path(config.output_dir) if config.output_dir else None)
        folder = (output_root / run).resolve()
        if folder.parent != output_root.resolve() or not folder.is_dir():
            raise FileNotFoundError(run)
        return folder

    @app.get("/api/download/<run>")
    def download_zip(run: str):
        try:
            folder = _run_folder(run)
        except FileNotFoundError:
            return jsonify({"ok": False, "error": "Unknown run."}), 404

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(folder.glob("*.txt")):
                archive.write(path, arcname=path.name)
        buffer.seek(0)
        return send_file(buffer, mimetype="application/zip",
                         as_attachment=True, download_name=f"{run}.zip")

    @app.get("/api/download/<run>/<name>")
    def download_one(run: str, name: str):
        try:
            folder = _run_folder(run)
        except FileNotFoundError:
            return jsonify({"ok": False, "error": "Unknown run."}), 404
        target = (folder / name).resolve()
        if target.parent != folder.resolve() or not target.is_file():
            return jsonify({"ok": False, "error": "Unknown file."}), 404
        return send_file(target, mimetype="text/plain",
                         as_attachment=True, download_name=name)

    @app.get("/api/health")
    def health_route():
        """Returns immediately with the last known state, never a live connect."""
        return jsonify(probe.snapshot())

    @app.post("/api/health/recheck")
    def health_recheck():
        probe.start(force=True)
        return jsonify(probe.snapshot())

    @app.errorhandler(413)
    def too_large(_):
        return jsonify({
            "ok": False,
            "error": f"That file is larger than "
                     f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        }), 413

    @app.teardown_appcontext
    def _noop(_exc):
        return None

    app.cleanup_uploads = lambda: shutil.rmtree(uploads, ignore_errors=True)
    return app
