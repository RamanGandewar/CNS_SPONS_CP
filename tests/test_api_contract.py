from pathlib import Path

from app import app
from services.validator import VideoValidator


def auth_headers(client, email="contract@example.com"):
    signup_response = client.post(
        "/api/auth/signup",
        json={"name": "Contract User", "email": email, "password": "password123"},
    )
    assert signup_response.status_code in (201, 409)

    login_response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "password123"},
    )
    assert login_response.status_code == 200
    payload = login_response.get_json()
    token = payload["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health_contract():
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["version"]
    assert payload["db"]["ok"] is True
    assert "uptime_seconds" in payload
    assert "models_loaded" in payload


def test_model_info_contract():
    client = app.test_client()
    response = client.get("/api/v1/model/info")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert "request_id" in payload
    assert payload["data"]["models"]
    assert payload["data"]["models"][0]["artifact"].endswith(".tflite")
    assert "calibration" in payload["data"]


def test_protected_async_analysis_requires_auth():
    client = app.test_client()
    response = client.post("/api/v1/analyze", data={})

    assert response.status_code == 401
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "request_id" in payload


def test_auth_me_contract():
    client = app.test_client()
    headers = auth_headers(client, email="me-contract@example.com")

    response = client.get("/api/auth/me", headers=headers)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["user"]["email"] == "me-contract@example.com"
    assert payload["user"]["role"] in {"analyst", "operator", "admin"}


def test_validator_rejects_non_mp4_signature(tmp_path):
    fake_video = Path(tmp_path) / "fake.mp4"
    fake_video.write_bytes(b"MZnot-a-video")

    result = VideoValidator().validate(fake_video)

    assert result.valid is False
    assert "valid MP4" in result.message
