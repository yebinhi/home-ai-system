"""Notification sink abstraction. Real push integrations require explicit setup."""
from typing import Protocol
from ..models import SecurityEvent


class NotificationSink(Protocol):
    async def send(self, event: SecurityEvent) -> None: ...


class DisabledNotificationSink:
    async def send(self, event: SecurityEvent) -> None:
        # Native UniFi Protect alerts remain the fallback.
        return None
