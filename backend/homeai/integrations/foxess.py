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
        """PV production in kWh: today and this month from the plant report, lifetime from the PV meter.

        Fox's /op/v0/device/generation `today` is inverter output, not the Daily production shown in the app.
        """
        if self.cfg.mock_mode:
            return EnergyYield(
                today_kwh=0, month_kwh=0, cumulative_kwh=0, source="SIMULATED",
                timestamp=datetime.now(ZoneInfo(self.cfg.app_timezone)),
            )
        global _yield_cache
        now_ts = time.time()
        if _yield_cache and now_ts - _yield_cache[0] < _YIELD_TTL_SECONDS:
            return _yield_cache[1]
        local = datetime.now(ZoneInfo(self.cfg.app_timezone))
        report = await self._post("/op/v0/device/report/query", {
            "sn": self.cfg.fox_device_sn,
            "year": local.year,
            "month": local.month,
            "dimension": "month",
            "variables": ["PVEnergyTotal"],
        })
        rows = {row.get("variable"): row.get("values") or [] for row in (report.get("result") or [])}
        days = rows.get("PVEnergyTotal") or []
        if local.day - 1 >= len(days):
            raise RuntimeError("FoxCloud report did not include today's PV production")
        raw = await self.raw_variables()
        datas = ((raw.get("result") or [{}])[0].get("datas") or [])
        lifetime = next((item.get("value") for item in datas if item.get("variable") == "PVEnergyTotal"), None)
        if lifetime is None:
            raise RuntimeError("FoxCloud telemetry did not include PVEnergyTotal")
        parsed = EnergyYield(
            today_kwh=round(float(days[local.day - 1]), 3),
            month_kwh=round(sum(float(value) for value in days), 3),
            cumulative_kwh=round(float(lifetime), 3),
            source="FOX_CLOUD", timestamp=local,
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
