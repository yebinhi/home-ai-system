from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from homeai.db import initialize, save_plan
from homeai.models import EnergyPlan, PlanSlot
from homeai.services.energy_service import plan_for_display

LONDON = ZoneInfo("Europe/London")


def _slot(start: datetime, mode: str) -> PlanSlot:
    return PlanSlot(
        start=start, solar_kwh=0, load_kwh=0.1,
        import_gbp_per_kwh=0.2, export_gbp_per_kwh=0,
        soc_start_pct=80, soc_end_pct=80,
        import_kwh=0, export_kwh=0, grid_charge_kwh=0,
        solar_charge_kwh=0, battery_home_kwh=0,
        battery_export_kwh=0, curtailed_kwh=0, mode_hint=mode,
    )


def _plan(plan_id: str, created: datetime, start: datetime, mode: str, count: int = 4) -> EnergyPlan:
    slots = [_slot(start + timedelta(minutes=30 * i), mode) for i in range(count)]
    return EnergyPlan(
        id=plan_id, created_at=created, source="TEST", simulated=True,
        forecast_quality="TEST", horizon_hours=2, step_minutes=30,
        predicted_import_cost_gbp=0, predicted_export_revenue_gbp=0,
        predicted_degradation_cost_gbp=0, predicted_net_cost_gbp=1.25,
        notes=[], slots=slots,
    )


def test_today_keeps_the_newest_plan_that_covered_each_hour():
    initialize()
    morning = datetime(2026, 10, 15, 0, 0, tzinfo=LONDON).astimezone(timezone.utc)
    afternoon = datetime(2026, 10, 15, 15, 0, tzinfo=LONDON).astimezone(timezone.utc)
    save_plan(_plan("old", datetime(2026, 10, 14, 16, 0, tzinfo=timezone.utc), morning, "ForceCharge", 48))
    save_plan(_plan("new", datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc), afternoon, "SelfUse", 16))
    shown = plan_for_display(datetime(2026, 10, 15, 16, 40, tzinfo=LONDON))
    assert shown is not None
    assert shown.id == "new"
    assert shown.predicted_net_cost_gbp == 1.25
    by_local = {slot.start.astimezone(LONDON).hour: slot.mode_hint for slot in shown.slots}
    assert by_local[0] == "ForceCharge"
    assert by_local[14] == "ForceCharge"
    assert by_local[15] == "SelfUse"
    assert by_local[22] == "SelfUse"
    assert by_local[23] == "ForceCharge"
