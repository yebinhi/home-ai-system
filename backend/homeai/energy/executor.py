"""Protected execution boundary for a future KH7 schedule compiler.

No writable API endpoints or MCP tools exist in this scaffold.
"""
from ..models import EnergyPlan


def compile_and_apply(_plan: EnergyPlan, _approval_token: str):
    raise PermissionError(
        "No hardware writing is implemented. Device firmware schedule mapping, "
        "SOC/power checks, explicit user approval and readback validation are required."
    )
