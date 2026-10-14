import asyncio
from datetime import datetime, timezone

from homeai.config import get_settings
from homeai.integrations.octopus import OctopusRates


def test_configured_tariff_uses_published_rate_while_mock_mode(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("OCTOPUS_IMPORT_PRODUCT", "VAR-22-11-01")
    monkeypatch.setenv("OCTOPUS_IMPORT_TARIFF", "E-1R-VAR-22-11-01-C")
    monkeypatch.setenv("EXPORT_ENABLED", "false")
    get_settings.cache_clear()

    async def fake_intervals(_self, product, tariff, _start, _end):
        assert product == "VAR-22-11-01"
        assert tariff == "E-1R-VAR-22-11-01-C"
        return [
            {"valid_from": "2020-01-01T00:00:00Z", "valid_to": None, "value_inc_vat": 28.0896, "payment_method": "NON_DIRECT_DEBIT"},
            {"valid_from": "2020-01-01T00:00:00Z", "valid_to": None, "value_inc_vat": 26.5956, "payment_method": "DIRECT_DEBIT"},
        ]

    monkeypatch.setattr(OctopusRates, "_rate_intervals", fake_intervals)
    start = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    imp, exp = asyncio.run(OctopusRates().slots([start]))
    assert abs(imp[0] - 0.265956) < 1e-9
    assert exp == [0.0]


def test_demo_prices_when_tariff_is_not_configured(monkeypatch):
    monkeypatch.setenv("MOCK_MODE", "true")
    monkeypatch.setenv("OCTOPUS_IMPORT_PRODUCT", "")
    monkeypatch.setenv("OCTOPUS_IMPORT_TARIFF", "")
    get_settings.cache_clear()
    start = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
    imp, exp = asyncio.run(OctopusRates().slots([start]))
    assert imp == [0.30]
    assert exp == [0.0]
