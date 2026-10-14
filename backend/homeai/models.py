from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class DeviceStatus(BaseModel):
    soc_pct: float = Field(ge=0, le=100)
    solar_kw: float = Field(ge=0)
    load_kw: float = Field(ge=0)
    grid_kw: float
    battery_kw: float
    source: str
    timestamp: datetime


class EnergyYield(BaseModel):
    today_kwh: float = Field(ge=0)
    month_kwh: float = Field(ge=0)
    cumulative_kwh: float = Field(ge=0)
    source: str
    timestamp: datetime


class InputSlot(BaseModel):
    start: datetime
    solar_kwh: float = Field(ge=0)
    load_kwh: float = Field(ge=0)
    import_gbp_per_kwh: float = Field(ge=0)
    export_gbp_per_kwh: float = Field(ge=0)


class PlanSlot(InputSlot):
    soc_start_pct: float
    soc_end_pct: float
    import_kwh: float
    export_kwh: float
    grid_charge_kwh: float
    solar_charge_kwh: float
    battery_home_kwh: float
    battery_export_kwh: float
    curtailed_kwh: float
    mode_hint: Literal["SelfUse", "Feedin", "ForceCharge", "Backup"]


class EnergyPlan(BaseModel):
    id: str
    created_at: datetime
    source: str
    simulated: bool
    forecast_quality: str
    executable: bool = False
    currency: str = "GBP"
    horizon_hours: int
    step_minutes: int = 30
    predicted_import_cost_gbp: float
    predicted_export_revenue_gbp: float
    predicted_degradation_cost_gbp: float
    predicted_net_cost_gbp: float
    notes: list[str]
    slots: list[PlanSlot]


class SecurityEvent(BaseModel):
    id: str
    timestamp: datetime
    received_at: datetime
    camera: str
    kind: str
    severity: Literal["low", "medium", "high"]
    summary: str
    source: str = "unifi_protect"


class ChatInput(BaseModel):
    message: str = Field(min_length=1, max_length=3000)


class ChatOutput(BaseModel):
    answer: str
