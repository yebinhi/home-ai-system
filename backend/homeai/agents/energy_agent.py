"""Deterministic Energy Agent entry point (no LLM dependency).

A trigger may be the daily scheduler or an explicit simulation request.
Real inverter actuation is deliberately outside this module.
"""
from ..models import EnergyPlan
from ..services.energy_service import create_plan


async def run_energy_planning() -> EnergyPlan:
    return await create_plan()
