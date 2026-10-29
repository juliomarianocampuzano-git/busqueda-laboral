"""Consultar RemoteOK con caché y límites de espera."""

from __future__ import annotations

import ipaddress
import json
import time
from concurrent.futures import ThreadPoolExecutor, wait
from threading import Lock
from urllib.parse import urlsplit

import requests

REMOTEOK_API = "https://remoteok.com/api"
USER_AGENT = "busqueda-laboral/1.0 (+https://github.com/juliomarianocampuzano-git/busqueda-laboral)"


class UpstreamError(RuntimeError):
    pass


def public_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        host = (url.hostname or "").lower()
        if (
            url.scheme != "https"
            or not host
            or url.username
            or url.password
            or url.port not in (None, 443)
        ):
            return False
        if host == "localhost" or host.endswith((".localhost", ".local")) or "." not in host:
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            return True
    except ValueError:
        return False


def fetch_jobs(session=None) -> list[dict]:
    owner = session is None
    sess = session or requests.Session()
    deadline = time.monotonic() + 8
    try:
        with sess.get(
            REMOTEOK_API,
            headers={"User-Agent": USER_AGENT},
            timeout=(2, 4),
            stream=True,
        ) as response:
            response.raise_for_status()
            chunks = []
            size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 4 * 1024 * 1024 or time.monotonic() > deadline:
                    raise UpstreamError(
                        "La consulta de ofertas superó el límite de espera o tamaño."
                    )
                chunks.append(chunk)
        payload = json.loads(b"".join(chunks))
        if not isinstance(payload, list):
            raise ValueError("Respuesta inesperada")
        jobs = []
        seen = set()
        for item in payload:
            if (
                not isinstance(item, dict)
                or not item.get("id")
                or not public_url(item.get("apply_url"))
            ):
                continue
            identity = str(item["id"])
            if identity in seen:
                continue
            seen.add(identity)
            tags = item.get("tags") or []
            jobs.append(
                {
                    "id": identity,
                    "position": str(item.get("position") or "")[:300],
                    "company": str(item.get("company") or "")[:200],
                    "location": str(item.get("location") or "")[:300],
                    "tags": [str(tag)[:80] for tag in tags[:30]] if isinstance(tags, list) else [],
                    "description": str(item.get("description") or "")[:20000],
                    "apply_url": item["apply_url"],
                    "salary_min": item.get("salary_min")
                    if isinstance(item.get("salary_min"), (int, float))
                    else None,
                    "salary_max": item.get("salary_max")
                    if isinstance(item.get("salary_max"), (int, float))
                    else None,
                }
            )
        return jobs[:2000]
    except (requests.RequestException, ValueError, OSError) as exc:
        raise UpstreamError(
            "No se pudieron consultar las ofertas de RemoteOK. Probá de nuevo más tarde."
        ) from exc
    finally:
        if owner:
            sess.close()


def check_link(url: str, session=None) -> str:
    if not public_url(url):
        return "no disponible"
    owner = session is None
    sess = session or requests.Session()
    try:
        with sess.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=(1.5, 2),
            stream=True,
            allow_redirects=False,
        ) as response:
            if response.status_code == 200:
                return "accesible"
            if response.status_code in (404, 410):
                return "no disponible"
            return "sin verificar"
    except requests.RequestException:
        return "sin verificar"
    finally:
        if owner:
            sess.close()


def apply_url_is_alive(url: str, session=None) -> bool:
    return check_link(url, session) == "accesible"


class RemoteOKClient:
    def __init__(self, fetcher=None, checker=None, clock=None):
        self.fetcher = fetcher or fetch_jobs
        self.checker = checker or check_link
        self.clock = clock or time.monotonic
        self.jobs = None
        self.expires = 0
        self.links = {}
        self.lock = Lock()

    def get_jobs(self):
        with self.lock:
            if self.jobs is None or self.clock() >= self.expires:
                self.jobs = self.fetcher()
                self.expires = self.clock() + 300
            return list(self.jobs)

    def verify_links(self, ranked, limit=10, budget=8):
        candidates = ranked[:20]
        states = {}
        pending = []
        with self.lock:
            now = self.clock()
            for job in candidates:
                cached = self.links.get(job["apply_url"])
                if cached and cached[0] > now:
                    states[job["apply_url"]] = cached[1]
                else:
                    pending.append(job)
        executor = ThreadPoolExecutor(max_workers=4)
        futures = {
            executor.submit(self.checker, job["apply_url"]): job["apply_url"] for job in pending
        }
        try:
            done, _ = wait(futures, timeout=budget)
            for future in done:
                url = futures[future]
                try:
                    status = future.result()
                except Exception:
                    status = "sin verificar"
                states[url] = status
                with self.lock:
                    self.links[url] = (self.clock() + 600, status)
                    if len(self.links) > 2000:
                        self.links = {
                            key: val for key, val in self.links.items() if val[0] > self.clock()
                        }
                        if len(self.links) > 2000:
                            self.links.clear()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        return [
            {**job, "link_status": states.get(job["apply_url"], "sin verificar")}
            for job in candidates
            if states.get(job["apply_url"]) != "no disponible"
        ][:limit]
