from pathlib import Path

from app import app
from services.validator import VideoValidator


def test_health_contract():
    client = app.test_client()
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["model_loaded"] is True
    assert "uptime_seconds" in payload


def test_model_info_contract():
    client = app.test_client()
    response = client.get("/api/v1/model/info")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["data"]["artifact"].endswith(".tflite")


def test_protected_async_analysis_requires_auth():
    client = app.test_client()
    response = client.post("/api/v1/analyze", data={})

    assert response.status_code == 401
    payload = response.get_json()
    assert payload["status"] == "error"
    assert "request_id" in payload


def test_validator_rejects_non_mp4_signature(tmp_path):
    fake_video = Path(tmp_path) / "fake.mp4"
    fake_video.write_bytes(b"MZnot-a-video")

    result = VideoValidator().validate(fake_video)

    assert result.valid is False
    assert "valid MP4" in result.message
