"""FoxCloud read-only adapter. No schedule writes in this starter release.

Reference: https://www.foxesscloud.com/public/i18n/en/OpenApiDocument.html
Headers sign PATH + CRLF + TOKEN + CRLF + TIMESTAMP (milliseconds).
"""
import hashlib
import math
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from ..config import get_settings
from ..models import DeviceStatus, EnergyYield

# Today's yield changes slowly. Reuse one Fox call across the UI poll and chat.
_yield_cache: tuple[float, EnergyYield] | None = None
_YIELD_TTL_SECONDS = 600


class FoxCloud:
    def __init__(self):
        self.cfg = get_settings()

    def _signed_headers(self, path: str) -> dict:
        if not self.cfg.fox_api_token or not self.cfg.fox_device_sn:
            raise RuntimeError("Set FOX_API_TOKEN and FOX_DEVICE_SN before using live mode")
        stamp = str(int(time.time() * 1000))
        signature = hashlib.md5(f"{path}\r\n{self.cfg.fox_api_token}\r\n{stamp}".encode()).hexdigest()
        return {
            "token": self.cfg.fox_api_token, "timestamp": stamp, "signature": signature,
            "lang": "en", "User-Agent": "HomeAIPlatform/0.1",
        }

    async def _exchange(self, method: str, path: str, **kwargs) -> dict:
        async with httpx.AsyncClient(base_url=self.cfg.fox_api_base, timeout=20) as client:
            response = await client.request(method, path, headers=self._signed_headers(path), **kwargs)
            response.raise_for_status()
            data = response.json()
        if data.get("errno") != 0:
            raise RuntimeError(f"FoxCloud returned error {data.get('errno')}: {data.get('msg', 'unknown')}")
        return data

    async def _post(self, path: str, body: dict) -> dict:
        return await self._exchange("POST", path, json=body)

    async def raw_variables(self) -> dict:
        if self.cfg.mock_mode:
            return {"result": [{"deviceSN": "DEMO", "datas": [{"variable": "SoC", "value": 85, "unit": "%"}]}]}
        return await self._post("/op/v1/device/real/query", {"sns": [self.cfg.fox_device_sn]})

    async def status(self) -> DeviceStatus:
        if self.cfg.mock_mode:
            now = datetime.now(ZoneInfo(self.cfg.app_timezone))
            sun = max(0.0, math.sin(math.pi * (now.hour + now.minute / 60 - 7) / 11))
            solar = round(self.cfg.pv_kwp * sun * 0.55, 2)
            return DeviceStatus(
                soc_pct=85, solar_kw=solar, load_kw=0.35,
                grid_kw=round(0.35 - solar, 2), battery_kw=0,
                source="SIMULATED", timestamp=now,
            )
        data = await self.raw_variables()
        entries = data.get("result") or []
        if not entries:
            raise RuntimeError("FoxCloud did not return inverter telemetry")
        vals = {str(x.get("variable", "")).lower(): x.get("value") for x in entries[0].get("datas", [])}

        def get_value(*aliases, required=False):
            for alias in aliases:
                val = vals.get(alias.lower())
                if val is not None:
                    return float(val)
            if required:
                raise RuntimeError(f"FoxCloud telemetry variable not found: {aliases}; inspect /api/energy/raw")
            return 0.0

        # Some Fox inverters use different variable names. Confirm variables/units on KH7.
        return DeviceStatus(
            soc_pct=get_value("SoC", "SoC1", "soc", required=True),
            solar_kw=max(0, get_value("pvPower")),
            load_kw=max(0, get_value("loadsPower", "loadPower")),
            grid_kw=get_value("gridConsumptionPower", "gridPower"),
            battery_kw=get_value("batPower", "batteryPower"),
            source="FOX_CLOUD", timestamp=datetime.now(ZoneInfo(self.cfg.app_timezone)),
        )

    async def generation(self) -> EnergyYield:
        """Today, month, and lifetime generation in kWh from the plant timezone."""
        if self.cfg.mock_mode:
            return EnergyYield(
                today_kwh=0, month_kwh=0, cumulative_kwh=0, source="SIMULATED",
                timestamp=datetime.now(ZoneInfo(self.cfg.app_timezone)),
            )
        global _yield_cache
        now_ts = time.time()
        if _yield_cache and now_ts - _yield_cache[0] < _YIELD_TTL_SECONDS:
            return _yield_cache[1]
        data = await self._exchange("GET", "/op/v0/device/generation", params={"sn": self.cfg.fox_device_sn})
        result = data.get("result") or {}

        def kwh(key: str) -> float:
            value = result.get(key)
            if value is None:
                raise RuntimeError(f"FoxCloud generation did not include {key}")
            return round(float(value), 3)

        parsed = EnergyYield(
            today_kwh=kwh("today"), month_kwh=kwh("month"), cumulative_kwh=kwh("cumulative"),
            source="FOX_CLOUD", timestamp=datetime.now(ZoneInfo(self.cfg.app_timezone)),
        )
        _yield_cache = (now_ts, parsed)
        return parsed

    async def get_schedule(self) -> dict:
        if self.cfg.mock_mode:
            return {"result": {"enable": 0, "groups": []}, "simulated": True}
        return await self._post("/op/v3/device/scheduler/get", {"deviceSN": self.cfg.fox_device_sn})

    async def set_schedule(self, _groups: list[dict]):
        # Fox V1/V2/V3 parameters/semantics require KH7 firmware validation.
        # Never expose an unverified device command to LLMs.
        raise PermissionError("Hardware writes intentionally disabled; validate KH7 Scheduler API and add an approved executor")
