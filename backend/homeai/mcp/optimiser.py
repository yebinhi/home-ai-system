from fastmcp import FastMCP
from ..db import initialize, latest_plan
mcp = FastMCP("energy-optimiser-readonly")

@mcp.tool
async def get_latest_energy_plan() -> dict:
    """Read the latest simulated plan and predicted costs. No hardware control."""
    initialize()
    plan = latest_plan()
    return plan.model_dump(mode="json") if plan else {"message": "No plan generated yet"}

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8104)
