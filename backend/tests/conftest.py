import pytest
from homeai.config import get_settings

@pytest.fixture(autouse=True)
def isolated_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.sqlite"))
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("RUN_SCHEDULER", "false")
    monkeypatch.setenv("PROTECT_WEBHOOK_TOKEN", "test-token-secret")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
