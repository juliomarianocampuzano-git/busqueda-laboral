"""RemoteOK public API client."""
from __future__ import annotations
from typing import Any
import requests

REMOTEOK_API = "https://remoteok.com/api"
USER_AGENT = "ofertas-para-mi/1.0 (+https://github.com/juliomarianocampuzano-git/ofertas-para-mi)"


def fetch_jobs(session: requests.Session | None = None) -> list[dict[str, Any]]:
    sess = session or requests.Session()
    resp = sess.get(REMOTEOK_API, headers={"User-Agent": USER_AGENT}, timeout=45)
    resp.raise_for_status()
    jobs: list[dict[str, Any]] = []
    for item in resp.json():
        if not isinstance(item, dict) or not item.get("id") or not item.get("apply_url"):
            continue
        jobs.append({
            "id": item.get("id"),
            "position": item.get("position"),
            "company": item.get("company"),
            "location": item.get("location"),
            "tags": item.get("tags") or [],
            "description": item.get("description") or "",
            "apply_url": item.get("apply_url"),
            "url": item.get("url"),
            "salary_min": item.get("salary_min"),
            "salary_max": item.get("salary_max"),
            "date": item.get("date"),
        })
    return jobs


def apply_url_is_alive(apply_url: str, session: requests.Session | None = None) -> bool:
    sess = session or requests.Session()
    try:
        resp = sess.get(apply_url, headers={"User-Agent": USER_AGENT}, timeout=25, allow_redirects=True)
        return resp.status_code == 200
    except requests.RequestException:
        return False
