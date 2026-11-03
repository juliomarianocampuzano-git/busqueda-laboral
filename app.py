"""Búsqueda laboral: comparar un CV con avisos de RemoteOK."""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import click
from flask import Flask, Response, current_app, jsonify, render_template, request

from cv_parser import MAX_BYTES, MAX_TEXT, load_cv_bytes
from db import Store
from matcher import score_jobs
from remoteok_client import RemoteOKClient, UpstreamError

ROOT = Path(__file__).resolve().parent
STATUSES = ("guardada", "postulada", "entrevista", "oferta", "descartada")


def text_field(data: dict, key: str, limit: int, *, required: bool = False) -> str:
    value = data.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"El campo {key} tiene que ser texto.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"Falta el campo {key}.")
    if len(value) > limit:
        raise ValueError(f"El campo {key} admite hasta {limit} caracteres.")
    return value


def clean_url(value: str) -> str:
    """Solo enlaces https sin usuario ni contraseña; vacío si el aviso no tiene enlace."""
    if not value:
        return ""
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("El enlace del aviso tiene que empezar con https://.")
    return value


def csv_text(value: str) -> str:
    # Evita que una planilla interprete el texto como fórmula.
    if value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def json_body() -> dict:
    if not request.is_json:
        raise ValueError("Enviá los datos como JSON.")
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Enviá un objeto JSON válido.")
    return data


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

    # ---------- postulaciones ----------
    def summary(items):
        return {status: sum(item["status"] == status for item in items) for status in STATUSES}

    @app.get("/api/postulaciones")
    def list_applications():
        items = current_app.extensions["store"].list_applications()
        return jsonify(items=items, counts=summary(items), statuses=list(STATUSES))

    @app.post("/api/postulaciones")
    def add_application():
        try:
            data = json_body()
            position = text_field(data, "position", 200, required=True)
            company = text_field(data, "company", 200)
            url = clean_url(text_field(data, "apply_url", 2000))
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        item, created = current_app.extensions["store"].add_application(position, company, url)
        return jsonify(item=item, created=created), 201 if created else 200

    @app.patch("/api/postulaciones/<int:app_id>")
    def update_application(app_id: int):
        try:
            data = json_body()
            changes = {}
            if "status" in data:
                if data["status"] not in STATUSES:
                    raise ValueError("Elegí un estado válido.")
                changes["status"] = data["status"]
            if "notes" in data:
                changes["notes"] = text_field(data, "notes", 1000)
            if not changes:
                raise ValueError("No hay cambios para guardar.")
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        item = current_app.extensions["store"].update_application(app_id, changes)
        if item is None:
            return jsonify(error="La postulación no existe."), 404
        return jsonify(item=item)

    @app.delete("/api/postulaciones/<int:app_id>")
    def delete_application(app_id: int):
        if not current_app.extensions["store"].delete_application(app_id):
            return jsonify(error="La postulación no existe."), 404
        return jsonify(ok=True)

    @app.get("/api/postulaciones.csv")
    def export_applications():
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["puesto", "empresa", "estado", "notas", "enlace", "actualizada"])
        for item in current_app.extensions["store"].list_applications():
            writer.writerow(
                [
                    csv_text(item["position"]),
                    csv_text(item["company"]),
                    item["status"],
                    csv_text(item["notes"]),
                    item["apply_url"],
                    item["updated_at"],
                ]
            )
        return Response(
            "﻿" + output.getvalue(),
            content_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="postulaciones.csv"'},
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
