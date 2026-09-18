
from __future__ import annotations
from unittest.mock import patch
import app as app_module


def test_match_endpoint_filters_dead_links(tmp_path):
    app_module.DB_PATH = tmp_path / "t.db"
    app_module.store = app_module.Store(app_module.DB_PATH)
    app_module.app.config.update(TESTING=True)
    client = app_module.app.test_client()
    jobs = [
        {"id": "1", "position": "Python Engineer", "company": "X", "location": "Remote", "tags": ["python"], "description": "python flask sql", "apply_url": "https://example.com/dead"},
        {"id": "2", "position": "Python Analyst", "company": "Y", "location": "Remote", "tags": ["python", "sql"], "description": "python sql pandas remote junior", "apply_url": "https://example.com/live"},
    ]
    with patch("app.fetch_jobs", return_value=jobs), patch("app.apply_url_is_alive", side_effect=lambda u, session=None: u.endswith("/live")):
        res = client.post("/api/match", data={"cv_text": "Python SQL Flask pandas data analyst remote junior " + ("exp " * 20)})
    body = res.get_json()
    assert res.status_code == 200
    assert len(body["matches"]) == 1
    assert body["matches"][0]["apply_url"] == "https://example.com/live"


def test_match_reports_zero_when_empty(tmp_path):
    app_module.DB_PATH = tmp_path / "t.db"
    app_module.store = app_module.Store(app_module.DB_PATH)
    app_module.app.config.update(TESTING=True)
    client = app_module.app.test_client()
    with patch("app.fetch_jobs", return_value=[]), patch("app.apply_url_is_alive", return_value=True):
        res = client.post("/api/match", data={"cv_text": "Python SQL Flask pandas automation " + ("detalle " * 20)})
    body = res.get_json()
    assert body["message"] == "0 matches encontrados"
    assert body["matches"] == []
