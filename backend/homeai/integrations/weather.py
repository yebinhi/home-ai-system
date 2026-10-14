"""Illustrative PV/load forecasts. Replace with calibrated multi-orientation forecasts before hardware control."""
from datetime import datetime, timedelta, timezone
import math
import httpx
from zoneinfo import ZoneInfo
from ..config import get_settings


def mock_hour_profile(time: datetime) -> float:
    local = time.astimezone(ZoneInfo(get_settings().app_timezone))
    hour = local.hour + local.minute / 60
    return max(0.0, math.sin(math.pi * (hour - 7) / 11))


async def forecast_kwh(starts: list[datetime]) -> tuple[list[float], list[float], str]:
    cfg = get_settings()
    halfhour = 0.5
    hour_load = []
    for t in starts:
        local = t.astimezone(ZoneInfo(cfg.app_timezone))
        # Uncalibrated domestic load profile, typically ~7 kWh/day.
        load_kw = 0.20 + (0.28 if (7 <= local.hour < 9 or 18 <= local.hour < 23) else 0.0)
        hour_load.append(round(load_kw * halfhour, 4))
    if cfg.mock_mode:
        pv = [round(cfg.pv_kwp * mock_hour_profile(t) * 0.54 * halfhour, 4) for t in starts]
        return pv, hour_load, "DEMO synthetic solar and load forecasts"

    # Open-Meteo irradiance is horizontal, not plane-of-array; approximate only.
    # Geo reference: New Malden area, not a precise residential address.
    async with httpx.AsyncClient(timeout=25) as client:
        resp = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": 51.40, "longitude": -0.26,
                "hourly": "shortwave_radiation", "timezone": "UTC", "forecast_days": 4,
            },
        )
        resp.raise_for_status()
        hourly = resp.json().get("hourly", {})
    irradiation = {
        datetime.fromisoformat(t).replace(tzinfo=timezone.utc): float(v or 0)
        for t, v in zip(hourly.get("time", []), hourly.get("shortwave_radiation", []))
    }
    # Half-hour slots use corresponding hourly irradiance bucket.
    pv = []
    for start in starts:
        hour = start.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        if hour not in irradiation:
            raise RuntimeError("Weather forecast does not cover the optimisation horizon")
        kw = cfg.pv_kwp * min(1.0, max(0.0, irradiation[hour] / 1000)) * cfg.pv_forecast_factor
        pv.append(round(kw * halfhour, 4))
    return pv, hour_load, "UNCALIBRATED Open-Meteo horizontal irradiance and assumed household load"
