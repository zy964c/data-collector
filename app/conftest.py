import pytest


@pytest.fixture(autouse=True)
def mock_envs(monkeypatch):
    monkeypatch.setenv("token_timeout", "1800")
    monkeypatch.setenv("login", "admin")
    monkeypatch.setenv("password", "x9bZPj1wV%")
    monkeypatch.setenv("camera_guard_base", "http://127.0.0.1:8080")
    monkeypatch.setenv("s3_user", "cameradog")
    monkeypatch.setenv("s3_password", "FGBICS8C@s")
    monkeypatch.setenv("S3_ENDPOINT", "http://10.10.77.29:9000")
    monkeypatch.setenv("youtube_delay", "2")
    monkeypatch.setenv("proxy", "10.10.256.4")
    monkeypatch.setenv("task_queue_size", "5")
    monkeypatch.setenv("retries_number", "5")
    monkeypatch.setenv("retries_period", "1")
    monkeypatch.setenv("DEBUG", "0")
    monkeypatch.setenv("sensor_timeout", "2")
    monkeypatch.setenv("image_api_url", "http://127.0.0.1:8080/")
    monkeypatch.setenv("s3_bucket", "bucket")
    monkeypatch.setenv('http_client_retries_number', "1")
    monkeypatch.setenv('wectech_delay', "0")
    monkeypatch.setenv('td_delay', "0")
