"""48h half-hour MILP energy optimiser. No battery-to-grid export by default.

Flows (kWh per slot):
  pv_to_home, pv_to_batt, pv_to_grid, curtailed,
  grid_to_home, grid_to_batt, batt_to_home, batt_to_grid,
  binary_charge, binary_grid_import.
MILP prevents simultaneous charge/discharge and grid import/export.
"""
from datetime import datetime, timezone
from uuid import uuid4
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix

from ..models import InputSlot, PlanSlot, EnergyPlan
from ..config import Settings, get_settings

PV_HOME, PV_BATT, PV_GRID, CURTAIL, GRID_HOME, GRID_BATT, BATT_HOME, BATT_GRID, BINARY_CHARGE, BINARY_IMPORT = range(10)
N_VARS = 10


def optimise(slots: list[InputSlot], initial_soc_pct: float, cfg: Settings | None = None) -> EnergyPlan:
    cfg = cfg or get_settings()
    if not slots:
        raise ValueError("Forecast must contain at least one slot")
    if not cfg.battery_min_soc <= initial_soc_pct <= cfg.battery_max_soc:
        raise ValueError("SOC out of configured bounds")
    n = len(slots)
    step_hours = 0.5
    cmax = cfg.battery_max_charge_kw * step_hours
    dmax = cfg.battery_max_discharge_kw * step_hours
    imax = cfg.grid_import_limit_kw * step_hours
    emax = cfg.export_limit_kw * step_hours if cfg.export_enabled else 0
    capacity = cfg.battery_capacity_kwh
    soc_start = initial_soc_pct * capacity / 100
    soc_min = cfg.battery_min_soc * capacity / 100
    soc_max = cfg.battery_max_soc * capacity / 100
    eta_in, eta_out = cfg.roundtrip_charge_eff, cfg.roundtrip_discharge_eff

    total_vars = n * N_VARS
    c = np.zeros(total_vars)
    lower = np.zeros(total_vars)
    upper = np.full(total_vars, np.inf)
    integer = np.zeros(total_vars, dtype=np.int32)
    rows, cols, vals, bounds_lower, bounds_upper = [], [], [], [], []

    def var(t: int, which: int) -> int:
        return t * N_VARS + which

    def add(coefficients: dict[int, float], lo: float, hi: float):
        r = len(bounds_lower)
        for k, v in coefficients.items():
            rows.append(r)
            cols.append(k)
            vals.append(v)
        bounds_lower.append(lo)
        bounds_upper.append(hi)

    for t, slot in enumerate(slots):
        for v in (GRID_HOME, GRID_BATT):
            c[var(t, v)] += slot.import_gbp_per_kwh
        for v in (PV_GRID, BATT_GRID):
            c[var(t, v)] -= slot.export_gbp_per_kwh
        for v in (PV_BATT, GRID_BATT, BATT_HOME, BATT_GRID):
            c[var(t, v)] += cfg.degradation_gbp_per_kwh / 2

        # Bound battery export to zero: do not assume battery arbitrage is permitted.
        upper[var(t, BATT_GRID)] = 0
        upper[var(t, PV_GRID)] = emax
        upper[var(t, BINARY_CHARGE)] = 1
        upper[var(t, BINARY_IMPORT)] = 1
        integer[var(t, BINARY_CHARGE)] = 1
        integer[var(t, BINARY_IMPORT)] = 1

        add({var(t, PV_HOME): 1, var(t, PV_BATT): 1, var(t, PV_GRID): 1, var(t, CURTAIL): 1},
            slot.solar_kwh, slot.solar_kwh)
        add({var(t, PV_HOME): 1, var(t, GRID_HOME): 1, var(t, BATT_HOME): 1},
            slot.load_kwh, slot.load_kwh)
        # Battery charge OR discharge.
        add({var(t, PV_BATT): 1, var(t, GRID_BATT): 1, var(t, BINARY_CHARGE): -cmax}, -np.inf, 0)
        add({var(t, BATT_HOME): 1, var(t, BATT_GRID): 1, var(t, BINARY_CHARGE): dmax}, -np.inf, dmax)
        # Grid import OR export.
        add({var(t, GRID_HOME): 1, var(t, GRID_BATT): 1, var(t, BINARY_IMPORT): -imax}, -np.inf, 0)
        add({var(t, PV_GRID): 1, var(t, BATT_GRID): 1, var(t, BINARY_IMPORT): emax}, -np.inf, emax)

    # Accumulate SOC, imposing bounds at EVERY step, not merely at horizon end.
    delta: dict[int, float] = {}
    for t in range(n):
        for v in (PV_BATT, GRID_BATT):
            delta[var(t, v)] = eta_in
        for v in (BATT_HOME, BATT_GRID):
            delta[var(t, v)] = -1 / eta_out
        add(delta.copy(), soc_min - soc_start, soc_max - soc_start)
    # Terminal SOC avoids artificial depletion at 48h horizon boundary.
    add(delta.copy(), max(soc_min, soc_start) - soc_start, np.inf)

    a = coo_matrix((vals, (rows, cols)), shape=(len(bounds_lower), total_vars)).tocsr()
    result = milp(
        c=c,
        integrality=integer,
        bounds=Bounds(lower, upper),
        constraints=LinearConstraint(a, bounds_lower, bounds_upper),
        options={"time_limit": 25, "mip_rel_gap": 0.01},
    )
    if result.x is None or result.status not in (0, 1):
        raise RuntimeError(f"Optimisation failed: {result.message}")
    if result.status == 1 and result.mip_gap is not None and result.mip_gap > 0.05:
        raise RuntimeError("Optimiser timed out without a sufficiently good result")

    x = np.maximum(0.0, result.x)
    state = soc_start
    output = []
    import_cost, export_revenue, degradation = 0.0, 0.0, 0.0
    for t, slot in enumerate(slots):
        v = lambda field: float(x[var(t, field)])
        charging = v(PV_BATT) + v(GRID_BATT)
        discharging = v(BATT_HOME) + v(BATT_GRID)
        new_state = state + eta_in * charging - discharging / eta_out
        if v(GRID_BATT) > 0.08:
            mode = "ForceCharge"
        elif v(PV_GRID) > 0.08:
            mode = "Feedin"
        else:
            mode = "SelfUse"
        imp = v(GRID_HOME) + v(GRID_BATT)
        exp = v(PV_GRID) + v(BATT_GRID)
        import_cost += slot.import_gbp_per_kwh * imp
        export_revenue += slot.export_gbp_per_kwh * exp
        degradation += cfg.degradation_gbp_per_kwh * (charging + discharging) / 2
        output.append(PlanSlot(
            **slot.model_dump(),
            soc_start_pct=round(state / capacity * 100, 2),
            soc_end_pct=round(new_state / capacity * 100, 2),
            import_kwh=round(imp, 4), export_kwh=round(exp, 4),
            grid_charge_kwh=round(v(GRID_BATT), 4), solar_charge_kwh=round(v(PV_BATT), 4),
            battery_home_kwh=round(v(BATT_HOME), 4), battery_export_kwh=round(v(BATT_GRID), 4),
            curtailed_kwh=round(v(CURTAIL), 4), mode_hint=mode,
        ))
        state = new_state
    return EnergyPlan(
        id=uuid4().hex,
        created_at=datetime.now(timezone.utc),
        source="SIMULATION" if cfg.mock_mode else "LIVE_READ_ONLY",
        simulated=cfg.mock_mode,
        forecast_quality="PENDING FORECAST QUALITY LABEL",
        horizon_hours=n // 2,
        predicted_import_cost_gbp=round(import_cost, 3),
        predicted_export_revenue_gbp=round(export_revenue, 3),
        predicted_degradation_cost_gbp=round(degradation, 3),
        predicted_net_cost_gbp=round(import_cost - export_revenue + degradation, 3),
        notes=[
            "Optimised cost, not solar self-consumption; cheap overnight grid charge is allowed.",
            "Battery-to-grid export disabled, pending tariff and grid permission review.",
            "Mode hints are illustrative, NOT an executable FoxCloud schedule.",
            "Device writes are disabled in this starter release.",
        ],
        slots=output,
    )
