import hashlib
from homeai.config import Settings
from homeai.integrations.foxess import FoxCloud


def test_signature_formula():
    path, token, stamp = "/op/v1/device/real/query", "ABC", "1720000000000"
    expected = hashlib.md5(f"{path}\r\n{token}\r\n{stamp}".encode()).hexdigest()
    assert len(expected) == 32
    assert expected == hashlib.md5((path + "\r\nABC\r\n1720000000000").encode()).hexdigest()


def test_mock_generation_does_not_call_fox():
    import asyncio
    result = asyncio.run(FoxCloud().generation())
    assert result.source == "SIMULATED"
    assert result.today_kwh == 0


def test_generation_reads_today_kwh(monkeypatch):
    import asyncio
    from homeai.config import get_settings
    import homeai.integrations.foxess as fox

    monkeypatch.setenv("MOCK_MODE", "false")
    monkeypatch.setenv("FOX_API_TOKEN", "token")
    monkeypatch.setenv("FOX_DEVICE_SN", "SN1")
    get_settings.cache_clear()
    fox._yield_cache = None
    calls = {"n": 0}

    async def fake_exchange(_self, method, path, **kwargs):
        calls["n"] += 1
        assert method == "GET"
        assert path == "/op/v0/device/generation"
        assert kwargs["params"] == {"sn": "SN1"}
        return {"errno": 0, "result": {"today": 16.199999, "month": 60, "cumulative": 187.5}}

    monkeypatch.setattr(FoxCloud, "_exchange", fake_exchange)
    first = asyncio.run(FoxCloud().generation())
    second = asyncio.run(FoxCloud().generation())
    assert first.today_kwh == 16.2
    assert first.month_kwh == 60
    assert first.cumulative_kwh == 187.5
    assert first.source == "FOX_CLOUD"
    assert second.today_kwh == 16.2
    assert calls["n"] == 1
    fox._yield_cache = None
    get_settings.cache_clear()


def test_hardware_writes_disabled():
    import asyncio
    controller = FoxCloud()
    try:
        asyncio.run(controller.set_schedule([]))
        assert False, "Must not write to a device"
    except PermissionError:
        pass
