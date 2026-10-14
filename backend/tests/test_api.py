from fastapi.testclient import TestClient
from homeai.main import app


def test_health_and_protect_webhook():
    with TestClient(app) as c:
        health = c.get("/api/health").json()
        assert health["device_writes"] is False
        body = {"alarm": {"name": "Vehicle", "triggers": [{"key": "vehicle", "device": "drive"}]},"timestamp": 1722526793954}
        assert c.post("/api/webhooks/unifi",json=body).status_code == 401
        a = c.post("/api/webhooks/unifi",json=body,headers={"X-HomeAI-Token":"test-token-secret"})
        assert a.status_code == 200
        assert a.json()["new"] is True
        b = c.post("/api/webhooks/unifi",json=body,headers={"X-HomeAI-Token":"test-token-secret"})
        assert b.json()["new"] is False
        assert len(c.get("/api/security/events").json()) == 1
