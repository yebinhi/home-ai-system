from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from ..config import get_settings
from ..db import initialize, recent_plans, save_plan
from ..integrations.foxess import FoxCloud
from ..integrations.octopus import OctopusRates
from ..integrations.weather import forecast_kwh
from ..energy.optimizer import optimise
from ..models import InputSlot, EnergyPlan


def forecast_start() -> datetime:
    now = datetime.now(timezone.utc)
    minute = (now.minute // 30 + 1) * 30
    return now.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minute)


async def create_plan() -> EnergyPlan:
    initialize()
    cfg = get_settings()
    start = forecast_start()
    starts = [start + timedelta(minutes=i * 30) for i in range(96)]
    status = await FoxCloud().status()
    solar, load, quality = await forecast_kwh(starts)
    imp, exp = await OctopusRates().slots(starts)
    slots = [
        InputSlot(
            start=t, solar_kwh=solar[i], load_kwh=load[i],
            import_gbp_per_kwh=imp[i], export_gbp_per_kwh=exp[i],
        ) for i, t in enumerate(starts)
    ]
    plan = optimise(slots, status.soc_pct, cfg)
    plan.forecast_quality = quality
    if not cfg.export_enabled:
        plan.notes.append("Export is disabled: MPAN, export tariff and DNO limit must be verified first.")
    save_plan(plan)
    return plan


def plan_for_display(now: datetime | None = None) -> EnergyPlan | None:
    """Each half-hour of the local day keeps the newest saved plan that covered it.

    A new plan starts at the next half-hour, so the latest row alone leaves the
    morning empty. Older rows stay in the database and fill those hours here.
    Hours that no saved plan ever covered stay absent.
    """
    plans = recent_plans(400)
    if not plans:
        return None
    latest = plans[0]
    tz = ZoneInfo(get_settings().app_timezone)
    clock = now.astimezone(tz) if now else datetime.now(tz)
    midnight = clock.replace(hour=0, minute=0, second=0, microsecond=0)
    # 26h always lands on the next calendar date, including a 25-hour clock change.
    day_end = (midnight + timedelta(hours=26)).astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    step = timedelta(minutes=30)
    stitched = []
    cursor = midnight
    while cursor < day_end:
        instant = cursor.astimezone(timezone.utc)
        slot = _newest_covering(plans, instant)
        if slot is not None:
            stitched.append(slot.model_copy(update={"start": instant}))
        cursor += step
    if not stitched:
        return latest
    return latest.model_copy(update={"slots": stitched})


def _newest_covering(plans: list[EnergyPlan], instant: datetime):
    target = instant.astimezone(timezone.utc)
    for plan in plans:
        width = timedelta(minutes=plan.step_minutes or 30)
        for slot in plan.slots:
            start = slot.start.astimezone(timezone.utc)
            if start <= target < start + width:
                return slot
    return None


def schedule_preview(plan: EnergyPlan) -> dict:
    """Illustrative 24h mode grouping. NOT semantically equivalent to MILP kWh dispatch."""
    from zoneinfo import ZoneInfo
    cfg = get_settings()
    rows = plan.slots[:48]
    groups = []
    for s in rows:
        local = s.start.astimezone(ZoneInfo(cfg.app_timezone))
        end = (s.start + timedelta(minutes=30)).astimezone(ZoneInfo(cfg.app_timezone))
        # Treat midnight crossing and day-light-saving transitions as boundaries.
        segment = {
            "start": local.isoformat(), "end": end.isoformat(), "workMode": s.mode_hint,
        }
        if groups and groups[-1]["workMode"] == segment["workMode"] and groups[-1]["end"] == segment["start"]:
            groups[-1]["end"] = segment["end"]
        else:
            groups.append(segment)
    return {
        "status": "PREVIEW_ONLY_NOT_SAFE_TO_APPLY",
        "reason": "MILP energy flows cannot be translated exactly to KH7 work modes without device/firmware calibration.",
        "periods": groups,
    }
