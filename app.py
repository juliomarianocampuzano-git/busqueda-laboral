"""Ofertas para mi CV — RemoteOK matcher."""
from __future__ import annotations
from pathlib import Path
from flask import Flask, jsonify, render_template, request
from cv_parser import load_cv_text
from db import Store
from matcher import score_jobs
from remoteok_client import apply_url_is_alive, fetch_jobs

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "ofertas.db"
app = Flask(__name__)
store = Store(DB_PATH)


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/match")
def match():
    cv_text = ""
    if "cv_file" in request.files and request.files["cv_file"].filename:
        f = request.files["cv_file"]
        tmp = ROOT / "data" / f"upload_{Path(f.filename).name}"
        f.save(tmp)
        try:
            cv_text = load_cv_text(tmp)
        finally:
            tmp.unlink(missing_ok=True)
    else:
        data = request.get_json(silent=True) or {}
        cv_text = request.form.get("cv_text") or data.get("cv_text") or ""
    cv_text = (cv_text or "").strip()
    if len(cv_text) < 40:
        return jsonify({"error": "CV demasiado corto", "matches": [], "message": "0 matches encontrados"}), 400

    jobs = fetch_jobs()
    ranked = score_jobs(cv_text, jobs, top_k=40)
    verified = []
    for job in ranked:
        url = job.get("apply_url")
        if url and apply_url_is_alive(url):
            verified.append(job)
        if len(verified) >= 10:
            break

    if not verified:
        store.save_search(cv_text, [])
        return jsonify({
            "source": "RemoteOK API (https://remoteok.com/api)",
            "matches": [],
            "message": "0 matches encontrados",
        })

    sid = store.save_search(cv_text, verified)
    safe = [{
        "id": m.get("id"),
        "position": m.get("position"),
        "company": m.get("company"),
        "location": m.get("location"),
        "tags": m.get("tags"),
        "apply_url": m.get("apply_url"),
        "salary_min": m.get("salary_min"),
        "salary_max": m.get("salary_max"),
        "affinity": m.get("affinity"),
        "why": m.get("why"),
    } for m in verified]
    return jsonify({
        "source": "RemoteOK API (https://remoteok.com/api)",
        "search_id": sid,
        "matches": safe,
        "message": f"{len(safe)} matches encontrados",
    })


if __name__ == "__main__":
    app.run(debug=True, port=5055)
