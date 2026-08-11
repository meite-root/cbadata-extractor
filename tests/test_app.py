from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_home_and_health():
    assert client.get("/").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}


def test_process_validation_and_response():
    response = client.post("/api/process", json={"text": "Employees shall receive paid leave.", "step": 11})
    assert response.status_code == 200
    assert "measures" in response.json()
    assert client.post("/api/process", json={"text": "", "step": 2}).status_code == 422

