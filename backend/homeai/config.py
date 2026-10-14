from functools import lru_cache
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mock_mode: bool = True
    run_scheduler: bool = True
    allow_device_writes: bool = False
    export_enabled: bool = False
    export_limit_kw: float = Field(0, ge=0)
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    app_timezone: str = "Europe/London"
    plan_hour_local: int = Field(22, ge=0, le=23)
    database_path: str = "./data/home-ai.sqlite"

    pv_kwp: float = Field(6.86, gt=0)
    battery_capacity_kwh: float = Field(11, gt=0)
    battery_min_soc: float = Field(10, ge=0, le=100)
    battery_max_soc: float = Field(100, ge=0, le=100)
    battery_max_charge_kw: float = Field(5, gt=0)
    battery_max_discharge_kw: float = Field(5, gt=0)
    grid_import_limit_kw: float = Field(10, gt=0)
    roundtrip_charge_eff: float = Field(0.95, gt=0, le=1)
    roundtrip_discharge_eff: float = Field(0.95, gt=0, le=1)
    degradation_gbp_per_kwh: float = Field(0.015, ge=0)
    pv_forecast_factor: float = Field(0.78, ge=0, le=1)

    demo_import_offpeak_gbp: float = Field(0.08, ge=0)
    demo_import_peak_gbp: float = Field(0.30, ge=0)
    demo_export_gbp: float = Field(0.12, ge=0)

    fox_api_token: str = ""
    fox_device_sn: str = ""
    fox_api_base: str = "https://www.foxesscloud.com"
    octopus_api_key: str = ""
    octopus_import_product: str = ""
    octopus_import_tariff: str = ""
    octopus_export_product: str = ""
    octopus_export_tariff: str = ""
    vision_enabled: bool = False
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    protect_webhook_token: str = "change-me-before-live"
    mcp_foxess_url: str = "http://127.0.0.1:8101/mcp"
    mcp_octopus_url: str = "http://127.0.0.1:8102/mcp"
    mcp_unifi_url: str = "http://127.0.0.1:8103/mcp"
    mcp_optimiser_url: str = "http://127.0.0.1:8104/mcp"

    @model_validator(mode="after")
    def check_battery(self):
        if self.battery_min_soc >= self.battery_max_soc:
            raise ValueError("Battery min SOC must be below max SOC")
        if self.allow_device_writes:
            raise ValueError("Hardware writes deliberately unavailable in this starter release")
        return self


@lru_cache

def get_settings() -> Settings:
    return Settings()
