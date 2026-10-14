"""Octopus half-hourly rate adapter; no guessed real-rate fallback."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import httpx
from ..config import get_settings


def demo_rate_gbp(start: datetime) -> float:
    cfg = get_settings()
    local = start.astimezone(ZoneInfo(cfg.app_timezone))
    minute = local.hour * 60 + local.minute
    return cfg.demo_import_offpeak_gbp if (minute >= 23 * 60 + 30 or minute < 5 * 60 + 30) else cfg.demo_import_peak_gbp


class OctopusRates:
    def __init__(self):
        self.cfg = get_settings()

    async def _rate_intervals(self, product: str, tariff: str, start: datetime, end: datetime) -> list[dict]:
        if not product or not tariff:
            raise RuntimeError("Live Octopus tariff product and tariff IDs are required")
        path = f"https://api.octopus.energy/v1/products/{product}/electricity-tariffs/{tariff}/standard-unit-rates/"
        params = {"period_from": start.isoformat(), "period_to": end.isoformat(), "page_size": 1500}
        output = []
        async with httpx.AsyncClient(timeout=25) as client:
            for _ in range(4):
                response = await client.get(path, params=params)
                response.raise_for_status()
                obj = response.json()
                output.extend(obj.get("results", []))
                if not obj.get("next"):
                    break
                path, params = obj["next"], None
        return output

    @staticmethod
    def _lookup(intervals: list[dict], at: datetime) -> float:
        matches = []
        for rate in intervals:
            start = datetime.fromisoformat(rate["valid_from"].replace("Z", "+00:00"))
            end_txt = rate.get("valid_to")
            end = datetime.fromisoformat(end_txt.replace("Z", "+00:00")) if end_txt else datetime.max.replace(tzinfo=timezone.utc)
            if start <= at < end:
                matches.append(rate)
        if not matches:
            raise RuntimeError(f"No Octopus tariff rate published for {at.isoformat()}; refusing to guess")
        # The same window is published twice. Household direct debit is the contractual rate.
        chosen = next((rate for rate in matches if rate.get("payment_method") in (None, "DIRECT_DEBIT")), matches[0])
        return float(chosen["value_inc_vat"]) / 100.0

    def _use_live_rates(self) -> bool:
        return bool(self.cfg.octopus_import_product and self.cfg.octopus_import_tariff)

    async def slots(self, starts: list[datetime]) -> tuple[list[float], list[float]]:
        if not starts:
            return [], []
        # Demo prices apply only when no real tariff is configured. Fox and security can stay in mock mode.
        if not self._use_live_rates():
            if self.cfg.mock_mode:
                return [demo_rate_gbp(x) for x in starts], [self.cfg.demo_export_gbp if self.cfg.export_enabled else 0.0] * len(starts)
            raise RuntimeError("Live Octopus tariff product and tariff IDs are required")
        end = starts[-1] + timedelta(minutes=30)
        imp = await self._rate_intervals(self.cfg.octopus_import_product, self.cfg.octopus_import_tariff, starts[0], end)
        exports = []
        if self.cfg.export_enabled:
            exports = await self._rate_intervals(self.cfg.octopus_export_product, self.cfg.octopus_export_tariff, starts[0], end)
        return ([self._lookup(imp, t) for t in starts], [self._lookup(exports, t) if self.cfg.export_enabled else 0.0 for t in starts])
