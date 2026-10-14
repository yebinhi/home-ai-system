from fastapi.testclient import TestClient
from homeai.main import app


def test_system_config_never_exposes_credentials():
    with TestClient(app) as c:
        config = c.get('/api/system/config')
        assert config.status_code == 200
        assert config.json()['device_writes_enabled'] is False
        assert 'fox_api_token' not in config.text
        assert c.get('/api/energy/history').json() == []
