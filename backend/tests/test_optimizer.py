from datetime import datetime, timedelta, timezone
from homeai.config import Settings
from homeai.energy.optimizer import optimise
from homeai.models import InputSlot


def example_slots():
    now = datetime(2026, 10, 14, 23, 30, tzinfo=timezone.utc)
    slots = []
    for i in range(24):
        t = now + timedelta(minutes=30*i)
        cheap = i < 8
        solar = 0.9 if 10 <= i <= 17 else 0.0
        slots.append(InputSlot(
            start=t, solar_kwh=solar, load_kwh=0.3,
            import_gbp_per_kwh=0.08 if cheap else 0.30,
            export_gbp_per_kwh=0.12,
        ))
    return slots


def config():
    return Settings(
        _env_file=None,
        mock_mode=True,
        export_enabled=True, export_limit_kw=3.68,
        battery_capacity_kwh=5, battery_min_soc=10, battery_max_soc=100,
        battery_max_charge_kw=3, battery_max_discharge_kw=3,
        grid_import_limit_kw=10,
    )


def test_overnight_charge_when_export_price_above_offpeak():
    result = optimise(example_slots(), 20, config())
    assert result.predicted_export_revenue_gbp > 0
    assert sum(s.grid_charge_kwh for s in result.slots[:8]) > 1.0
    assert sum(s.export_kwh for s in result.slots[10:18]) > 1.0
    assert result.executable is False


def test_battery_reserve_and_physical_balance():
    cfg = config()
    result = optimise(example_slots(), 20, cfg)
    for slot in result.slots:
        assert cfg.battery_min_soc - 1e-3 <= slot.soc_end_pct <= cfg.battery_max_soc + 1e-3
        assert slot.import_kwh <= cfg.grid_import_limit_kw * 0.5 + 1e-3
        assert slot.export_kwh <= cfg.export_limit_kw * 0.5 + 1e-3
        assert slot.grid_charge_kwh < 1e-3 or slot.battery_home_kwh < 1e-3
        assert slot.import_kwh < 1e-3 or slot.export_kwh < 1e-3
    assert result.slots[-1].soc_end_pct >= 20 - 1e-3


def test_export_off_means_no_export():
    cfg = Settings(_env_file=None, mock_mode=True, export_enabled=False, export_limit_kw=0,
                   battery_capacity_kwh=5, battery_max_charge_kw=3, battery_max_discharge_kw=3)
    result = optimise(example_slots(), 30, cfg)
    assert all(x.export_kwh < 1e-6 for x in result.slots)
