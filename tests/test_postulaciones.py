import csv
import io

import pytest

from app import create_app

AVISO = {
    "position": "Analista de datos",
    "company": "Empresa de ejemplo",
    "apply_url": "https://example.com/empleo-1",
}


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "test.db", test_config={"TESTING": True, "DEMO": True})
    return app.test_client()


def test_save_list_and_no_duplicates(client):
    first = client.post("/api/postulaciones", json=AVISO)
    assert first.status_code == 201 and first.get_json()["created"] is True
    again = client.post("/api/postulaciones", json=AVISO)
    assert again.status_code == 200 and again.get_json()["created"] is False
    body = client.get("/api/postulaciones").get_json()
    assert len(body["items"]) == 1
    assert body["items"][0]["status"] == "guardada"
    assert body["counts"] == {
        "guardada": 1,
        "postulada": 0,
        "entrevista": 0,
        "oferta": 0,
        "descartada": 0,
    }


def test_offer_without_link_can_be_saved_twice(client):
    sin_link = {**AVISO, "apply_url": ""}
    assert client.post("/api/postulaciones", json=sin_link).status_code == 201
    assert client.post("/api/postulaciones", json=sin_link).status_code == 201


def test_update_status_and_notes(client):
    app_id = client.post("/api/postulaciones", json=AVISO).get_json()["item"]["id"]
    res = client.patch(
        f"/api/postulaciones/{app_id}", json={"status": "entrevista", "notes": "  Martes 10 h  "}
    )
    assert res.status_code == 200
    item = res.get_json()["item"]
    assert item["status"] == "entrevista" and item["notes"] == "Martes 10 h"
    counts = client.get("/api/postulaciones").get_json()["counts"]
    assert counts["entrevista"] == 1 and counts["guardada"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "contratada"},
        {"notes": "x" * 1001},
        {"notes": 5},
        {},
    ],
)
def test_bad_updates(client, payload):
    app_id = client.post("/api/postulaciones", json=AVISO).get_json()["item"]["id"]
    assert client.patch(f"/api/postulaciones/{app_id}", json=payload).status_code == 400


@pytest.mark.parametrize(
    "payload",
    [
        {**AVISO, "position": ""},
        {**AVISO, "position": "x" * 201},
        {**AVISO, "apply_url": "javascript:alert(1)"},
        {**AVISO, "apply_url": "http://example.com/empleo"},
        {**AVISO, "apply_url": "https://usuario:clave@example.com/"},
        {**AVISO, "company": ["no", "texto"]},
    ],
)
def test_bad_new_applications(client, payload):
    assert client.post("/api/postulaciones", json=payload).status_code == 400


def test_requires_json(client):
    res = client.post("/api/postulaciones", data=AVISO)
    assert res.status_code == 400
    assert client.get("/api/postulaciones").get_json()["items"] == []


def test_missing_ids_return_404(client):
    assert client.patch("/api/postulaciones/99", json={"status": "oferta"}).status_code == 404
    assert client.delete("/api/postulaciones/99").status_code == 404


def test_delete(client):
    app_id = client.post("/api/postulaciones", json=AVISO).get_json()["item"]["id"]
    assert client.delete(f"/api/postulaciones/{app_id}").status_code == 200
    assert client.get("/api/postulaciones").get_json()["items"] == []


def test_csv_export_is_spreadsheet_safe(client):
    client.post("/api/postulaciones", json={**AVISO, "company": "=HYPERLINK(1)"})
    res = client.get("/api/postulaciones.csv")
    assert res.status_code == 200
    assert res.headers["Content-Disposition"].endswith('filename="postulaciones.csv"')
    text = res.data.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == ["puesto", "empresa", "estado", "notas", "enlace", "actualizada"]
    assert rows[1][1] == "'=HYPERLINK(1)"
    assert rows[1][2] == "guardada"


def test_page_has_applications_section(client):
    assert "Mis postulaciones" in client.get("/").get_data(as_text=True)
