"""Event-driven Security Agent: event metadata only, independent of cloud AI."""
from ..security.events import parse_unifi
from ..db import save_event
from ..models import SecurityEvent


def record_protect_alarm(payload: dict) -> tuple[SecurityEvent, bool]:
    event = parse_unifi(payload)
    inserted = save_event(event)
    return event, inserted
