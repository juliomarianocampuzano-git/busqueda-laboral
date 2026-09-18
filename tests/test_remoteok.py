
from __future__ import annotations
from unittest.mock import MagicMock, patch
import pytest
import requests
from matcher import score_jobs
from remoteok_client import USER_AGENT, apply_url_is_alive, fetch_jobs


def test_fetch_jobs_uses_user_agent_and_keeps_apply_url():
    fake = [{"legal": "x"}, {"id": "1", "position": "Python Developer", "company": "Acme", "location": "Remote", "tags": ["python", "sql"], "description": "Flask SQL", "apply_url": "https://example.com/apply/1", "url": "https://remoteok.com/x"}]
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = fake
    with patch("remoteok_client.requests.Session.get", return_value=mock_resp) as get:
        jobs = fetch_jobs(requests.Session())
    assert jobs[0]["apply_url"] == "https://example.com/apply/1"
    headers = get.call_args.kwargs["headers"]
    assert headers["User-Agent"] == USER_AGENT


def test_score_jobs_orders_by_affinity():
    cv = "Python Flask SQL pandas data analyst remote"
    jobs = [
        {"id": "a", "position": "Java Designer", "tags": ["java"], "description": "UI design", "apply_url": "http://x/a"},
        {"id": "b", "position": "Python Data Analyst", "tags": ["python", "sql"], "description": "pandas flask sql remote", "apply_url": "http://x/b"},
    ]
    ranked = score_jobs(cv, jobs, top_k=2)
    assert ranked[0]["id"] == "b"
    assert "python" in ranked[0]["why"]["shared_skills"]


def test_apply_url_is_alive_true_on_200():
    with patch("remoteok_client.requests.Session.get", return_value=MagicMock(status_code=200)):
        assert apply_url_is_alive("https://example.com/ok") is True


def test_apply_url_is_alive_false_on_404():
    with patch("remoteok_client.requests.Session.get", return_value=MagicMock(status_code=404)):
        assert apply_url_is_alive("https://example.com/missing") is False


@pytest.mark.integration
def test_live_remoteok_apply_url_returns_200():
    jobs = fetch_jobs()
    assert jobs
    alive = next((j for j in jobs[:20] if apply_url_is_alive(j["apply_url"])), None)
    assert alive is not None
    assert str(alive["apply_url"]).startswith("http")
