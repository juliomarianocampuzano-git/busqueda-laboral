import io
import json
import sqlite3
from pathlib import Path

import pytest
from pypdf import PdfWriter

from app import create_app
from cv_parser import load_cv_bytes
from remoteok_client import UpstreamError

CV = "Conocimientos de Python, SQL, Flask y pandas para analizar datos y preparar reportes."


class FakeClient:
    def get_jobs(self):
        return [
            {
                "id": "1",
                "position": "Python SQL",
                "company": "<script>ejemplo</script>",
                "tags": ["python", "sql"],
                "description": "Python SQL pandas Flask",
                "location": "Remoto",
                "apply_url": "https://example.com/empleo",
            }
        ]

    def verify_links(self, ranked, **kwargs):
        return [{**job, "link_status": "accesible"} for job in ranked]


@pytest.fixture
def application(tmp_path):
    return create_app(tmp_path / "test.db", provider=FakeClient(), test_config={"TESTING": True})


def test_results_and_cv_privacy(application):
    response = application.test_client().post("/api/match", json={"cv_text": CV})
    assert response.status_code == 200
    body = response.get_json()
    assert body["matches"][0]["why"]["shared_skills"] == ["flask", "pandas", "python", "sql"]
    with sqlite3.connect(application.config["DATABASE"]) as conn:
        assert conn.execute("SELECT cv_preview FROM searches").fetchone()[0] == ""
    assert CV.encode() not in Path(application.config["DATABASE"]).read_bytes()


@pytest.mark.parametrize("value", ["", "corto", 123, [], None, "x" * 50001])
def test_bad_text(application, value):
    assert application.test_client().post("/api/match", json={"cv_text": value}).status_code == 400


@pytest.mark.parametrize("payload", [[], 15, None, "un texto"])
def test_bad_json(application, payload):
    assert (
        application.test_client()
        .post("/api/match", data=json.dumps(payload), content_type="application/json")
        .status_code
        == 400
    )


def test_text_upload_stays_in_memory(application):
    response = application.test_client().post(
        "/api/match", data={"cv_file": (io.BytesIO(CV.encode()), "../../archivo.txt")}
    )
    assert response.status_code == 200
    assert sorted(Path(application.config["DATABASE"]).parent.iterdir()) == [
        Path(application.config["DATABASE"])
    ]


@pytest.mark.parametrize(
    "name,content",
    [
        ("cv.exe", b"bad"),
        ("cv.pdf", b"not a pdf"),
        ("cv.txt", b"\xff"),
        ("cv.txt", b"abc\x00xyz"),
        ("cv.txt", b"x" * 1048577),
    ],
)
def test_bad_files(application, name, content):
    response = application.test_client().post(
        "/api/match", data={"cv_file": (io.BytesIO(content), name)}
    )
    assert response.status_code in (400, 413)
    assert response.is_json


def test_pdf_limits():
    writer = PdfWriter()
    for _ in range(11):
        writer.add_blank_page(width=100, height=100)
    out = io.BytesIO()
    writer.write(out)
    with pytest.raises(ValueError, match="10 páginas"):
        load_cv_bytes(out.getvalue(), ".pdf")
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.encrypt("clave")
    out = io.BytesIO()
    writer.write(out)
    with pytest.raises(ValueError, match="contraseña"):
        load_cv_bytes(out.getvalue(), ".pdf")


def test_provider_error(tmp_path):
    class Offline(FakeClient):
        def get_jobs(self):
            raise UpstreamError("No se pudo consultar RemoteOK.")

    response = (
        create_app(tmp_path / "t.db", provider=Offline())
        .test_client()
        .post("/api/match", json={"cv_text": CV})
    )
    assert response.status_code == 503
    assert "RemoteOK" in response.get_json()["error"]


def test_demo(tmp_path):
    app = create_app(tmp_path / "demo.db", test_config={"DEMO": True})
    body = app.test_client().post("/api/match", json={"cv_text": CV}).get_json()
    assert body["demo"] is True and body["matches"]
    assert all(job["link_status"] == "ejemplo" for job in body["matches"])
    assert b"B\xc3\xbasqueda laboral" in app.test_client().get("/").data


def test_clear_previews_and_isolation(tmp_path):
    first = create_app(tmp_path / "first.db", provider=FakeClient())
    second = create_app(tmp_path / "second.db", provider=FakeClient())
    first.test_client().post("/api/match", json={"cv_text": CV})
    with sqlite3.connect(first.config["DATABASE"]) as conn:
        conn.execute("UPDATE searches SET cv_preview='texto anterior'")
    assert first.test_cli_runner().invoke(args=["borrar-textos-cv"]).exit_code == 0
    with sqlite3.connect(first.config["DATABASE"]) as conn:
        assert conn.execute("SELECT cv_preview FROM searches").fetchone()[0] == ""
    with sqlite3.connect(second.config["DATABASE"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM searches").fetchone()[0] == 0
