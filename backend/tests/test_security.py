from homeai.db import initialize, save_event, recent_events
from homeai.security.events import parse_unifi


def test_unifi_post_and_deduplicate():
    initialize()
    body = {"alarm":{"name":"Front Door Person", "triggers":[{"key":"person", "device":"frontcam"}]},"timestamp":1722526793954}
    event = parse_unifi(body)
    assert event.severity == "high"
    assert event.camera == "frontcam"
    assert save_event(event)
    assert not save_event(event)
    assert len(recent_events()) == 1
