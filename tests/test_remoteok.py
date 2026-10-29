import json
import threading

import pytest
import requests

from matcher import extract_skills, score_jobs
from remoteok_client import RemoteOKClient, UpstreamError, check_link, fetch_jobs, public_url


class Response:
    def __init__(self, payload=None, status=200):
        self.payload, self.status_code = payload, status

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError("Error")

    def iter_content(self, _):
        yield json.dumps(self.payload).encode()


class Session:
    def __init__(self, response):
        self.response, self.calls = response, []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def test_skills():
    skills = extract_skills("Django y JavaScript. GitHub. Una página web.")
    assert {"go", "java", "git"} & skills == set()
    assert {"django", "javascript"} <= skills


def test_ranking():
    jobs = [
        {"id": "1", "position": "Python SQL", "tags": ["python"], "description": "pandas"},
        {"id": "2", "position": "Diseño", "tags": [], "description": "Ilustración"},
    ]
    result = score_jobs("Python SQL pandas", jobs)
    assert result[0]["id"] == "1"
    assert 0 < result[0]["affinity"] <= 1
    assert score_jobs("!!!", [{"id": "3", "position": "???"}]) == []


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com",
        "javascript:alert(1)",
        "https://localhost/x",
        "https://127.0.0.1/x",
        "https://10.1.1.1",
        "https://user:pass@example.com",
        "https://example.com:8080",
        None,
    ],
)
def test_urls(url):
    assert not public_url(url)


def test_fetch_and_deduplicate():
    job = {"id": 1, "position": "Python", "apply_url": "https://example.com/1", "tags": ["sql"]}
    sess = Session(Response([{"legal": "x"}, job, job, {"id": 2, "apply_url": "http://localhost"}]))
    result = fetch_jobs(sess)
    assert len(result) == 1
    assert result[0]["apply_url"] == job["apply_url"]
    assert sess.calls[0][1]["headers"]["User-Agent"].startswith("busqueda-laboral/")


@pytest.mark.parametrize(
    "status,expected",
    [
        (200, "accesible"),
        (404, "no disponible"),
        (410, "no disponible"),
        (301, "sin verificar"),
        (403, "sin verificar"),
        (429, "sin verificar"),
    ],
)
def test_link_status(status, expected):
    sess = Session(Response(status=status))
    assert check_link("https://example.com/1", sess) == expected
    assert sess.calls[0][1]["allow_redirects"] is False


def test_invalid_upstream():
    with pytest.raises(UpstreamError):
        fetch_jobs(Session(Response({"unexpected": True})))


def test_cache():
    now, fetch_calls, link_calls = [0], [], []

    def fetcher():
        fetch_calls.append(1)
        return [{"id": "1", "apply_url": "https://example.com/1"}]

    def checker(url):
        link_calls.append(url)
        return "accesible"

    client = RemoteOKClient(fetcher=fetcher, checker=checker, clock=lambda: now[0])
    for _ in range(2):
        assert client.verify_links(client.get_jobs())[0]["link_status"] == "accesible"
    assert len(fetch_calls) == len(link_calls) == 1
    now[0] = 601
    client.verify_links(client.get_jobs())
    assert len(fetch_calls) == len(link_calls) == 2


def test_wait_budget():
    release = threading.Event()

    def slow(_):
        release.wait(2)
        return "accesible"

    client = RemoteOKClient(checker=slow)
    try:
        result = client.verify_links([{"id": "1", "apply_url": "https://example.com/1"}], budget=0)
        assert result[0]["link_status"] == "sin verificar"
    finally:
        release.set()


@pytest.mark.integration
def test_live_source():
    assert isinstance(fetch_jobs(), list)
