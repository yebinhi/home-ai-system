from fastmcp import FastMCP
from ..integrations.foxess import FoxCloud
mcp = FastMCP("foxess-readonly")

@mcp.tool
async def get_device_status() -> dict:
    """Read Fox ESS battery SOC, solar, household load, grid and battery power."""
    return (await FoxCloud().status()).model_dump(mode="json")

@mcp.tool
async def get_energy_yield() -> dict:
    """Read today's, this month's, and lifetime generation in kWh. Does not change the device."""
    return (await FoxCloud().generation()).model_dump(mode="json")

@mcp.tool
async def get_foxcloud_schedule() -> dict:
    """Read current FoxCloud scheduler. This tool does not change the device."""
    return await FoxCloud().get_schedule()

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8101)
