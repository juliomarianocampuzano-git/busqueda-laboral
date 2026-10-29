"""Búsqueda laboral: comparar un CV con avisos de RemoteOK."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import click
from flask import Flask, current_app, jsonify, render_template, request

from cv_parser import MAX_BYTES, MAX_TEXT, load_cv_bytes
from db import Store
from matcher import score_jobs
from remoteok_client import RemoteOKClient, UpstreamError

ROOT = Path(__file__).resolve().parent


class DemoClient:
    def get_jobs(self):
        return json.loads((ROOT / "samples" / "ofertas.json").read_text(encoding="utf-8"))

    def verify_links(self, ranked, limit=10, budget=8):
        return [{**job, "link_status": "ejemplo"} for job in ranked[:limit]]


def create_app(db_path=None, provider=None, test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE=str(
            db_path or os.environ.get("BUSQUEDA_DATABASE") or ROOT / "data" / "busqueda.db"
        ),
        MAX_CONTENT_LENGTH=MAX_BYTES + 65536,
        DEMO=False,
    )
    if test_config:
        app.config.update(test_config)
    app.extensions["store"] = Store(Path(app.config["DATABASE"]))
    app.extensions["provider"] = provider or (
        DemoClient() if app.config["DEMO"] else RemoteOKClient()
    )

    @app.after_request
    def headers(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(413)
    def too_large(_):
        return jsonify(error="El archivo no puede superar 1 MB."), 413

    @app.get("/")
    def index():
        return render_template("index.html", demo=app.config["DEMO"])

    @app.post("/api/match")
    def match():
        try:
            upload = request.files.get("cv_file")
            if upload and upload.filename:
                cv_text = load_cv_bytes(
                    upload.stream.read(MAX_BYTES + 1), Path(upload.filename).suffix
                )
            else:
                data = request.get_json(silent=True) if request.is_json else request.form
                if not isinstance(data, dict) and not hasattr(data, "get"):
                    raise ValueError("Enviá el texto del CV o un archivo PDF/TXT.")
                cv_text = (data or {}).get("cv_text", "")
            if not isinstance(cv_text, str):
                raise ValueError("El CV tiene que ser texto.")
            cv_text = cv_text.strip()
            if not 40 <= len(cv_text) <= MAX_TEXT:
                raise ValueError("El CV debe tener entre 40 y 50.000 caracteres.")
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        try:
            client = current_app.extensions["provider"]
            jobs = client.get_jobs()
            ranked = score_jobs(cv_text, jobs, top_k=20)
            results = client.verify_links(ranked)
        except UpstreamError as exc:
            return jsonify(error=str(exc)), 503
        safe = [
            {
                key: job.get(key)
                for key in (
                    "id",
                    "position",
                    "company",
                    "location",
                    "tags",
                    "apply_url",
                    "affinity",
                    "why",
                    "link_status",
                )
            }
            for job in results
        ]
        sid = current_app.extensions["store"].save_search(safe)
        return jsonify(
            source="Datos ficticios" if app.config["DEMO"] else "RemoteOK",
            demo=app.config["DEMO"],
            search_id=sid,
            matches=safe,
            message=f"{len(safe)} avisos encontrados",
        )

    @app.cli.command("borrar-textos-cv")
    def clear_previews():
        """Borrar fragmentos de CV guardados por la versión anterior."""
        total = current_app.extensions["store"].clear_cv_previews()
        click.echo(f"Se borraron {total} fragmentos de CV de búsquedas anteriores.")

    return app


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Búsqueda laboral")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="probar con ofertas ficticias y sin consultas externas",
    )
    args = parser.parse_args()
    create_app(test_config={"DEMO": args.demo}).run(host="127.0.0.1", port=5055, debug=False)
