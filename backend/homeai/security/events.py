"""UniFi Alarm Manager GET/POST ingest. Payload shape follows vendor example."""
from datetime import datetime, timezone
import hashlib
import json
from ..models import SecurityEvent


def parse_unifi(payload: dict) -> SecurityEvent:
    alarm = payload.get("alarm") or {}
    name = str(alarm.get("name") or "UniFi Alarm")
    triggers = alarm.get("triggers") or []
    camera = str(triggers[0].get("device") or "unknown") if triggers else "unknown"
    trigger = str(triggers[0].get("key") or "") if triggers else ""
    kind = (trigger or name).lower().replace(" ", "_")[:70]
    high = any(x in kind for x in ("person", "intrusion", "doorbell", "trespass"))
    severity = "high" if high else ("medium" if "vehicle" in kind or "motion" in kind else "low")
    timestamp = payload.get("timestamp")
    when = datetime.fromtimestamp(int(timestamp) / 1000, timezone.utc) if isinstance(timestamp, (int, float)) else datetime.now(timezone.utc)
    # Event key is deterministic for webhook delivery replays.
    event_id = str(payload.get("event_id") or hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:32])
    return SecurityEvent(
        id=event_id, timestamp=when, received_at=datetime.now(timezone.utc),
        camera=camera, kind=kind, severity=severity,
        summary=f"{name} triggered on camera/device {camera}",
    )
