from datetime import datetime, timedelta, timezone
from fastmcp import FastMCP
from ..integrations.octopus import OctopusRates
mcp = FastMCP("octopus-readonly")

@mcp.tool
async def get_electricity_prices(hours: int = 24) -> list[dict]:
    """Read half-hourly import/export prices in GBP/kWh from the configured Octopus tariff."""
    if hours < 1 or hours > 48:
        raise ValueError("Allowed horizon: 1 to 48 hours")
    now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    starts = [now + timedelta(minutes=i*30) for i in range(hours*2)]
    imp, exp = await OctopusRates().slots(starts)
    return [{"start": t.isoformat(), "import_gbp_per_kwh": imp[i], "export_gbp_per_kwh": exp[i]} for i,t in enumerate(starts)]

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8102)
